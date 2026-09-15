#!/usr/bin/env bash
# Full daily pipeline refresh, in dependency order.
# fetch_recent_form.py is the slow step (~3-4 min): it pulls raw Statcast
# pitch-level data for the last 21 days and aggregates it, since Savant's
# player leaderboard endpoint only supports full-season filtering.
set -euo pipefail
cd "$(dirname "$0")/.."

DATE="${1:-$(date +%F)}"

python3 scripts/fetch_schedule.py "$DATE"
python3 scripts/fetch_batter_stats.py "$DATE"
python3 scripts/fetch_pitcher_stats.py "$DATE"
python3 scripts/fetch_recent_form.py "$DATE"
python3 scripts/build_features.py
python3 scripts/build_scores.py
python3 scripts/build_parlays.py
python3 scripts/build_site_data.py "$DATE"

echo "Pipeline complete for $DATE. site/data.json is ready to publish."
