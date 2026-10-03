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

DATE = "2026-10-03"

VENOM_TOP50 = [
    (1, "Shohei Ohtani"), (2, "Munetaka Murakami"), (3, "Jake Bauers"),
    (4, "Max Muncy"), (5, "Rowdy Tellez"), (6, "Andy Pages"),
    (7, "Drake Baldwin"), (8, "Michael Harris II"), (9, "Will Smith"),
    (10, "Teoscar Hernández"), (11, "Ronald Acuña Jr."), (12, "Jackson Merrill"),
    (13, "Austin Riley"), (14, "Fernando Tatis Jr."), (15, "Junior Caminero"),
    (16, "Jackson Chourio"), (17, "Garrett Mitchell"), (18, "Matt Olson"),
    (19, "Spencer Jones"), (20, "Miguel Vargas"), (21, "Dalton Rushing"),
    (22, "Freddie Freeman"), (23, "CJ Kayfus"), (24, "Enrique Hernández"),
    (25, "Jo Adell"), (26, "Colson Montgomery"), (27, "Jonathan Aranda"),
    (28, "Luis García Jr."), (29, "Ben Rice"), (30, "Kyle Teel"),
    (31, "Randal Grichuk"), (32, "Hunter Feduccia"), (33, "Victor Mesa Jr."),
    (34, "Bo Naylor"), (35, "Sean Murphy"), (36, "Austin Wells"),
    (37, "Nathaniel Lowe"), (38, "Mookie Betts"), (39, "William Contreras"),
    (40, "Brice Turang"), (41, "Heliot Ramos"), (42, "Christian Yelich"),
    (43, "Patrick Bailey"), (44, "Mike Yastrzemski"), (45, "Daniel Schneemann"),
    (46, "Andrew Benintendi"), (47, "Miguel Rojas"), (48, "Gary Sánchez"),
    (49, "Tommy Edman"), (50, "Dominic Smith"),
]

VENOM_VIPER = [
    "Jake Bauers", "Garrett Mitchell", "Shohei Ohtani", "Michael Harris II",
    "Freddie Freeman", "Colson Montgomery", "Luis García Jr.", "Sean Murphy",
    "Nathaniel Lowe", "Paul Goldschmidt", "Jake Rogers", "Amed Rosario",
    "Trent Grisham",
]

VENOM_EDGE = [
    "Michael Harris II", "Drake Baldwin", "Kyle Teel", "Garrett Mitchell",
    "Munetaka Murakami", "Andy Pages", "Jackson Merrill", "Patrick Bailey",
    "Nathaniel Lowe", "Christian Yelich", "Austin Wells", "Max Muncy",
    "Jake Bauers", "Austin Riley", "Chase Meidroth", "Jonathan Aranda",
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
