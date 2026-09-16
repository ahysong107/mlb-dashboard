"""One-off: compare Venom Analytics' 9/15 top-50 HR board against ours and
against what actually happened, using the same backtest data.
"""
import json
import sys
import unicodedata
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, "scripts")
from lib_data import ROOT
from backtest import actual_outcomes, lookup_names, load_snapshot

DATE = "2026-09-15"

VENOM_TOP50 = [
    (1, "Jackson Merrill"), (2, "Luis García Jr."), (3, "Elly De La Cruz"),
    (4, "Kazuma Okamoto"), (5, "Corbin Carroll"), (6, "Pete Crow-Armstrong"),
    (7, "Fernando Tatis Jr."), (8, "Roman Anthony"), (9, "Eugenio Suárez"),
    (10, "Ian Happ"), (11, "Teoscar Hernández"), (12, "Ty France"),
    (13, "Riley Greene"), (14, "Corey Seager"), (16, "Kyle Schwarber"),
    (17, "Wilyer Abreu"), (18, "Max Muncy"), (19, "Manny Machado"),
    (20, "Carter Jensen"), (21, "Cal Raleigh"), (22, "Pete Alonso"),
    (24, "Munetaka Murakami"), (25, "Kyle Tucker"), (26, "Heliot Ramos"),
    (27, "William Contreras"), (28, "Matt Olson"), (29, "Bryan Reynolds"),
    (30, "Jake Burger"), (31, "Connor Norby"), (32, "Mookie Betts"),
    (33, "Leo Bernal"), (35, "Jac Caglianone"), (36, "Spencer Jones"),
    (37, "Jonathan Aranda"), (38, "Coby Mayo"), (39, "Bobby Witt Jr."),
    (40, "Mickey Gasper"), (41, "Zack Gelof"), (43, "Josh Bell"),
    (45, "Heriberto Hernández"), (46, "Zac Veen"), (47, "Ben Rice"),
    (48, "Seiya Suzuki"), (49, "Junior Caminero"), (50, "Randy Arozarena"),
]

VENOM_VIPER = [
    "Wilyer Abreu", "Seiya Suzuki", "Spencer Jones", "Ian Happ",
    "Jac Caglianone", "Zac Veen", "Eduardo Valencia", "Colton Cowser",
    "Hunter Feduccia", "JJ Bleday", "Gabriel Arias", "Royce Lewis",
]


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return name.lower().strip()


def main():
    snapshot = load_snapshot(DATE)
    hr_counts, _ = actual_outcomes(DATE)
    names = lookup_names(list(hr_counts.keys()))
    actual_hr_names = {norm(n) for n in names.values()}

    our_board = snapshot["rankings"]["home_run"]
    our_rank_by_name = {norm(p["name"]): (i + 1, p["hr_probability"]) for i, p in enumerate(our_board)}
    our_scored = {norm(p["name"]): p["hr_probability"] for p in our_board}
    for g in snapshot["games"]:
        for p in g["players"]["home_run"]:
            our_scored.setdefault(norm(p["name"]), p["hr_probability"])

    print(f"=== Venom top-50 vs actual outcomes, {DATE} ===\n")
    hits = 0
    top25_hits = 0
    rows = []
    for rank, name in VENOM_TOP50:
        did_hr = norm(name) in actual_hr_names
        our_info = our_rank_by_name.get(norm(name))
        our_pct = our_scored.get(norm(name))
        if did_hr:
            hits += 1
            if rank <= 25:
                top25_hits += 1
        rows.append((rank, name, did_hr, our_info, our_pct))

    print(f"{'Venom#':<8}{'Player':<24}{'Actual HR':<11}{'Our Rank':<10}{'Our HR%'}")
    for rank, name, did_hr, our_info, our_pct in rows:
        our_rank_str = str(our_info[0]) if our_info else "-"
        our_pct_str = f"{our_pct:.1f}%" if our_pct is not None else "not scored"
        print(f"{rank:<8}{name:<24}{'HIT' if did_hr else 'no':<11}{our_rank_str:<10}{our_pct_str}")

    print(f"\nVenom top-50: {hits}/{len(VENOM_TOP50)} actually homered.")
    n_top25 = sum(1 for r, *_ in rows if r <= 25)
    print(f"Venom top-25 (by their rank number, {n_top25} entries present): {top25_hits}/{n_top25} actually homered.")

    print(f"\n=== Viper Alert vs actual outcomes ===")
    viper_hits = sum(1 for n in VENOM_VIPER if norm(n) in actual_hr_names)
    print(f"{viper_hits}/{len(VENOM_VIPER)} Venom Viper Alert names actually homered on {DATE}.")
    for n in VENOM_VIPER:
        print(f"   {n}: {'HIT' if norm(n) in actual_hr_names else 'no'}")

    # our own DUE/VIPER flagged players that day, for the same comparison
    our_viper = []
    for g in snapshot["games"]:
        for p in g["players"]["home_run"]:
            if "VIPER" in p.get("reason_tags", []) or "DUE" in p.get("reason_tags", []):
                our_viper.append(p["name"])
    our_viper = sorted(set(our_viper))
    our_viper_hits = sum(1 for n in our_viper if norm(n) in actual_hr_names)
    print(f"\nOur own DUE/VIPER flagged batters that day: {len(our_viper)}, {our_viper_hits} actually homered.")
    for n in our_viper:
        print(f"   {n}: {'HIT' if norm(n) in actual_hr_names else 'no'}")


if __name__ == "__main__":
    main()
