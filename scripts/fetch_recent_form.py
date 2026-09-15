"""Pull raw Statcast pitch-level data for a rolling recent window and
aggregate it into per-batter and per-pitcher recent-form rates.

This is the source of truth for anything "recent" (rolling barrel%, hard-hit%,
trend, HR drought) because Baseball Savant's player leaderboard endpoint only
supports full-season filtering (see fetch_batter_stats.py) -- pitch-level
Statcast Search, by contrast, genuinely supports date-range filtering.
"""
import datetime as dt
import sys
import warnings

import pandas as pd

from lib_data import save_df

warnings.filterwarnings("ignore")

WINDOW_DAYS = 21
SPLIT_DAYS = 7

SWING_DESCRIPTIONS = {
    "foul", "foul_tip", "foul_bunt", "hit_into_play",
    "swinging_strike", "swinging_strike_blocked", "missed_bunt",
}
WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt"}


def _fetch_statcast(start, end):
    import pybaseball
    pybaseball.cache.enable()
    return pybaseball.statcast(start_dt=start, end_dt=end, verbose=False)


def _agg_batter(df, name):
    if df.empty:
        return pd.DataFrame()
    pa_rows = df[df["events"].notna()]
    bbe = df[df["bb_type"].notna()]
    swings = df[df["description"].isin(SWING_DESCRIPTIONS)]

    g_pa = pa_rows.groupby("batter")
    g_bbe = bbe.groupby("batter")
    g_sw = swings.groupby("batter")

    out = pd.DataFrame({
        "pa": g_pa.size(),
        "k": pa_rows.assign(_k=pa_rows["events"] == "strikeout").groupby("batter")["_k"].sum(),
        "bb": pa_rows.assign(_bb=pa_rows["events"] == "walk").groupby("batter")["_bb"].sum(),
        "hr": pa_rows.assign(_hr=pa_rows["events"] == "home_run").groupby("batter")["_hr"].sum(),
        "bbe": g_bbe.size(),
        "barrels": bbe.assign(_b=bbe["launch_speed_angle"] == 6).groupby("batter")["_b"].sum(),
        "hard_hit": bbe.assign(_h=bbe["launch_speed"] >= 95).groupby("batter")["_h"].sum(),
        "avg_ev": g_bbe["launch_speed"].mean(),
        "fly_balls": bbe.assign(_f=bbe["bb_type"] == "fly_ball").groupby("batter")["_f"].sum(),
        "xslg_bbe": g_bbe["estimated_slg_using_speedangle"].mean(),
        "swings": g_sw.size(),
        "whiffs": swings.assign(_w=swings["description"].isin(WHIFF_DESCRIPTIONS)).groupby("batter")["_w"].sum(),
    }).fillna(0)

    out["barrel_pct"] = (out["barrels"] / out["bbe"] * 100).where(out["bbe"] > 0)
    out["hard_hit_pct"] = (out["hard_hit"] / out["bbe"] * 100).where(out["bbe"] > 0)
    out["fb_pct"] = (out["fly_balls"] / out["bbe"] * 100).where(out["bbe"] > 0)
    out["hr_per_fb"] = (out["hr"] / out["fly_balls"] * 100).where(out["fly_balls"] > 0)
    out["k_pct"] = (out["k"] / out["pa"] * 100).where(out["pa"] > 0)
    out["bb_pct"] = (out["bb"] / out["pa"] * 100).where(out["pa"] > 0)
    out["whiff_pct"] = (out["whiffs"] / out["swings"] * 100).where(out["swings"] > 0)
    out.index.name = "player_id"
    return out.add_prefix(f"{name}_")


def _agg_pitcher(df, name):
    if df.empty:
        return pd.DataFrame()
    pa_rows = df[df["events"].notna()]
    bbe = df[df["bb_type"].notna()]
    swings = df[df["description"].isin(SWING_DESCRIPTIONS)]

    g_pa = pa_rows.groupby("pitcher")
    g_bbe = bbe.groupby("pitcher")
    g_sw = swings.groupby("pitcher")

    out = pd.DataFrame({
        "pa": g_pa.size(),
        "k": pa_rows.assign(_k=pa_rows["events"] == "strikeout").groupby("pitcher")["_k"].sum(),
        "bb": pa_rows.assign(_bb=pa_rows["events"] == "walk").groupby("pitcher")["_bb"].sum(),
        "hr_allowed": pa_rows.assign(_hr=pa_rows["events"] == "home_run").groupby("pitcher")["_hr"].sum(),
        "bbe": g_bbe.size(),
        "barrels_allowed": bbe.assign(_b=bbe["launch_speed_angle"] == 6).groupby("pitcher")["_b"].sum(),
        "hard_hit_allowed": bbe.assign(_h=bbe["launch_speed"] >= 95).groupby("pitcher")["_h"].sum(),
        "xslg_allowed_bbe": g_bbe["estimated_slg_using_speedangle"].mean(),
        "swings": g_sw.size(),
        "whiffs": swings.assign(_w=swings["description"].isin(WHIFF_DESCRIPTIONS)).groupby("pitcher")["_w"].sum(),
    }).fillna(0)

    out["k_pct"] = (out["k"] / out["pa"] * 100).where(out["pa"] > 0)
    out["bb_pct"] = (out["bb"] / out["pa"] * 100).where(out["pa"] > 0)
    out["whiff_pct"] = (out["whiffs"] / out["swings"] * 100).where(out["swings"] > 0)
    out["barrel_pct_allowed"] = (out["barrels_allowed"] / out["bbe"] * 100).where(out["bbe"] > 0)
    out["hard_hit_pct_allowed"] = (out["hard_hit_allowed"] / out["bbe"] * 100).where(out["bbe"] > 0)
    out.index.name = "player_id"
    return out.add_prefix(f"{name}_")


def fetch_all(as_of_date):
    as_of = dt.date.fromisoformat(as_of_date)
    yesterday = as_of - dt.timedelta(days=1)
    window_start = yesterday - dt.timedelta(days=WINDOW_DAYS - 1)
    split_point = yesterday - dt.timedelta(days=SPLIT_DAYS - 1)
    prior_start = split_point - dt.timedelta(days=SPLIT_DAYS)
    prior_end = split_point - dt.timedelta(days=1)

    raw = _fetch_statcast(window_start.isoformat(), yesterday.isoformat())
    raw["game_date"] = pd.to_datetime(raw["game_date"]).dt.date

    last7 = raw[raw["game_date"] >= split_point]
    prior7 = raw[(raw["game_date"] >= prior_start) & (raw["game_date"] <= prior_end)]

    # batters
    full_b = _agg_batter(raw, "w21")
    last7_b = _agg_batter(last7, "last7")
    prior7_b = _agg_batter(prior7, "prior7")

    hr_events = raw[raw["events"] == "home_run"]
    last_hr = hr_events.groupby("batter")["game_date"].max().rename("last_hr_date")

    batters = full_b.join(last7_b, how="outer").join(prior7_b, how="outer").join(last_hr, how="left")
    batters["days_since_hr"] = batters["last_hr_date"].apply(
        lambda d: (yesterday - d).days if pd.notna(d) else None
    ).astype("float64")
    batters["last_hr_date"] = batters["last_hr_date"].apply(lambda d: d.isoformat() if pd.notna(d) else None)
    batters = batters.reset_index()

    # pitchers
    full_p = _agg_pitcher(raw, "w21")
    last7_p = _agg_pitcher(last7, "last7")
    pitchers = full_p.join(last7_p, how="outer").reset_index()

    save_df("batter_recent.parquet", batters)
    save_df("pitcher_recent.parquet", pitchers)
    return batters, pitchers


if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    batters, pitchers = fetch_all(as_of)
    print(f"recent-form: batters={len(batters)}, pitchers={len(pitchers)}")
