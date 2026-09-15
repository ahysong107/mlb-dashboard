"""Pull season-long pitcher Statcast leaderboards and, for the opposing-lineup
side of the strikeout Opportunity Score, each team's season and rolling
14-day team strikeout rate (team endpoint genuinely supports date ranges,
unlike the player custom-leaderboard endpoint -- see fetch_batter_stats.py).
"""
import datetime as dt
import sys

from lib_data import fetch_savant_leaderboard, statsapi_get, save_df, save_json

SEASON_START = "-03-01"

TEAM_IDS = {
    "AZ": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112, "CWS": 145,
    "CIN": 113, "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118,
    "LAA": 108, "LAD": 119, "MIA": 146, "MIL": 158, "MIN": 142, "NYM": 121,
    "NYY": 147, "ATH": 133, "PHI": 143, "PIT": 134, "SD": 135, "SF": 137,
    "SEA": 136, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "WSH": 120,
}


def fetch_team_hitting(team_abbrev, team_id, season, d14_start, d14_end):
    season_stat = statsapi_get(
        f"/teams/{team_id}/stats",
        params={"stats": "season", "group": "hitting", "season": season},
    )["stats"][0]["splits"][0]["stat"]
    try:
        recent_stat = statsapi_get(
            f"/teams/{team_id}/stats",
            params={"stats": "byDateRange", "group": "hitting", "startDate": d14_start, "endDate": d14_end, "season": season},
        )["stats"][0]["splits"][0]["stat"]
    except (KeyError, IndexError):
        recent_stat = season_stat

    def k_pct(stat):
        pa = stat.get("plateAppearances") or 0
        k = stat.get("strikeOuts") or 0
        return (k / pa * 100) if pa else None

    return {
        "team": team_abbrev,
        "season_k_pct": k_pct(season_stat),
        "recent_k_pct": k_pct(recent_stat),
        "season_ops": float(season_stat.get("ops") or 0),
    }


def fetch_all(as_of_date):
    as_of = dt.date.fromisoformat(as_of_date)
    yesterday = as_of - dt.timedelta(days=1)
    year = as_of.year
    season_start = dt.date.fromisoformat(f"{year}{SEASON_START}")
    d14_start = yesterday - dt.timedelta(days=13)

    season = fetch_savant_leaderboard("pitcher", season_start.isoformat(), yesterday.isoformat(), year, min_events=10)
    save_df("pitcher_season.parquet", season)

    team_hitting = [
        fetch_team_hitting(abbrev, tid, year, d14_start.isoformat(), yesterday.isoformat())
        for abbrev, tid in TEAM_IDS.items()
    ]
    save_json("team_hitting.json", team_hitting)
    return season, team_hitting


if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    season, team_hitting = fetch_all(as_of)
    print(f"season={len(season)} rows, teams={len(team_hitting)}")
