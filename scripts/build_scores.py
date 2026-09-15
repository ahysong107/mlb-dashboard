"""Compute Ali Score (Baseline x Opportunity composite), modeled HR and
strikeout probabilities, and DUE / OVERPERFORMING / VIPER style flags for
today's slate. All inputs are real Statcast + MLB Stats API data pulled by
the fetch_* scripts -- nothing here is synthetic.
"""
import math

import numpy as np
import pandas as pd

from lib_data import load_df, save_df

LEAGUE_AVG_WOBA_ALLOWED = 0.310


def pct_rank(series):
    s = series.astype(float)
    if s.notna().sum() < 2:
        return pd.Series(50.0, index=s.index)
    return s.rank(pct=True, method="average").fillna(0.5) * 100


def blend(a, b, wa=0.55, wb=0.45):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    both = wa * a + wb * b
    return both.where(a.notna() & b.notna(), a.where(a.notna(), b))


def approx_bbe(df):
    k_frac = df["k_percent"].fillna(0) / 100
    return (df["ab"] - df["pa"] * k_frac).clip(lower=1)


# ---------------------------------------------------------------- batters --

def score_batters(df):
    df = df.copy()
    bbe = approx_bbe(df)
    df["season_hr_per_fb"] = (df["home_run"] / (bbe * df["flyballs_percent"].fillna(0) / 100).clip(lower=1)) * 100

    df["b_barrel"] = blend(df["barrel_batted_rate"], df["w21_barrel_pct"])
    df["b_hardhit"] = blend(df["hard_hit_percent"], df["w21_hard_hit_pct"])
    df["b_xslg"] = blend(df["xslg"], df["w21_xslg_bbe"])
    df["b_fb"] = blend(df["flyballs_percent"], df["w21_fb_pct"])
    # guard against small-sample noise: only trust recent HR/FB once there's
    # a reasonable number of recent fly balls to divide by
    w21_hrfb_reliable = df["w21_hr_per_fb"].where(df["w21_fly_balls"].fillna(0) >= 8)
    df["b_hrfb"] = blend(df["season_hr_per_fb"], w21_hrfb_reliable)
    df["contact_trend"] = (df["last7_barrel_pct"] - df["prior7_barrel_pct"]).fillna(0)

    p_barrel = pct_rank(df["b_barrel"])
    p_hardhit = pct_rank(df["b_hardhit"])
    p_xslg = pct_rank(df["b_xslg"])
    p_fb = pct_rank(df["b_fb"])
    p_hrfb = pct_rank(df["b_hrfb"])
    p_trend = pct_rank(df["contact_trend"])

    df["baseline_score"] = (
        p_barrel * 0.25 + p_hardhit * 0.20 + p_xslg * 0.20 + p_fb * 0.10 + p_hrfb * 0.15 + p_trend * 0.10
    )

    pitch_vuln_raw = (
        df["opp_p_barrel_allowed"].fillna(df["opp_p_barrel_allowed"].median()) * 0.35
        + df["opp_p_hardhit_allowed"].fillna(df["opp_p_hardhit_allowed"].median()) * 0.25
        + df["opp_p_xslg_allowed"].fillna(df["opp_p_xslg_allowed"].median()) * 100 * 0.25
        + df["opp_p_era"].fillna(df["opp_p_era"].median()) * 0.15
    )
    p_pitch_vuln = pct_rank(pitch_vuln_raw)
    df["pitch_matchup_score"] = p_pitch_vuln
    p_park = ((df["park_factor"] - 82) / (120 - 82) * 100).clip(0, 100)
    p_wind = df["wind_score"]
    p_temp = df["temp_score"]
    p_order = df["order_score"]

    df["opportunity_score"] = p_pitch_vuln * 0.40 + p_park * 0.25 + p_wind * 0.15 + p_temp * 0.10 + p_order * 0.10

    # ---- flags ----
    drought = df["days_since_hr"].fillna(999)
    due_mask = (p_barrel >= 70) & (p_hardhit >= 70) & (drought >= 8)
    df["due_bonus"] = np.select(
        [due_mask & (drought >= 14), due_mask],
        [7, 4],
        default=0,
    )

    df["flag_due"] = due_mask
    df["flag_overperforming"] = (df["slg_percent"] - df["xslg"]).fillna(0) >= 0.060
    viper_mask = (df["contact_trend"] >= 6) & (df["last7_hr"].fillna(0) == 0)
    df["flag_viper"] = viper_mask

    df["ali_score"] = (df["baseline_score"] * 0.6 + df["opportunity_score"] * 0.4 + df["due_bonus"]).clip(1, 100)

    # ---- modeled HR probability, from real per-PA HR rate x matchup multiplier ----
    season_hr_rate = (df["home_run"] / df["pa"]).clip(lower=0.002)
    recent_hr_rate = (df["w21_hr"] / df["w21_pa"]).where(df["w21_pa"] >= 10)
    base_rate = blend(season_hr_rate * 100, recent_hr_rate * 100, 0.6, 0.4) / 100

    league_era = df["opp_p_era"].median()
    pitcher_mult = (df["opp_p_era"].fillna(league_era) / league_era).clip(0.6, 1.6) ** 0.5
    park_mult = (df["park_factor"] / 100).clip(0.8, 1.25)
    wind_mult = (0.85 + p_wind / 200).clip(0.85, 1.20)
    matchup_mult = (pitcher_mult * park_mult * wind_mult).clip(0.55, 2.2)

    adj_rate = (base_rate * matchup_mult).clip(0.003, 0.22)
    pa_est = 4.5 - 0.09 * (df["order"].fillna(5) - 1)
    df["hr_probability"] = (1 - (1 - adj_rate) ** pa_est) * 100

    # ---- hit & total-base probability, for parlay legs only ----
    # Savant's xba/batting_avg/slg_percent are already fractions (e.g. .262),
    # not percentages -- no extra /100 needed here.
    hit_rate_pa = blend(df["xba"], df["batting_avg"]) * pitcher_mult.clip(0.75, 1.3)
    df["hit_probability"] = (1 - (1 - hit_rate_pa.clip(0.05, 0.45)) ** pa_est) * 100
    tb_rate_pa = blend(df["b_xslg"], df["slg_percent"]) * pitcher_mult.clip(0.75, 1.3)
    proj_tb = (tb_rate_pa.clip(0.08, 0.9) * pa_est)
    df["projected_tb"] = proj_tb
    df["tb2_probability"] = (1 - np.exp(-proj_tb) * (1 + proj_tb)) * 100  # P(Poisson(proj_tb) >= 2)

    return df


# --------------------------------------------------------------- pitchers --

def score_pitchers(df):
    df = df.copy()
    df["b_k"] = blend(df["k_percent"], df["w21_k_pct"])
    df["b_whiff"] = blend(df["whiff_percent"], df["w21_whiff_pct"])
    df["contact_against"] = blend(df["barrel_batted_rate"], df["w21_barrel_pct_allowed"]) * 0.5 + blend(
        df["hard_hit_percent"], df["w21_hard_hit_pct_allowed"]
    ) * 0.5
    df["k_trend"] = (df["last7_k_pct"] - df["k_percent"]).fillna(0)

    p_k = pct_rank(df["b_k"])
    p_whiff = pct_rank(df["b_whiff"])
    p_contact = 100 - pct_rank(df["contact_against"])
    p_trend = pct_rank(df["k_trend"])

    df["baseline_score"] = p_k * 0.40 + p_whiff * 0.30 + p_contact * 0.15 + p_trend * 0.15

    opp_k = blend(df["opp_lineup_k_pct_season"], df["opp_lineup_k_pct_recent"])
    p_opp_k = pct_rank(opp_k)
    p_park = 100 - ((df["park_factor"] - 82) / (120 - 82) * 100).clip(0, 100)
    df["opportunity_score"] = p_opp_k * 0.75 + p_park * 0.25

    df["ali_score"] = (df["baseline_score"] * 0.65 + df["opportunity_score"] * 0.35).clip(1, 100)

    df["flag_overperforming"] = (
        (df["woba"] - df["xwoba"]).fillna(0) <= -0.035
    ) & (df["p_era"].fillna(99) <= 3.80)
    df["flag_trending_up"] = df["k_trend"] >= 6

    # ---- expected/projected strikeouts + threshold lines ----
    # BF estimate: fixed modern-starter average (~5.2 IP), nudged slightly by
    # how K-prone the opposing lineup is (more Ks -> fewer balls in play ->
    # quicker innings -> marginally deeper outings).
    bf_est = 21.5 * (opp_k.fillna(opp_k.median()) / opp_k.median()).clip(0.85, 1.15)
    df["bf_estimate"] = bf_est
    df["projected_k"] = df["b_k"] / 100 * bf_est
    df["k_std"] = np.sqrt((bf_est * df["b_k"] / 100 * (1 - df["b_k"] / 100)).clip(lower=0.5))

    def norm_sf(x):
        return 0.5 * (1 - math.erf(x / math.sqrt(2)))

    lines = []
    for mean, std in zip(df["projected_k"], df["k_std"]):
        base_line = max(2.5, round(mean - 0.5) + 0.5)
        thresholds = [base_line, base_line + 1, base_line + 2]
        row_lines = []
        for t in thresholds:
            z = (t - mean) / std if std > 0 else 0
            row_lines.append({"line": t, "prob_over": round(max(1, min(99, norm_sf(z) * 100)), 1)})
        lines.append(row_lines)
    df["k_lines"] = lines

    return df


def main():
    batters = load_df("batter_features.parquet")
    pitchers = load_df("pitcher_features.parquet")

    scored_b = score_batters(batters)
    scored_p = score_pitchers(pitchers)

    save_df("batter_scores.parquet", scored_b)
    save_df("pitcher_scores.parquet", scored_p)
    print(f"scored batters={len(scored_b)}, pitchers={len(scored_p)}")
    print("top HR:", scored_b.sort_values("ali_score", ascending=False)[["name", "ali_score", "hr_probability"]].head(5).to_string())
    print("top K:", scored_p.sort_values("ali_score", ascending=False)[["name", "ali_score", "projected_k"]].head(5).to_string())


if __name__ == "__main__":
    main()
