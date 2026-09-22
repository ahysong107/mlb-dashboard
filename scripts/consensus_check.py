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

DATE = "2026-09-22"

VENOM_TOP50 = [
    (1, "Elly De La Cruz"), (2, "Jackson Merrill"), (3, "Pete Alonso"),
    (4, "Pete Crow-Armstrong"), (5, "Coby Mayo"), (6, "Luis García Jr."),
    (7, "Corbin Carroll"), (8, "Fernando Tatis Jr."), (9, "Victor Mesa Jr."),
    (10, "Ronald Acuña Jr."), (11, "Spencer Jones"), (12, "Zack Gelof"),
    (13, "Riley Greene"), (15, "Jake Bauers"), (16, "Brandon Lowe"),
    (17, "Emmanuel Rodriguez"), (18, "Vinnie Pasquantino"), (19, "Kyle Tucker"),
    (20, "Brett Callahan"), (22, "Munetaka Murakami"), (23, "Matt Olson"),
    (24, "Junior Caminero"), (25, "Carter Jensen"), (26, "William Contreras"),
    (27, "Gunnar Henderson"), (28, "Eduardo Valencia"), (30, "Drake Baldwin"),
    (31, "Eugenio Suárez"), (32, "Josh Jung"), (33, "Jake Burger"),
    (34, "Kyle Stowers"), (35, "Joc Pederson"), (36, "Ben Rice"),
    (37, "Rafael Flores Jr."), (38, "Kazuma Okamoto"), (39, "Leo Bernal"),
    (40, "Shea Langeliers"), (41, "Randy Arozarena"), (42, "Francisco Alvarez"),
    (43, "Max Muncy"), (44, "Wilyer Abreu"), (45, "Jac Caglianone"),
    (46, "Mike Trout"), (47, "Cal Raleigh"), (48, "Daylen Lile"),
    (49, "Austin Wells"), (50, "Kyle Schwarber"),
]

VENOM_VIPER = [
    "Jordan Walker", "Thomas Saggese", "Kyle Stowers", "Brett Callahan",
    "Alec Bohm", "Braden Montgomery", "Matt McLain", "Tyler Stephenson",
    "Bryan Reynolds", "Eduardo Valencia", "Jac Caglianone", "Colton Cowser",
    "Justin Foscue", "Jesús Sánchez", "Kyle Teel", "Colson Montgomery",
    "Gabriel Arias", "Amed Rosario", "Brady House", "Mickey Moniak",
    "Zac Veen", "Abimelec Ortiz", "Andrew Benintendi", "José Tena",
    "Ryan Jeffers", "Max Schuemann", "Jake Rogers",
]

VENOM_EDGE = [
    "Victor Mesa Jr.", "Vinnie Pasquantino", "Emmanuel Rodriguez",
    "Spencer Jones", "Carter Jensen", "Luis García Jr.", "Ian Happ",
    "Bryan Reynolds", "Thomas Saggese", "Rafael Flores Jr.",
    "Jonathan Aranda", "Brice Turang", "Pete Crow-Armstrong", "Kyle Stowers",
    "Brandon Lowe", "Michael Conforto",
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
