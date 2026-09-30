"""Daily manual step (chat-only, not published): compare our HR board
against Venom Analytics' pasted lists (top-50, Viper Alert, Edge) to find
consensus picks, real coverage gaps, and one-sided calls worth a second look.

Venom has no API -- their lists get pasted into this file (or passed inline)
each morning, by hand.
"""
import sys
import unicodedata
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, "scripts")
from backtest import load_snapshot

DATE = "2026-09-30"

VENOM_TOP50 = [
    (1, "Munetaka Murakami"), (2, "Ben Rice"), (3, "Christian Walker"),
    (4, "Heliot Ramos"), (5, "Nelson Velázquez"), (6, "Michael Conforto"),
    (7, "Lucas Spence"), (8, "Spencer Jones"), (9, "Drake Baldwin"),
    (10, "Rowdy Tellez"), (11, "Fernando Tatis Jr."), (12, "George Lombard Jr."),
    (13, "Luis García Jr."), (14, "Yordan Alvarez"), (15, "Willson Contreras"),
    (16, "Austin Wells"), (17, "Otto Kemp"), (18, "Jeremy Peña"),
    (19, "Yainer Diaz"), (20, "Colson Montgomery"), (21, "Jazz Chisholm Jr."),
    (22, "Trent Grisham"), (23, "Kyle Teel"), (24, "Cam Smith"),
    (25, "Randal Grichuk"), (26, "Taylor Trammell"), (27, "Brenton Doyle"),
    (28, "Jackson Merrill"), (29, "Ronald Acuña Jr."), (30, "Miguel Amaya"),
    (31, "Matt Olson"), (32, "Jahmai Jones"), (33, "Michael Harris II"),
    (34, "Pete Crow-Armstrong"), (35, "Austin Riley"), (36, "Seiya Suzuki"),
    (37, "Kyle Schwarber"), (38, "Roman Anthony"), (39, "Paul Goldschmidt"),
    (40, "Amed Rosario"), (41, "Alex Bregman"), (42, "Gabriel Arias"),
    (43, "Derek Hill"), (44, "Wilyer Abreu"), (45, "Andrew Benintendi"),
    (46, "Jarren Duran"), (47, "Michael Busch"), (48, "Giancarlo Stanton"),
    (49, "Ryan McMahon"), (50, "Jake Cronenworth"),
]

VENOM_VIPER = [
    "Sean Murphy", "Wilyer Abreu", "Luis García Jr.", "Trent Grisham",
    "Paul Goldschmidt", "Amed Rosario", "Gabriel Arias", "Jarren Duran",
    "Jake Rogers",
]

VENOM_EDGE = [
    "Heliot Ramos", "Spencer Jones", "Lucas Spence", "Taylor Trammell",
    "Ben Rice", "Austin Wells", "Michael Conforto", "Derek Hill",
    "Jake Cronenworth", "Chase Meidroth", "Roman Anthony", "Andrew Benintendi",
    "Amed Rosario", "Drake Baldwin", "Kyle Teel", "Jarren Duran",
    "Munetaka Murakami", "Willson Contreras", "Ceddanne Rafaela", "Adley Rutschman",
]

OUR_TOP_N_FOR_CONSENSUS = 25
VENOM_TOP_N_FOR_CONSENSUS = 25


SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower().strip().rstrip(".")
    parts = name.split()
    if parts and parts[-1].rstrip(".") in SUFFIXES:
        parts = parts[:-1]
    return " ".join(parts)


def main():
    snapshot = load_snapshot(DATE)
    our_board = snapshot["rankings"]["home_run"]

    our_rank = {norm(p["name"]): (i + 1, p["hr_probability"], p.get("reason_tags", [])) for i, p in enumerate(our_board)}
    our_scored = dict(our_rank)
    for g in snapshot["games"]:
        for p in g["players"]["home_run"]:
            our_scored.setdefault(norm(p["name"]), (None, p["hr_probability"], p.get("reason_tags", [])))

    venom_rank = {norm(name): rank for rank, name in VENOM_TOP50}

    print(f"=== Consensus check for {DATE} ===\n")

    print(f"-- CONSENSUS: in both our top {OUR_TOP_N_FOR_CONSENSUS} and Venom's top {VENOM_TOP_N_FOR_CONSENSUS} --")
    consensus = []
    for rank, name in VENOM_TOP50:
        if rank > VENOM_TOP_N_FOR_CONSENSUS:
            continue
        info = our_rank.get(norm(name))
        if info and info[0] <= OUR_TOP_N_FOR_CONSENSUS:
            consensus.append((name, info[0], rank, info[1]))
    consensus.sort(key=lambda x: x[1] + x[2])
    for name, our_r, venom_r, pct in consensus:
        print(f"   {name:<24} our #{our_r:<4} venom #{venom_r:<4} our HR% {pct:.1f}%")
    print(f"   -> {len(consensus)} consensus picks\n")

    print(f"-- VENOM STRONG, WE'RE LOW/ABSENT: Venom top {VENOM_TOP_N_FOR_CONSENSUS}, outside our top 50 or unscored --")
    for rank, name in VENOM_TOP50:
        if rank > VENOM_TOP_N_FOR_CONSENSUS:
            continue
        info = our_rank.get(norm(name))
        scored_info = our_scored.get(norm(name))
        if info is None:
            if scored_info:
                print(f"   {name:<24} venom #{rank:<4} we scored {scored_info[1]:.1f}% but outside our top 50")
            else:
                print(f"   {name:<24} venom #{rank:<4} NOT SCORED BY US AT ALL")
    print()

    print(f"-- WE'RE STRONG, VENOM'S LOW/ABSENT: our top {OUR_TOP_N_FOR_CONSENSUS}, outside Venom's top 50 --")
    for i, p in enumerate(our_board[:OUR_TOP_N_FOR_CONSENSUS]):
        if norm(p["name"]) not in venom_rank:
            print(f"   {p['name']:<24} our #{i+1:<4} {p['hr_probability']:.1f}%  (not in Venom's top 50)")
    print()

    print("-- VIPER ALERT overlap --")
    our_viper_names = {norm(n) for n, (r, pct, tags) in our_scored.items() if "VIPER" in tags or "DUE" in tags}
    venom_viper_norm = {norm(n) for n in VENOM_VIPER}
    both = [n for n in VENOM_VIPER if norm(n) in our_viper_names]
    venom_only = [n for n in VENOM_VIPER if norm(n) not in our_viper_names]
    print(f"   Both flag as DUE/VIPER: {both or 'none'}")
    print(f"   Venom-only viper names: {venom_only}")
    print()

    print("-- VENOM EDGE (model beats market odds) x our board --")
    for name in VENOM_EDGE:
        info = our_rank.get(norm(name))
        if info:
            print(f"   {name:<24} our #{info[0]}, {info[1]:.1f}% -- also on OUR board (edge + our confirmation)")
        else:
            scored_info = our_scored.get(norm(name))
            note = f"scored {scored_info[1]:.1f}%, outside top 50" if scored_info else "not scored by us"
            print(f"   {name:<24} {note}")


if __name__ == "__main__":
    main()
