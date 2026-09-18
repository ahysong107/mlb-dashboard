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

DATE = "2026-09-18"

VENOM_TOP50 = [
    (1, "Pete Crow-Armstrong"), (2, "Riley Greene"), (3, "Elly De La Cruz"),
    (4, "Kazuma Okamoto"), (5, "William Contreras"), (6, "Jackson Merrill"),
    (7, "Corbin Carroll"), (8, "Munetaka Murakami"), (9, "Yordan Alvarez"),
    (10, "Henry Bolte"), (11, "Luis García Jr."), (12, "Coby Mayo"),
    (13, "Nathaniel Lowe"), (14, "Eugenio Suárez"), (15, "Eduardo Valencia"),
    (16, "Kyle Schwarber"), (17, "Colson Montgomery"), (18, "Connor Norby"),
    (19, "Seiya Suzuki"), (20, "Max Muncy"), (21, "Teoscar Hernández"),
    (22, "Garrett Mitchell"), (23, "Lawrence Butler"), (24, "Mookie Betts"),
    (25, "Matt Olson"), (26, "Aaron Judge"), (27, "Kyle Tucker"),
    (28, "Nelson Velázquez"), (29, "Alec Burleson"), (30, "Brett Callahan"),
    (31, "Jake Bauers"), (32, "Bryce Eldridge"), (33, "Spencer Torkelson"),
    (34, "Cal Raleigh"), (35, "Kyle Teel"), (36, "Francisco Alvarez"),
    (37, "Ian Happ"), (38, "Jo Adell"), (39, "Pete Alonso"),
    (40, "Wilyer Abreu"), (41, "Bryan Reynolds"), (42, "Brett Baty"),
    (43, "Kevin McGonigle"), (44, "Dominic Canzone"), (45, "Ronald Acuña Jr."),
    (46, "Daylen Lile"), (47, "Tyler Stephenson"), (48, "Willson Contreras"),
    (49, "Randy Arozarena"), (50, "Fernando Tatis Jr."),
]

VENOM_VIPER = [
    "Jordan Walker", "Amed Rosario", "Tyler Stephenson", "Eduardo Valencia",
    "Kyle Stowers", "Connor Norby", "Brett Callahan", "Brady House",
    "Seiya Suzuki", "Ian Happ", "Jake McCarthy", "Ty France",
    "Colson Montgomery", "Colton Cowser", "Jac Caglianone", "Zac Veen",
    "Justin Foscue", "Gabriel Arias", "James Wood", "Jesús Sánchez",
    "Jake Rogers", "Davis Schneider", "Abimelec Ortiz", "José Tena",
]

VENOM_EDGE = [
    "Henry Bolte", "William Contreras", "Lawrence Butler", "Garrett Mitchell",
    "Nathaniel Lowe", "Josh Jung", "Jackson Merrill", "Patrick Bailey",
    "Grant McCray", "Colton Cowser", "Brice Turang", "Connor Norby",
    "Juan Brito", "Amed Rosario", "Alec Burleson", "Corbin Carroll",
    "Kyle Karros", "Brett Bateman", "Coby Mayo", "Riley Greene",
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
