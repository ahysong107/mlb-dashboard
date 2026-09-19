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

DATE = "2026-09-19"

VENOM_TOP50 = [
    (1, "Pete Crow-Armstrong"), (2, "Elly De La Cruz"), (3, "Jackson Merrill"),
    (4, "Coby Mayo"), (5, "Luis García Jr."), (6, "Seiya Suzuki"),
    (7, "Kazuma Okamoto"), (8, "Kyle Tucker"), (9, "Mookie Betts"),
    (10, "Teoscar Hernández"), (11, "Yordan Alvarez"), (12, "Eugenio Suárez"),
    (13, "Pete Alonso"), (14, "Munetaka Murakami"), (15, "Max Muncy"),
    (16, "Alec Burleson"), (17, "Will Smith"), (18, "Aaron Judge"),
    (19, "Connor Norby"), (20, "Riley Greene"), (21, "Ian Happ"),
    (22, "Corbin Carroll"), (23, "Randy Arozarena"), (24, "Jake Bauers"),
    (25, "Cal Raleigh"), (26, "Ben Rice"), (27, "Wilyer Abreu"),
    (28, "William Contreras"), (29, "Matt Olson"), (30, "Mike Trout"),
    (31, "Nathaniel Lowe"), (32, "Garrett Mitchell"), (33, "Dominic Canzone"),
    (34, "Brett Baty"), (35, "Henry Bolte"), (36, "Juan Soto"),
    (37, "Nelson Velázquez"), (38, "Colson Montgomery"), (39, "Kyle Teel"),
    (40, "Francisco Alvarez"), (41, "Moisés Ballesteros"), (42, "Kyle Stowers"),
    (43, "Zac Veen"), (44, "Victor Mesa Jr."), (45, "Vinnie Pasquantino"),
    (46, "Carter Jensen"), (47, "Jake Burger"), (48, "Eduardo Valencia"),
    (49, "Jo Adell"), (50, "Gabriel Arias"),
]

VENOM_VIPER = [
    "Jordan Walker", "Eduardo Valencia", "Tyler Stephenson", "Jake McCarthy",
    "Kyle Stowers", "Seiya Suzuki", "Wilyer Abreu", "Salvador Perez",
    "Connor Norby", "Colson Montgomery", "Zac Veen", "Gabriel Arias",
    "Bryan Reynolds", "Jac Caglianone", "Justin Foscue", "Victor Bericoto",
    "Colton Cowser", "Brett Callahan", "Andrew Benintendi", "Amed Rosario",
    "Brady House", "Abimelec Ortiz", "Jake Rogers", "José Tena",
    "Jesús Sánchez", "Davis Schneider",
]

VENOM_EDGE = [
    "Garrett Mitchell", "Alec Burleson", "Luis García Jr.", "Jackson Merrill",
    "Josh Jung", "Henry Bolte", "Kyle Teel", "Kyle Karros", "Brett Baty",
    "Victor Mesa Jr.", "Rafael Flores Jr.", "Moisés Ballesteros",
    "Connor Norby", "Brice Turang", "Corbin Carroll", "Bryan Reynolds",
    "Anthony Volpe", "Jeremiah Jackson", "Jac Caglianone", "Leo Bernal",
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
