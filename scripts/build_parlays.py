"""Build Safe / Standard / Bold system parlays from the scored batter and
pitcher legs. Combined probabilities assume independence between legs (a
simplification -- same-game legs are usually correlated in reality, and
we say so in the site footer, same as the NFL dashboard).
"""
from lib_data import load_df, save_json

MIN_SEASON_PA = 120
MIN_SEASON_PA_PITCHER = 40


def fair_odds(p):
    p = max(0.01, min(0.99, p))
    if p >= 0.5:
        val = -100 * p / (1 - p)
        return f"{val:.0f}"
    val = 100 * (1 - p) / p
    return f"+{val:.0f}"


def build_legs_pool():
    b = load_df("batter_scores.parquet")
    p = load_df("pitcher_scores.parquet")
    b = b[b["pa"] >= MIN_SEASON_PA]
    p = p[p["pa"] >= MIN_SEASON_PA_PITCHER]

    legs = []
    for _, r in b.iterrows():
        legs.append({
            "type": "hr", "player": r["name"], "team": r["team"], "game_id": r["game_id"],
            "game_label": r["game_label"], "description": f"{r['name']} - Anytime Home Run",
            "prob": r["hr_probability"] / 100, "tag": "DUE" if r["flag_due"] else ("VIPER" if r["flag_viper"] else None),
        })
        legs.append({
            "type": "hit", "player": r["name"], "team": r["team"], "game_id": r["game_id"],
            "game_label": r["game_label"], "description": f"{r['name']} - 1+ Hits",
            "prob": r["hit_probability"] / 100, "tag": None,
        })
        legs.append({
            "type": "tb", "player": r["name"], "team": r["team"], "game_id": r["game_id"],
            "game_label": r["game_label"], "description": f"{r['name']} - 2+ Total Bases",
            "prob": r["tb2_probability"] / 100, "tag": None,
        })
    for _, r in p.iterrows():
        for i, l in enumerate(r["k_lines"]):
            legs.append({
                "type": "k", "player": r["name"], "team": r["team"], "game_id": r["game_id"],
                "game_label": r["game_label"], "description": f"{r['name']} - Over {l['line']} Strikeouts",
                "prob": l["prob_over"] / 100, "tag": "line" + str(i), "line_idx": i,
            })
    return legs


def build_cards(pool, lo, hi, n_legs, n_cards, prefer_tags=None, max_per_type=None):
    qualifying = [leg for leg in pool if lo <= leg["prob"] < hi]
    if prefer_tags:
        qualifying.sort(key=lambda x: (x.get("tag") not in prefer_tags, -x["prob"]))
    else:
        qualifying.sort(key=lambda x: -x["prob"])

    max_per_type = max_per_type or n_legs

    cards = []
    used_players = set()
    i = 0
    while len(cards) < n_cards and i < len(qualifying):
        card_legs = []
        used_games = set()
        type_counts = {}
        j = i
        while j < len(qualifying) and len(card_legs) < n_legs:
            leg = qualifying[j]
            key = (leg["player"], leg["type"], leg.get("line_idx"))
            if (
                leg["game_id"] not in used_games
                and key not in used_players
                and type_counts.get(leg["type"], 0) < max_per_type
            ):
                card_legs.append(leg)
                used_games.add(leg["game_id"])
                type_counts[leg["type"]] = type_counts.get(leg["type"], 0) + 1
            j += 1
        if len(card_legs) == n_legs:
            for leg in card_legs:
                used_players.add((leg["player"], leg["type"], leg.get("line_idx")))
            combined = 1.0
            for leg in card_legs:
                combined *= leg["prob"]
            cards.append({
                "legs": [{
                    "description": leg["description"], "team": leg["team"],
                    "game_label": leg["game_label"], "prob": round(leg["prob"], 3),
                } for leg in card_legs],
                "combined_prob": round(combined * 100, 1),
                "fair_odds": fair_odds(combined),
                "same_game": len(used_games) < len(card_legs),
            })
        i += 1
    return cards


def main():
    pool = build_legs_pool()

    safe = build_cards(pool, 0.60, 1.01, n_legs=2, n_cards=3, max_per_type=1)
    standard = build_cards(pool, 0.35, 0.65, n_legs=3, n_cards=3, max_per_type=2)
    bold = build_cards(pool, 0.10, 0.35, n_legs=3, n_cards=3, prefer_tags={"DUE", "VIPER"}, max_per_type=2)

    parlays = {"safe": safe, "standard": standard, "bold": bold}
    save_json("parlays.json", parlays)
    print(f"safe={len(safe)}, standard={len(standard)}, bold={len(bold)}")


if __name__ == "__main__":
    main()
