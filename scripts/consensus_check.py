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

DATE = "2026-09-16"

VENOM_TOP50 = [
    (1, "Riley Greene"), (2, "Jackson Merrill"), (3, "Luis García Jr."),
    (4, "Pete Crow-Armstrong"), (5, "Corbin Carroll"), (6, "Elly De La Cruz"),
    (7, "Aaron Judge"), (8, "Fernando Tatis Jr."), (9, "Pete Alonso"),
    (10, "Carter Jensen"), (11, "Kazuma Okamoto"), (12, "Teoscar Hernández"),
    (13, "Brett Callahan"), (14, "Eugenio Suárez"), (15, "Jac Caglianone"),
    (16, "Ty France"), (17, "Vinnie Pasquantino"), (18, "Bryan Reynolds"),
    (19, "Eduardo Valencia"), (20, "Griffin Conine"), (21, "Ben Rice"),
    (22, "Max Muncy"), (23, "Connor Norby"), (24, "Munetaka Murakami"),
    (25, "Kyle Tucker"), (26, "Matt Olson"), (27, "Kyle Schwarber"),
    (28, "Manny Machado"), (29, "Bobby Witt Jr."), (30, "Coby Mayo"),
    (31, "Seiya Suzuki"), (32, "Kyle Stowers"), (33, "Junior Caminero"),
    (34, "Roman Anthony"), (35, "Ian Happ"), (36, "Corey Seager"),
    (37, "Heliot Ramos"), (38, "Mookie Betts"), (39, "Daylen Lile"),
    (40, "William Contreras"), (41, "Heriberto Hernández"), (42, "Spencer Torkelson"),
    (43, "Cal Raleigh"), (44, "Josh Bell"), (45, "Austin Riley"),
    (46, "Bryce Eldridge"), (47, "Spencer Jones"), (48, "Alec Burleson"),
    (49, "Wilyer Abreu"), (50, "Ronald Acuña Jr."),
]

VENOM_VIPER = [
    "Amed Rosario", "Brett Callahan", "Ty France", "Seiya Suzuki",
    "Eduardo Valencia", "Ian Happ", "Jac Caglianone", "Willson Contreras",
    "James Wood", "Zac Veen", "Justin Foscue", "Gabriel Arias",
    "Samuel Basallo", "Colton Cowser", "Jesús Sánchez", "Andrew Benintendi",
    "José Tena", "Brandon Marsh", "Abimelec Ortiz", "Nate Eaton", "Davis Schneider",
]

VENOM_EDGE = [
    "Luis García Jr.", "Elly De La Cruz", "Eugenio Suárez", "Bryan Reynolds",
    "Javier Sanoja", "Grant McCray", "Connor Norby", "Nick Sogard",
    "Corbin Carroll", "Seiya Suzuki", "Luis Torrens", "Ian Happ", "Ty France",
    "Brett Harris", "Josh Bell", "Kyle Tucker", "Pete Crow-Armstrong",
    "William Contreras", "Jackson Merrill", "Michael Busch",
]

OUR_TOP_N_FOR_CONSENSUS = 25
VENOM_TOP_N_FOR_CONSENSUS = 25


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return name.lower().strip()


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
