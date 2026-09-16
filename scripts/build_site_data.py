"""Assemble the final site/data.json: games with top HR/K boards, league-wide
rankings (with day-over-day rank-movement arrows), and system parlays.
"""
import datetime as dt
import json
import sys

from lib_data import load_df, load_json, save_json, ROOT, HISTORY_DIR

SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
MIN_PA_DISPLAY = 60
MIN_PA_PITCHER_DISPLAY = 20
TOP_N_PER_GAME = 8
TOP_N_RANKINGS = 50
HISTORY_LOOKBACK = 3
RETENTION_DAYS = 7


def r1(x):
    return None if x is None or (isinstance(x, float) and x != x) else round(float(x), 1)


def r3(x):
    return None if x is None or (isinstance(x, float) and x != x) else round(float(x), 3)


def batter_tags(row):
    tags = []
    if row.get("flag_due"):
        tags.append("DUE")
    if row.get("flag_viper"):
        tags.append("VIPER")
    if row.get("flag_overperforming"):
        tags.append("OVERPERFORMING")
    if row.get("lineup_source") == "projected":
        tags.append("Projected Lineup")
    return tags


def pitcher_tags(row):
    tags = []
    if row.get("flag_trending_up"):
        tags.append("TRENDING UP")
    if row.get("flag_overperforming"):
        tags.append("OVERPERFORMING")
    return tags


def batter_summary(row):
    era = row.get("opp_p_era")
    era_txt = f"(ERA {era:.2f})" if era is not None and era == era else ""
    park_note = ""
    if row.get("park_factor", 100) >= 108:
        park_note = f" at an HR-friendly park (factor {row['park_factor']:.0f})"
    elif row.get("park_factor", 100) <= 92:
        park_note = f" at a pitcher-friendly park (factor {row['park_factor']:.0f})"
    wind_note = ""
    if row.get("wind_dir") and "out" in str(row["wind_dir"]).lower():
        wind_note = f", wind {row['wind_dir'].lower()}"
    return f"{row['name']} faces {row['opp_pitcher_name']} {era_txt}{park_note}{wind_note}.".replace("  ", " ")


def pitcher_summary(row):
    opp_k = row.get("opp_lineup_k_pct_season")
    opp_txt = f"a lineup that strikes out {opp_k:.1f}% of the time" if opp_k == opp_k else "an average lineup"
    return f"{row['name']} ({row['b_k']:.1f}% K rate) faces {row['opponent']}, {opp_txt}."


def batter_to_dict(row):
    return {
        "player_id": int(row["player_id"]),
        "name": row["name"],
        "position": row.get("pos", ""),
        "team": row["team"],
        "opponent": row["opponent"],
        "is_home": bool(row["is_home"]),
        "order": int(row["order"]) if row["order"] == row["order"] else None,
        "ali_score": r1(row["ali_score"]),
        "hr_probability": r1(row["hr_probability"]),
        "baseline_score": r1(row["baseline_score"]),
        "opportunity_score": r1(row["opportunity_score"]),
        "hit_probability": r1(row["hit_probability"]),
        "tb2_probability": r1(row["tb2_probability"]),
        "barrel_pct": r1(row["b_barrel"]),
        "hard_hit_pct": r1(row["b_hardhit"]),
        "exit_velo": r1(row["exit_velocity_avg"]),
        "fb_pct": r1(row["b_fb"]),
        "hr_per_fb": r1(row["b_hrfb"]),
        "xslg": r3(row["xslg"]),
        "xba": r3(row["xba"]),
        "season_hr": int(row["home_run"]) if row["home_run"] == row["home_run"] else 0,
        "days_since_hr": None if row["days_since_hr"] != row["days_since_hr"] else int(row["days_since_hr"]),
        "pitch_matchup": r1(row["pitch_matchup_score"]),
        "park_factor": r1(row["park_factor"]),
        "wind_dir": row.get("wind_dir"),
        "temp": r1(row.get("temp")),
        "opp_pitcher_name": row.get("opp_pitcher_name"),
        "lineup_source": row.get("lineup_source"),
        "reason_tags": batter_tags(row),
        "summary": batter_summary(row),
        "__game_id": row["game_id"],
    }


def pitcher_to_dict(row):
    return {
        "player_id": int(row["player_id"]),
        "name": row["name"],
        "team": row["team"],
        "opponent": row["opponent"],
        "is_home": bool(row["is_home"]),
        "ali_score": r1(row["ali_score"]),
        "baseline_score": r1(row["baseline_score"]),
        "opportunity_score": r1(row["opportunity_score"]),
        "projected_k": r1(row["projected_k"]),
        "k_lines": [{"line": r1(l["line"]), "prob_over": r1(l["prob_over"])} for l in row["k_lines"]],
        "era": r1(row["p_era"]),
        "k_pct": r1(row["b_k"]),
        "whiff_pct": r1(row["b_whiff"]),
        "contact_against": r1(row["contact_against"]),
        "opp_lineup_k_pct": r1(row["opp_lineup_k_pct_season"]),
        "opp_lineup_ops": r1(row["opp_lineup_ops"]),
        "bf_estimate": r1(row["bf_estimate"]),
        "reason_tags": pitcher_tags(row),
        "summary": pitcher_summary(row),
        "__game_id": row["game_id"],
    }


def apply_rank_movement(items, category, today_str):
    ranked = sorted(items, key=lambda p: p["_sort_key"], reverse=True)
    today_ranks = {p["player_id"]: i + 1 for i, p in enumerate(ranked)}

    prev_ranks = None
    for back in range(1, HISTORY_LOOKBACK + 1):
        d = (dt.date.fromisoformat(today_str) - dt.timedelta(days=back)).isoformat()
        f = HISTORY_DIR / f"{d}.json"
        if f.exists():
            snap = json.loads(f.read_text())
            if category in snap:
                prev_ranks = snap[category]
                break

    for p in ranked:
        pid = str(p["player_id"])
        if prev_ranks is None:
            p["rank_arrow"] = None
        elif pid not in prev_ranks:
            p["rank_arrow"] = "new"
        else:
            delta = prev_ranks[pid] - today_ranks[p["player_id"]]
            p["rank_arrow"] = "up" if delta > 0 else ("down" if delta < 0 else "same")
    return ranked, today_ranks


def main(date_str):
    batters = load_df("batter_scores.parquet")
    pitchers = load_df("pitcher_scores.parquet")
    parlays = load_json("parlays.json")
    schedule = load_json("schedule.json")

    batters = batters[batters["pa"] >= MIN_PA_DISPLAY]
    pitchers = pitchers[pitchers["pa"] >= MIN_PA_PITCHER_DISPLAY]

    batter_dicts = [batter_to_dict(r) for _, r in batters.iterrows()]
    pitcher_dicts = [pitcher_to_dict(r) for _, r in pitchers.iterrows()]

    for p in batter_dicts:
        p["_sort_key"] = p["hr_probability"]
    for p in pitcher_dicts:
        p["_sort_key"] = p["projected_k"]

    hr_ranked, hr_ranks = apply_rank_movement(batter_dicts, "home_run", date_str)
    k_ranked, k_ranks = apply_rank_movement(pitcher_dicts, "strikeouts", date_str)

    HISTORY_DIR.mkdir(exist_ok=True)
    (HISTORY_DIR / f"{date_str}.json").write_text(json.dumps({
        "home_run": {str(k): v for k, v in hr_ranks.items()},
        "strikeouts": {str(k): v for k, v in k_ranks.items()},
    }))

    # Keyed by (game_id, team) so the per-team cap below can't let one side's
    # depth crowd the other side's own best hitters/pitchers off the card --
    # e.g. 5 Marlins batters outscoring every Diamondback would otherwise
    # bump Corbin Carroll off the game entirely even at a reasonable 16.7%.
    by_team_hr = {}
    for p in hr_ranked:
        by_team_hr.setdefault((p["__game_id"], p["team"]), []).append(p)
    by_team_k = {}
    for p in k_ranked:
        by_team_k.setdefault((p["__game_id"], p["team"]), []).append(p)

    games = []
    for g in schedule["games"]:
        gid = g["game_id"]
        hr_list = []
        k_list = []
        for team in (g["away_team"], g["home_team"]):
            hr_list += sorted(by_team_hr.get((gid, team), []), key=lambda p: p["_sort_key"], reverse=True)[:TOP_N_PER_GAME]
            k_list += sorted(by_team_k.get((gid, team), []), key=lambda p: p["_sort_key"], reverse=True)[:TOP_N_PER_GAME]
        hr_list.sort(key=lambda p: p["_sort_key"], reverse=True)
        k_list.sort(key=lambda p: p["_sort_key"], reverse=True)
        w = g.get("weather") or {}
        weather_line = None
        if w.get("temp") is not None:
            weather_line = f"{w['temp']:.0f}°F"
            if w.get("wind_dir"):
                weather_line += f" · {w['wind_dir']}"
        games.append({
            "game_id": gid,
            "away_team": g["away_team"],
            "home_team": g["home_team"],
            "venue": g["venue"],
            "game_time_utc": g["game_time_utc"],
            "lineup_source": g["lineup_source"],
            "away_probable": g["away_probable"]["name"] if g["away_probable"] else "TBD",
            "home_probable": g["home_probable"]["name"] if g["home_probable"] else "TBD",
            "weather_line": weather_line,
            "players": {"home_run": hr_list, "strikeouts": k_list},
        })

    rankings_hr = sorted(hr_ranked, key=lambda p: p["_sort_key"], reverse=True)[:TOP_N_RANKINGS]
    rankings_k = sorted(k_ranked, key=lambda p: p["_sort_key"], reverse=True)[:TOP_N_RANKINGS]

    # hr_ranked/k_ranked back every list above (games + rankings share the
    # same dict objects) -- safe to strip internal-only keys exactly once now.
    for p in hr_ranked + k_ranked:
        p.pop("_sort_key", None)
        p.pop("__game_id", None)

    data = {
        "date": date_str,
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "games": games,
        "rankings": {"home_run": rankings_hr, "strikeouts": rankings_k},
        "parlays": parlays,
    }

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DATA_DIR / f"{date_str}.json").write_text(json.dumps(data))

    kept_dates, removed_dates = prune_and_index(date_str)
    save_json("pruned_dates.json", removed_dates)

    print(f"Wrote site/data/{date_str}.json: {len(games)} games, {len(rankings_hr)} HR-ranked, {len(rankings_k)} K-ranked")
    print(f"Rolling window now has {len(kept_dates)} day(s): {kept_dates}")
    if removed_dates:
        print(f"Expired (>{RETENTION_DAYS} days old, removed locally -- also strip these from the published artifact's files): {removed_dates}")


def prune_and_index(today_str):
    """Keep only the trailing RETENTION_DAYS snapshots under site/data/,
    delete anything older from disk, and write site/dates.json listing what
    remains (newest first) so the front-end knows what it can offer."""
    cutoff = dt.date.fromisoformat(today_str) - dt.timedelta(days=RETENTION_DAYS - 1)
    kept, removed = [], []
    for f in SITE_DATA_DIR.glob("*.json"):
        try:
            d = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < cutoff:
            f.unlink()
            removed.append(f.stem)
        else:
            kept.append(f.stem)
    kept.sort(reverse=True)
    (SITE_DIR / "dates.json").write_text(json.dumps(kept))
    return kept, sorted(removed, reverse=True)


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    main(date_str)
