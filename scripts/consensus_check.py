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

DATE = "2026-10-01"

# NOTE: Venom's list includes players from NYY/BOS and CHC/SD -- series that
# aren't playing today (user confirmed only ATL @ PHI is on today's actual
# schedule). Those entries are left in below for a complete comparison, but
# expect them to show as "not scored by us" simply because they're not
# playing today, not because of a real coverage gap -- don't read those as
# bugs the way earlier same-day gaps were.
VENOM_TOP50 = [
    (1, "Ben Rice"), (2, "Drake Baldwin"), (3, "Michael Conforto"),
    (4, "Wilyer Abreu"), (5, "Fernando Tatis Jr."), (6, "Spencer Jones"),
    (7, "Otto Kemp"), (8, "Willson Contreras"), (9, "Heliot Ramos"),
    (10, "Rowdy Tellez"), (11, "Jackson Merrill"), (12, "Austin Riley"),
    (13, "Michael Harris II"), (14, "George Lombard Jr."), (15, "Luis García Jr."),
    (16, "Derek Hill"), (17, "Ronald Acuña Jr."), (18, "Trent Grisham"),
    (19, "Jahmai Jones"), (20, "Jarren Duran"), (21, "Miguel Amaya"),
    (22, "Matt Olson"), (23, "Pete Crow-Armstrong"), (24, "Austin Wells"),
    (25, "Seiya Suzuki"), (26, "Alex Bregman"), (27, "Sean Murphy"),
    (28, "Gabriel Arias"), (29, "Michael Busch"), (30, "Amed Rosario"),
    (31, "Paul Goldschmidt"), (32, "Ceddanne Rafaela"), (33, "Giancarlo Stanton"),
    (34, "Jazz Chisholm Jr."), (35, "Gavin Sheets"), (36, "Jake Cronenworth"),
    (37, "Ian Happ"), (38, "Brandon Marsh"), (39, "Ryan McMahon"),
    (40, "Dominic Smith"), (41, "Luis Campusano"), (42, "Curtis Mead"),
    (43, "Alec Bohm"), (44, "Dansby Swanson"), (45, "Austin Hays"),
    (46, "Manny Machado"), (47, "Mike Yastrzemski"), (48, "Edmundo Sosa"),
    (49, "Mauricio Dubón"), (50, "Tyrone Taylor"),
]

VENOM_VIPER = [
    "Wilyer Abreu", "Trent Grisham", "Jarren Duran", "Sean Murphy",
    "Gabriel Arias", "Amed Rosario", "Paul Goldschmidt",
]

VENOM_EDGE = [
    "Derek Hill", "Drake Baldwin", "Jake Cronenworth", "Mauricio Dubón",
    "Jackson Merrill", "Austin Riley", "Sean Murphy", "Michael Harris II",
    "Justin Crawford",
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
