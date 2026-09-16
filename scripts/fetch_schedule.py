"""Fetch today's MLB slate: matchups, probable pitchers, lineups, weather.

Confirmed lineups usually post a few hours before first pitch. For games
that don't have one yet, we fall back to each team's most recent actual
batting order (looked back up to 6 days) and flag it as "projected" rather
than "confirmed" so the site can be honest about it.
"""
import datetime as dt
import sys
from collections import Counter

from lib_data import statsapi_get, save_json

LOOKBACK_DAYS = 6
FALLBACK_GAMES = 5  # majority-vote per batting slot across this many recent games


def _parse_lineup(players):
    return [
        {
            "id": p["id"],
            "name": p["fullName"],
            "order": i + 1,
            "pos": p.get("primaryPosition", {}).get("abbreviation", ""),
        }
        for i, p in enumerate(players)
    ]


def _fallback_lineup(team_id, before_date):
    """A single most-recent lineup is unreliable -- a regular starter who
    happened to sit (rest day, platoon matchup) the very last game would
    vanish entirely. Instead, majority-vote each batting-order slot across
    the last FALLBACK_GAMES games that had a posted lineup, so an every-day
    player's normal spot survives one-off absences.
    """
    end = dt.date.fromisoformat(before_date) - dt.timedelta(days=1)
    start = end - dt.timedelta(days=LOOKBACK_DAYS)
    data = statsapi_get(
        "/schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "hydrate": "lineups",
        },
    )
    recent_lineups = []
    for d in sorted(data.get("dates", []), key=lambda x: x["date"], reverse=True):
        for g in d["games"]:
            lineups = g.get("lineups", {})
            is_home = g["teams"]["home"]["team"]["id"] == team_id
            players = lineups.get("homePlayers" if is_home else "awayPlayers")
            if players:
                recent_lineups.append(players)
        if len(recent_lineups) >= FALLBACK_GAMES:
            break

    if not recent_lineups:
        return []
    if len(recent_lineups) == 1:
        return _parse_lineup(recent_lineups[0])

    composite = []
    max_slots = max(len(g) for g in recent_lineups)
    for slot in range(max_slots):
        candidates = [g[slot] for g in recent_lineups if len(g) > slot]
        if not candidates:
            continue
        best_id = Counter(p["id"] for p in candidates).most_common(1)[0][0]
        composite.append(next(p for p in candidates if p["id"] == best_id))
    return _parse_lineup(composite)


def fetch_schedule(date_str):
    data = statsapi_get(
        "/schedule",
        params={
            "sportId": 1,
            "date": date_str,
            "hydrate": "lineups,probablePitcher,venue,weather,team",
        },
    )
    games = []
    dates = data.get("dates", [])
    raw_games = dates[0]["games"] if dates else []

    for g in raw_games:
        if g.get("gameType") != "R" and g.get("gameType") != "F":
            # keep regular season + postseason, skip exhibitions etc if any leak in
            if g.get("gameType") not in ("R", "F", "D", "L", "W"):
                continue
        away = g["teams"]["away"]
        home = g["teams"]["home"]
        away_team = away["team"]
        home_team = home["team"]

        lineups = g.get("lineups", {})
        away_players = lineups.get("awayPlayers", [])
        home_players = lineups.get("homePlayers", [])
        lineup_source = "confirmed" if (away_players and home_players) else "none"

        away_lineup = _parse_lineup(away_players) if away_players else []
        home_lineup = _parse_lineup(home_players) if home_players else []

        if not away_lineup:
            fb = _fallback_lineup(away_team["id"], date_str)
            if fb:
                away_lineup = fb
                lineup_source = "projected" if lineup_source != "confirmed" else lineup_source
        if not home_lineup:
            fb = _fallback_lineup(home_team["id"], date_str)
            if fb:
                home_lineup = fb
                lineup_source = "projected" if lineup_source != "confirmed" else lineup_source

        if away_lineup and home_lineup and lineup_source == "none":
            lineup_source = "projected"

        weather = g.get("weather") or {}
        wind_raw = weather.get("wind")  # e.g. "6 mph, In From RF"
        wind_mph, wind_dir = None, None
        if wind_raw and "," in wind_raw:
            parts = wind_raw.split(",", 1)
            try:
                wind_mph = float(parts[0].strip().split(" ")[0])
            except ValueError:
                wind_mph = None
            wind_dir = parts[1].strip()

        temp = weather.get("temp")
        try:
            temp = float(temp) if temp is not None else None
        except ValueError:
            temp = None

        away_probable = away.get("probablePitcher")
        home_probable = home.get("probablePitcher")

        games.append({
            "game_id": str(g["gamePk"]),
            "game_time_utc": g.get("gameDate"),
            "venue": home_team.get("venue", {}).get("name", ""),
            "away_team": away_team.get("abbreviation"),
            "home_team": home_team.get("abbreviation"),
            "away_team_id": away_team.get("id"),
            "home_team_id": home_team.get("id"),
            "away_probable": {"id": away_probable["id"], "name": away_probable["fullName"]} if away_probable else None,
            "home_probable": {"id": home_probable["id"], "name": home_probable["fullName"]} if home_probable else None,
            "weather": {
                "condition": weather.get("condition"),
                "temp": temp,
                "wind_mph": wind_mph,
                "wind_dir": wind_dir,
            } if weather else None,
            "lineup_source": lineup_source,
            "away_lineup": away_lineup,
            "home_lineup": home_lineup,
        })

    return {"date": date_str, "games": games}


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    result = fetch_schedule(date_str)
    save_json("schedule.json", result)
    print(f"Fetched {len(result['games'])} games for {date_str}")
