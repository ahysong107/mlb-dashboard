"""Static HR park-factor reference table (100 = league neutral).

Approximate multi-year Statcast/park-factor figures, keyed by the team
abbreviation MLB Stats API returns for each home team. These are season-level
constants, not refetched daily -- update by hand if a park is renovated or a
team relocates.
"""

HR_PARK_FACTOR = {
    "AZ": 106,
    "ATL": 103,
    "BAL": 95,
    "BOS": 96,
    "CHC": 100,
    "CWS": 108,
    "CIN": 114,
    "CLE": 97,
    "COL": 118,
    "DET": 92,
    "HOU": 104,
    "KC": 92,
    "LAA": 98,
    "LAD": 101,
    "MIA": 88,
    "MIL": 106,
    "MIN": 97,
    "NYM": 94,
    "NYY": 116,
    "ATH": 113,
    "PHI": 110,
    "PIT": 90,
    "SD": 92,
    "SF": 84,
    "SEA": 93,
    "STL": 91,
    "TB": 97,
    "TEX": 100,
    "TOR": 102,
    "WSH": 97,
}


def park_factor(team_abbrev):
    return HR_PARK_FACTOR.get(team_abbrev, 100)
