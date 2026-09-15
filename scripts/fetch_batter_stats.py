"""Pull season-long batter Statcast leaderboards from Baseball Savant.

Note: Savant's "custom leaderboard" endpoint only supports a `year` filter,
not arbitrary date ranges (verified against the live site) -- it silently
ignores startDate/endDate and returns full-season totals regardless. Rolling
recent-form windows are computed separately in fetch_recent_form.py from raw
Statcast pitch-level data, which does support real date filtering.
"""
import datetime as dt
import sys

from lib_data import fetch_savant_leaderboard, save_df

SEASON_START = "-03-01"


def fetch_all(as_of_date):
    as_of = dt.date.fromisoformat(as_of_date)
    yesterday = as_of - dt.timedelta(days=1)
    year = as_of.year
    season_start = dt.date.fromisoformat(f"{year}{SEASON_START}")

    season = fetch_savant_leaderboard("batter", season_start.isoformat(), yesterday.isoformat(), year, min_events=30)
    save_df("batter_season.parquet", season)
    return season


if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    season = fetch_all(as_of)
    print(f"season={len(season)} rows")
