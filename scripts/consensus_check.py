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

DATE = "2026-09-26"

VENOM_TOP50 = [
    (1, "Brandon Lowe"), (2, "Elly De La Cruz"), (3, "Munetaka Murakami"),
    (4, "Jake Bauers"), (5, "Francisco Alvarez"), (6, "Shohei Ohtani"),
    (7, "Zack Gelof"), (8, "Eduardo Valencia"), (9, "Rafael Flores Jr."),
    (10, "Randy Arozarena"), (11, "Thomas Saggese"), (12, "Randal Grichuk"),
    (13, "Corbin Carroll"), (14, "Lawrence Butler"), (15, "Drake Baldwin"),
    (16, "Ronald Acuña Jr."), (17, "Yohandy Morales"), (18, "Vinnie Pasquantino"),
    (19, "Cal Raleigh"), (20, "Mike Trout"), (21, "Yordan Alvarez"),
    (22, "Emmanuel Rodriguez"), (23, "Josh Jung"), (24, "Iván Herrera"),
    (25, "Corey Seager"), (26, "Fernando Tatis Jr."), (27, "Kyle Teel"),
    (28, "Jackson Merrill"), (29, "Jonathan Aranda"), (30, "Kazuma Okamoto"),
    (31, "Lazaro Montes"), (32, "Colson Montgomery"), (33, "Daylen Lile"),
    (34, "Kyle Stowers"), (35, "Nelson Velázquez"), (36, "Eugenio Suárez"),
    (37, "Brett Callahan"), (38, "Davis Schneider"), (39, "Alec Burleson"),
    (40, "Jac Caglianone"), (41, "Jackson Chourio"), (42, "Sean Keys"),
    (43, "Jordan Walker"), (44, "Bryan Reynolds"), (45, "Riley Greene"),
    (46, "Spencer Torkelson"), (47, "Austin Riley"), (48, "Vladimir Guerrero Jr."),
    (49, "Henry Davis"), (50, "Walker Jenkins"),
]

VENOM_VIPER = [
    "Shohei Ohtani", "Thomas Saggese", "Sean Murphy", "Jesús Sánchez",
    "Brett Callahan", "Elias Díaz", "Drake Baldwin", "Wyatt Langford",
    "Kevin McGonigle", "Jac Caglianone", "Eduardo Valencia", "Freddie Freeman",
    "Alec Bohm", "Colson Montgomery", "Ryan Jeffers", "Brady House",
    "Andrew Benintendi", "Justin Foscue", "Nolan Gorman", "Matt McLain",
    "José Tena", "Jake Rogers", "Tyler Stephenson",
]

VENOM_EDGE = [
    "Brandon Lowe", "Thomas Saggese", "Rafael Flores Jr.", "Jake Bauers",
    "Kevin McGonigle", "Vladimir Guerrero Jr.", "Austin Riley", "Bryan Reynolds",
    "Zack Gelof", "Josh Jung", "Daylen Lile", "Drake Baldwin",
    "Davis Schneider", "Lawrence Butler", "Mark Vientos", "Alec Bohm",
    "Iván Herrera", "Emmanuel Rodriguez", "Carson Benge", "Sal Stewart",
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
