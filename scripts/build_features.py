"""Merge schedule + season Statcast + recent-form Statcast + park/weather
into one row per today's lineup batter and one row per today's probable
pitcher, each carrying its opposing pitcher/lineup context.
"""
import sys

import pandas as pd

from lib_data import load_json, load_df, save_df
from park_data import park_factor

MIN_SEASON_PA_BATTER = 40
MIN_SEASON_PA_PITCHER = 20


def wind_component(wind_dir, wind_mph):
    if not wind_dir or wind_mph is None:
        return 50.0
    d = wind_dir.lower()
    if "out" in d:
        return min(50 + wind_mph * 4.5, 96)
    if "in" in d:
        return max(50 - wind_mph * 4.0, 8)
    return 50.0


def temp_component(temp):
    if temp is None:
        return 50.0
    return max(20.0, min(80.0, 50 + (temp - 65) * 0.8))


def order_component(order):
    if order is None:
        return 50.0
    if order <= 2:
        return 82.0
    if order <= 5:
        return 62.0
    if order <= 7:
        return 45.0
    return 30.0


def game_label(row, side):
    if side == "batter":
        return f"{row['team']} {'vs' if row['is_home'] else '@'} {row['opponent']}"
    return f"{row['team']} {'vs' if row['is_home'] else '@'} {row['opponent']}"


def build():
    schedule = load_json("schedule.json")
    batter_season = load_df("batter_season.parquet").rename(columns={"player_id": "pid"})
    batter_recent = load_df("batter_recent.parquet").rename(columns={"player_id": "pid"})
    pitcher_season = load_df("pitcher_season.parquet").rename(columns={"player_id": "pid"})
    pitcher_recent = load_df("pitcher_recent.parquet").rename(columns={"player_id": "pid"})
    team_hitting = {t["team"]: t for t in load_json("team_hitting.json")}

    batter_season = batter_season[batter_season["pa"] >= MIN_SEASON_PA_BATTER]
    pitcher_season = pitcher_season[pitcher_season["pa"] >= MIN_SEASON_PA_PITCHER]

    pitcher_stats = pitcher_season.merge(pitcher_recent, on="pid", how="left")
    pitcher_lookup = pitcher_stats.set_index("pid").to_dict("index")

    batter_rows = []
    pitcher_rows = []

    for g in schedule["games"]:
        glabel_away = f"{g['away_team']} @ {g['home_team']}"
        park = park_factor(g["home_team"])
        weather = g.get("weather") or {}
        wind_mph, wind_dir, temp = weather.get("wind_mph"), weather.get("wind_dir"), weather.get("temp")

        sides = [
            ("away", g["away_team"], g["home_team"], False, g["away_lineup"], g["home_probable"]),
            ("home", g["home_team"], g["away_team"], True, g["home_lineup"], g["away_probable"]),
        ]
        for _, team, opp, is_home, lineup, opp_pitcher in sides:
            opp_p_stats = pitcher_lookup.get(opp_pitcher["id"]) if opp_pitcher else None
            for slot in lineup:
                batter_rows.append({
                    "player_id": slot["id"],
                    "name": slot["name"],
                    "pos": slot["pos"],
                    "order": slot["order"],
                    "team": team,
                    "opponent": opp,
                    "is_home": is_home,
                    "game_id": g["game_id"],
                    "game_label": glabel_away,
                    "game_time_utc": g["game_time_utc"],
                    "lineup_source": g["lineup_source"],
                    "park_factor": park,
                    "wind_mph": wind_mph,
                    "wind_dir": wind_dir,
                    "temp": temp,
                    "wind_score": wind_component(wind_dir, wind_mph),
                    "temp_score": temp_component(temp),
                    "order_score": order_component(slot["order"]),
                    "opp_pitcher_id": opp_pitcher["id"] if opp_pitcher else None,
                    "opp_pitcher_name": opp_pitcher["name"] if opp_pitcher else "TBD",
                    "opp_p_era": opp_p_stats.get("p_era") if opp_p_stats else None,
                    "opp_p_barrel_allowed": opp_p_stats.get("barrel_batted_rate") if opp_p_stats else None,
                    "opp_p_hardhit_allowed": opp_p_stats.get("hard_hit_percent") if opp_p_stats else None,
                    "opp_p_xslg_allowed": opp_p_stats.get("xslg") if opp_p_stats else None,
                    "opp_p_hr_allowed": opp_p_stats.get("home_run") if opp_p_stats else None,
                    "opp_p_recent_barrel_allowed": opp_p_stats.get("w21_barrel_pct_allowed") if opp_p_stats else None,
                    "opp_p_recent_hardhit_allowed": opp_p_stats.get("w21_hard_hit_pct_allowed") if opp_p_stats else None,
                })

            if opp_pitcher is None:
                continue
            opp_hitting = team_hitting.get(team, {})
            pitcher_rows.append({
                "player_id": opp_pitcher["id"],
                "name": opp_pitcher["name"],
                "team": opp,
                "opponent": team,
                "is_home": not is_home,
                "game_id": g["game_id"],
                "game_label": glabel_away,
                "game_time_utc": g["game_time_utc"],
                "park_factor": park,
                "opp_lineup_k_pct_season": opp_hitting.get("season_k_pct"),
                "opp_lineup_k_pct_recent": opp_hitting.get("recent_k_pct"),
                "opp_lineup_ops": opp_hitting.get("season_ops"),
            })

    batters = pd.DataFrame(batter_rows).drop_duplicates(subset=["player_id", "game_id"])
    pitchers_ctx = pd.DataFrame(pitcher_rows).drop_duplicates(subset=["player_id", "game_id"])

    batters = batters.merge(batter_season, left_on="player_id", right_on="pid", how="inner")
    batters = batters.merge(batter_recent, left_on="player_id", right_on="pid", how="left", suffixes=("", "_recent"))

    pitchers = pitchers_ctx.merge(pitcher_stats, left_on="player_id", right_on="pid", how="inner")

    save_df("batter_features.parquet", batters)
    save_df("pitcher_features.parquet", pitchers)
    return batters, pitchers


if __name__ == "__main__":
    batters, pitchers = build()
    print(f"batter_features={len(batters)} rows, pitcher_features={len(pitchers)} rows")
