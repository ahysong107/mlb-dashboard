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

DATE = "2026-09-25"

VENOM_TOP50 = [
    (1, "Pete Alonso"), (2, "Munetaka Murakami"), (3, "Ben Rice"),
    (4, "Brandon Lowe"), (6, "Yordan Alvarez"), (7, "Coby Mayo"),
    (8, "Gunnar Henderson"), (10, "Elly De La Cruz"), (13, "Spencer Jones"),
    (14, "Yohandy Morales"), (15, "Jake Bauers"), (16, "Ronald Acuña Jr."),
    (17, "Colton Cowser"), (18, "Mike Trout"), (20, "Emmanuel Rodriguez"),
    (21, "Thomas Saggese"), (22, "Francisco Alvarez"), (23, "Corbin Carroll"),
    (24, "Shohei Ohtani"), (25, "Iván Herrera"), (26, "Dylan Beavers"),
    (27, "Pete Crow-Armstrong"), (30, "Michael Conforto"), (31, "Kyle Teel"),
    (32, "Vinnie Pasquantino"), (33, "Colson Montgomery"), (34, "Jeremy Peña"),
    (35, "Kyle Stowers"), (36, "Nelson Velázquez"), (37, "Jeremiah Jackson"),
    (38, "Eugenio Suárez"), (40, "Jonathan Aranda"), (41, "Jordan Walker"),
    (42, "Fernando Tatis Jr."), (43, "Randy Arozarena"), (44, "Wilyer Abreu"),
    (45, "Amed Rosario"), (46, "Paul Goldschmidt"), (47, "Christian Encarnacion-Strand"),
    (48, "Jackson Merrill"), (49, "Riley Greene"), (50, "Kazuma Okamoto"),
]

VENOM_VIPER = [
    "Shohei Ohtani", "Thomas Saggese", "Jordan Walker", "Wilyer Abreu",
    "Jesús Sánchez", "Freddie Freeman", "Brett Callahan", "Francisco Lindor",
    "Eduardo Valencia", "Jac Caglianone", "Alec Bohm", "Dominic Canzone",
    "Kevin McGonigle", "Colton Cowser", "Colson Montgomery", "Amed Rosario",
    "Brady House", "Andrew Benintendi", "Tyler Stephenson", "Justin Foscue",
    "Nolan Gorman", "Gabriel Arias", "Jarren Duran", "José Tena",
    "Ryan Jeffers", "Matt McLain", "Jake Rogers",
]

VENOM_EDGE = [
    "Jonathan Aranda", "Brady House", "Elly De La Cruz", "Emmanuel Rodriguez",
    "Francisco Alvarez", "Vinnie Pasquantino", "Ian Happ", "Brandon Lowe",
    "Hao-Yu Lee", "Thomas Saggese", "Jarren Duran", "Brett Callahan",
    "Davis Schneider", "Daylen Lile", "Dylan Crews", "CJ Abrams",
    "Zac Veen", "Sam Antonacci", "Iván Herrera", "Alec Bohm",
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
