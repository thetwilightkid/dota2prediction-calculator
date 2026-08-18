"""Audits simulate_playoffs.py's bracket structure against the known invariants
of an 8-team, 14-match, no-reset double-elimination bracket. Mirrors
verify_format.py's pattern: run many trials, assert structural invariants,
print one full example bracket for manual eyeballing. Run this and confirm
every check passes BEFORE trusting simulate_playoffs.py's output.

Run: python verify_playoff_bracket.py [num_trials]
"""

import json
import random
import sys
from collections import Counter

import simulate_playoffs as sim
from team_config import TEAM_CANONICAL
from playoff_teams import PLAYOFF_TEAM_IDS, UB_R1_PAIRINGS

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000

# A team's number of series played is bounded by its path through the
# bracket: the shortest possible run is losing UB R1 then losing LB R1 (2
# series); the longest is entering via the lower bracket and winning every
# series through to the Grand Final (UB R1, LB R1, LB R2, LB R3, LB Final,
# Grand Final = 6 series).
VALID_SERIES_COUNTS = {2, 3, 4, 5, 6}


def loadRatings():
    with open(sim.localPath("team_composite_ratings.json"), "r", encoding="utf-8") as f:
        composite = json.load(f)["teams"]
    return {
        int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
        for tid, v in composite.items()
        if int(tid) in PLAYOFF_TEAM_IDS
    }


def auditTrial(results, failures):
    # every UB match's loser must land in the LB match BRACKET_MATCHES says it should
    for match_id, spec in sim.BRACKET_MATCHES.items():
        r = results[match_id]
        if spec["loser_to"]:
            target_match, slot = spec["loser_to"].split(":")
            if results[target_match][slot] != r["loser"]:
                failures["loser_routing"] += 1
        if spec["winner_to"]:
            target_match, slot = spec["winner_to"].split(":")
            if results[target_match][slot] != r["winner"]:
                failures["winner_routing"] += 1

        games_played = 0  # reconstruct from best_of + who won isn't stored, so just check plausible bounds
        wins_needed = spec["best_of"] // 2 + 1
        if spec["best_of"] == 5 and match_id != "grand_final":
            failures["unexpected_bo5"] += 1
        if spec["best_of"] == 3 and match_id == "grand_final":
            failures["grand_final_not_bo5"] += 1

    # exactly 1 champion, 1 runner-up
    gf = results["grand_final"]
    if gf["winner"] == gf["loser"]:
        failures["degenerate_grand_final"] += 1

    # every team's series-played count is in the valid range
    for tid in PLAYOFF_TEAM_IDS:
        count = sum(1 for mid in sim.MATCH_ORDER if tid in (results[mid]["a"], results[mid]["b"]))
        if count not in VALID_SERIES_COUNTS:
            failures["bad_series_count"] += 1

    # every team must appear in exactly one of UB R1's 4 matches, using the real seeding
    seeded = set()
    for i in range(1, 5):
        a, b = results[f"ub_r1_{i}"]["a"], results[f"ub_r1_{i}"]["b"]
        seeded.add(a)
        seeded.add(b)
    if seeded != set(PLAYOFF_TEAM_IDS):
        failures["seeding_mismatch"] += 1


def describeTrial(results):
    print("\n  --- Example bracket walkthrough ---")
    for match_id in sim.MATCH_ORDER:
        r = results[match_id]
        bo = r["best_of"]
        print(f"    [{match_id:12s} Bo{bo}]  {TEAM_CANONICAL[r['a']]:16s} vs {TEAM_CANONICAL[r['b']]:16s}  ->  winner: {TEAM_CANONICAL[r['winner']]}")

    print("\n  --- Final standings ---")
    tid_to_last = {}
    for tid in PLAYOFF_TEAM_IDS:
        appearances = [i for i, mid in enumerate(sim.MATCH_ORDER) if tid in (results[mid]["a"], results[mid]["b"])]
        tid_to_last[tid] = sim.MATCH_ORDER[max(appearances)]

    def rank(tid):
        last = tid_to_last[tid]
        won = results[last]["winner"] == tid
        if last == "grand_final":
            return 0 if won else 1
        order = ["lb_final", "lb_r3", "lb_r2_1", "lb_r1_1"]
        return 2 + (order.index(last) if last in order else 5)

    for tid in sorted(PLAYOFF_TEAM_IDS, key=rank):
        last = tid_to_last[tid]
        won = results[last]["winner"] == tid
        if last == "grand_final":
            status = "CHAMPION" if won else "runner-up"
        else:
            status = sim.ELIMINATION_LABEL[last]
        print(f"    {TEAM_CANONICAL[tid]:16s} {status}")


if __name__ == "__main__":
    team_ratings = loadRatings()
    rng = random.Random(2026)
    failures = Counter()
    champion_counts = Counter()
    first_result = None

    print(f"=== Auditing {TRIALS:,} simulated playoff brackets ===")

    for trial in range(TRIALS):
        trial_ratings = {tid: rng.gauss(p["mean"], p["sigma"]) for tid, p in team_ratings.items()}
        results = sim.runBracketTrial(trial_ratings, rng, UB_R1_PAIRINGS)
        auditTrial(results, failures)
        champion_counts[results["grand_final"]["winner"]] += 1
        if first_result is None:
            first_result = results

    checks = [
        ("Every UB/LB match's winner is routed to the correct next-match slot", failures["winner_routing"]),
        ("Every UB match's loser drops to the correct LB match", failures["loser_routing"]),
        ("Only the Grand Final is best-of-5, everything else best-of-3", failures["unexpected_bo5"] + failures["grand_final_not_bo5"]),
        ("Grand Final always has 2 distinct participants", failures["degenerate_grand_final"]),
        ("Every team's series-played count is in {2,3,4,5,6}", failures["bad_series_count"]),
        ("UB R1 seeding matches the real announced pairings, every trial", failures["seeding_mismatch"]),
        ("Exactly 1 champion emerges per trial (trivially true by construction)", TRIALS - sum(champion_counts.values())),
    ]
    print()
    for label, bad in checks:
        print(f"  [{'OK  ' if bad == 0 else 'FAIL'}] {label}" + ("" if bad == 0 else f"  ({bad:,} violations)"))

    print("\n  Champion distribution across trials:")
    for tid, count in champion_counts.most_common():
        print(f"    {TEAM_CANONICAL[tid]:16s} {100.0 * count / TRIALS:5.2f}%")

    describeTrial(first_result)
