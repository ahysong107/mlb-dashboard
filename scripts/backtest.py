"""Backtest a past day's Diamond Edge predictions against real outcomes.

Pulls actual home runs and actual strikeouts for the given date from
Statcast, cross-references against that day's stored site/data/<date>.json
snapshot, and prints an accuracy report. HR/K only -- no parlay grading,
those are acknowledged as long-shot combinations by design.
"""
import json
import sys
import warnings

import pandas as pd
import requests

warnings.filterwarnings("ignore")

from lib_data import ROOT


def load_snapshot(date_str):
    p = ROOT / "site" / "data" / f"{date_str}.json"
    return json.loads(p.read_text())


def actual_outcomes(date_str):
    import pybaseball
    pybaseball.cache.enable()
    raw = pybaseball.statcast(start_dt=date_str, end_dt=date_str, verbose=False)

    hr = raw[raw["events"] == "home_run"]
    hr_counts = hr.groupby("batter").size().to_dict()

    k = raw[raw["events"] == "strikeout"]
    k_counts = k.groupby("pitcher").size().to_dict()

    return hr_counts, k_counts


def lookup_names(ids):
    if not ids:
        return {}
    ids = list(ids)
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/people",
            params={"personIds": ",".join(str(x) for x in chunk)},
            timeout=20,
        )
        for person in r.json().get("people", []):
            out[person["id"]] = person["fullName"]
    return out


def hr_report(snapshot, hr_counts):
    board = snapshot["rankings"]["home_run"]
    board_ids = {p["player_id"] for p in board}

    # The top-50 flat ranking is a small slice -- build the full scored
    # population from every per-game board too (up to 8/team/game), which is
    # much closer to "everyone the model actually looked at that day."
    scored = {p["player_id"]: p for p in board}
    for g in snapshot["games"]:
        for p in g["players"]["home_run"]:
            scored[p["player_id"]] = p
    scored_ids = set(scored)

    print(f"\n=== HOME RUN CHECK -- {snapshot['date']} ===")
    print(f"Top-50 board: {len(board_ids)} batters. Full scored population (incl. per-game boards): {len(scored_ids)}. "
          f"Actual HR hitters league-wide: {len(hr_counts)}\n")

    print("-- Our top 25, and whether they actually homered --")
    hits_in_top25 = 0
    for i, p in enumerate(board[:25]):
        did = hr_counts.get(p["player_id"], 0)
        mark = f"HIT ({did}x)" if did else "no"
        if did:
            hits_in_top25 += 1
        print(f"{i+1:>2}. {p['name']:<26} {p['hr_probability']:>5.1f}%  -> {mark}")
    print(f"\n{hits_in_top25}/25 of our top-25 ranked batters actually hit a HR on {snapshot['date']}.")

    top50_hits = [pid for pid in hr_counts if pid in board_ids]
    scored_not_top50 = [pid for pid in hr_counts if pid in scored_ids and pid not in board_ids]
    never_scored = [pid for pid in hr_counts if pid not in scored_ids]
    print(f"\nOf all {len(hr_counts)} actual HR hitters:")
    print(f"  {len(top50_hits)} were in our top-50 league ranking")
    print(f"  {len(scored_not_top50)} were scored by the model but ranked outside the top 50 (probability too low, in hindsight)")
    print(f"  {len(never_scored)} were never scored at all (below PA floor, or not in a lineup/game we had)")

    if scored_not_top50:
        print("\nScored-but-outside-top-50 HR hitters (their HR probability that day, in parens):")
        for pid in scored_not_top50:
            p = scored[pid]
            print(f"   {p['name']:<26} {p['hr_probability']:.1f}%  ({hr_counts[pid]}x)")

    if never_scored:
        names = lookup_names(never_scored)
        print("\nActual HR hitters we never scored at all:")
        for pid in never_scored:
            print(f"   {names.get(pid, pid)} ({hr_counts[pid]}x)")

    id_to_rank = {p["player_id"]: i + 1 for i, p in enumerate(board)}
    if top50_hits:
        ranks = sorted(id_to_rank[pid] for pid in top50_hits)
        print(f"\nTop-50 rank distribution of the {len(top50_hits)} HR hitters who cracked the top 50: {ranks}")


def k_report(snapshot, k_counts):
    print(f"\n=== STRIKEOUT LINE CHECK -- {snapshot['date']} ===")
    rows = []
    for p in snapshot["rankings"]["strikeouts"]:
        actual = k_counts.get(p["player_id"], 0)
        line_results = []
        for l in p["k_lines"]:
            hit = actual > l["line"]
            line_results.append((l["line"], l["prob_over"], hit))
        rows.append((p["name"], p["projected_k"], actual, line_results))

    print(f"{'Pitcher':<22}{'Proj K':>8}{'Actual K':>10}   Lines (line/prob/result)")
    for name, proj, actual, lines in rows:
        line_str = "  ".join(f"o{l:.1f}@{prob:.0f}%={'HIT' if hit else 'miss'}" for l, prob, hit in lines)
        print(f"{name:<22}{proj:>8.1f}{actual:>10}   {line_str}")

    total_lines = sum(len(r[3]) for r in rows)
    hit_lines = sum(1 for r in rows for (_, _, hit) in r[3] if hit)
    print(f"\n{hit_lines}/{total_lines} modeled strikeout lines hit (line exceeded).")

    high_conf = [(n, l, prob, hit) for n, _, _, lines in rows for (l, prob, hit) in lines if prob >= 60]
    if high_conf:
        hc_hit = sum(1 for *_, hit in high_conf if hit)
        print(f"Of lines we projected >=60% probability: {hc_hit}/{len(high_conf)} hit.")


if __name__ == "__main__":
    date_str = sys.argv[1]
    snapshot = load_snapshot(date_str)
    hr_counts, k_counts = actual_outcomes(date_str)
    hr_report(snapshot, hr_counts)
    k_report(snapshot, k_counts)
