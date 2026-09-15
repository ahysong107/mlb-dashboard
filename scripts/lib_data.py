"""Shared HTTP + data-source helpers for the MLB dashboard pipeline.

Real data only: MLB Stats API (schedule/lineups/weather/probable pitchers/
team stats) and Baseball Savant's Statcast custom leaderboard CSV export.
Both are free and public, no API key required.
"""
import io
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = ROOT / "history"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

STATSAPI = "https://statsapi.mlb.com/api/v1"
SAVANT_LEADERBOARD = "https://baseballsavant.mlb.com/leaderboard/custom"

_session = requests.Session()
_session.headers.update({"User-Agent": "mlb-dashboard/1.0 (personal analytics project)"})


def _get(url, params=None, retries=3, timeout=30):
    last_err = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def statsapi_get(path, params=None):
    r = _get(f"{STATSAPI}{path}", params=params)
    return r.json()


BATTER_SELECTIONS = (
    "home_run,hit,b_total_bases,batting_avg,slg_percent,on_base_plus_slg,"
    "woba,xwoba,xba,xslg,barrel_batted_rate,hard_hit_percent,exit_velocity_avg,"
    "sweet_spot_percent,flyballs_percent,groundballs_percent,linedrives_percent,"
    "pull_percent,whiff_percent,k_percent,bb_percent,ab,pa"
)

PITCHER_SELECTIONS = (
    "p_era,k_percent,bb_percent,whiff_percent,barrel_batted_rate,hard_hit_percent,"
    "xslg,xwoba,woba,exit_velocity_avg,home_run,flyballs_percent,pitches,pa"
)


def fetch_savant_leaderboard(player_type, start_date, end_date, year, min_events=1):
    """Pull a Statcast custom leaderboard CSV for a date range. player_type: 'batter'|'pitcher'."""
    selections = BATTER_SELECTIONS if player_type == "batter" else PITCHER_SELECTIONS
    params = {
        "year": year,
        "type": player_type,
        "min": min_events,
        "selections": selections,
        "startDate": start_date,
        "endDate": end_date,
        "sort": "4",
        "sortDir": "desc",
        "csv": "true",
    }
    r = _get(SAVANT_LEADERBOARD, params=params)
    df = pd.read_csv(io.StringIO(r.text))
    df = df.rename(columns={"last_name, first_name": "savant_name"})
    numeric_cols = [c for c in df.columns if c not in ("savant_name", "player_id", "year")]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def cache_path(name):
    return DATA_DIR / name


def save_json(name, obj):
    with open(cache_path(name), "w") as f:
        json.dump(obj, f)


def load_json(name, default=None):
    p = cache_path(name)
    if not p.exists():
        return default
    with open(p) as f:
        return json.load(f)


def save_df(name, df):
    df.to_parquet(cache_path(name), index=False)


def load_df(name):
    return pd.read_parquet(cache_path(name))
