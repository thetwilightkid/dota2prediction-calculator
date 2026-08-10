"""Audits the group-stage simulator against the real TI2025 round structure.

The TI2025 group stage (compiled by hand from the actual results) worked like
this, and every rule below is asserted against many simulated trials:

  Rounds 1-3   within your own group only (Day 1 R1, Day 1 R2, Day 2 R1).
               Pairing is same-record, so the group's strong teams meet each
               other and its weak teams meet each other.
  Rounds 4-5   groups merge - still same-record, so a 3-0 from group A now
               plays a 3-0 from group B, a 1-2 plays a 1-2, and so on. (Round 4
               was physically split across Day 2 R2 and Day 3 R1: the low
               records played first, the high records the next morning, but it
               is one Swiss round.)
  Round 6      elimination day. Everyone not already at 4 wins or 4 losses
               plays once - winner qualifies, loser is out regardless of record.
               This is what produced TI2025's 3-3 teams on both sides.

Run: python verify_format.py [num_trials]
"""

import json
import random
import sys
from collections import Counter

import simulate_group_stage as sim
from team_config import TEAM_CANONICAL, TEAM_POD

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000


def loadRatings():
    with open(sim.localPath("team_composite_ratings.json"), "r", encoding="utf-8") as f:
        composite = json.load(f)["teams"]
    return {
        int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
        for tid, v in composite.items()
    }


def auditTrial(round_log, failures):
    """round_log: [(round_index, pairings, records_before), ...] for one trial."""
    for round_num, pairings, records in round_log:
        for a, b, update_b in pairings:
            if not update_b:
                continue  # borrowed already-finished opponent, not a real Swiss pair
            if round_num < sim.PODDED_ROUNDS and TEAM_POD.get(a) != TEAM_POD.get(b):
                failures["cross_group_early"] += 1
            if round_num < sim.DECIDER_ROUND and records[a] != records[b]:
                failures["mismatched_records"] += 1
            if round_num == sim.DECIDER_ROUND:
                # decider pairs best-remaining against worst-remaining, so a
                # record gap of at most one game is expected, never more
                if abs((records[a][0] - records[a][1]) - (records[b][0] - records[b][1])) > 2:
                    failures["decider_gap"] += 1


def describeTrial(round_log, final):
    """Print one trial the same way the TI2025 results were written up."""
    day_labels = {
        0: "Day 1, Round 1",
        1: "Day 1, Round 2",
        2: "Day 2, Round 1",
        3: "Day 2 R2 + Day 3 R1",
        4: "Day 3, Round 2",
        5: "Day 4 (elimination day)",
    }
    for round_num, pairings, records in round_log:
        scope = "within groups" if round_num < sim.PODDED_ROUNDS else "groups merged"
        if round_num == sim.DECIDER_ROUND:
            scope = "winner qualifies, loser is out"
        print(f"\n  --- Round {round_num + 1}: {day_labels.get(round_num, '')} ({scope}) ---")
        for a, b, update_b in pairings:
            pod_a, pod_b = TEAM_POD.get(a, "?"), TEAM_POD.get(b, "?")
            rec_a = f"{records[a][0]}:{records[a][1]}"
            rec_b = f"{records[b][0]}:{records[b][1]}"
            tail = "" if update_b else "   (opponent already finished)"
            print(
                f"    {TEAM_CANONICAL[a]:16s} [{pod_a} {rec_a}]  vs  "
                f"{TEAM_CANONICAL[b]:16s} [{pod_b} {rec_b}]{tail}"
            )

    print("\n  --- Final standings ---")
    ordered = sorted(final.items(), key=lambda kv: sim.outcomeSortKey(sim.outcomeKey(*kv[1])))
    for tid, (record, advanced) in ordered:
        status = "QUALIFIED" if advanced else "eliminated"
        print(f"    {TEAM_CANONICAL[tid]:16s} {record[0]}:{record[1]}  {status}")


if __name__ == "__main__":
    team_ratings = loadRatings()
    rng = random.Random(2026)
    failures = Counter()
    advancer_counts = Counter()
    games_played = Counter()
    round_sizes = Counter()
    first_log = None

    print(f"=== Auditing {TRIALS:,} simulated group stages against the TI2025 structure ===")

    for trial in range(TRIALS):
        ratings = {tid: rng.gauss(p["mean"], p["sigma"]) for tid, p in team_ratings.items()}
        round_log = []
        final = sim.runSwissTrial(
            ratings,
            rng,
            forced_first_round=sim.DAY1_PAIRINGS,
            trace=lambda rn, pr, rec: round_log.append((rn, list(pr), rec)),
        )
        auditTrial(round_log, failures)
        advancer_counts[sum(1 for _, adv in final.values() if adv)] += 1
        for record, _ in final.values():
            games_played[sum(record)] += 1
        for round_num, pairings, _ in round_log:
            round_sizes[(round_num, len(pairings))] += 1
        if first_log is None:
            first_log = (round_log, final)

    checks = [
        ("Rounds 1-3 stay inside a team's own group", failures["cross_group_early"]),
        ("Rounds 1-5 only pair teams on identical records", failures["mismatched_records"]),
        ("Round 6 pairs best-remaining vs worst-remaining", failures["decider_gap"]),
        ("Exactly 8 teams qualify, every trial", TRIALS - advancer_counts[8]),
        ("No team finishes past 6 games", sum(v for k, v in games_played.items() if k > 6)),
    ]
    print()
    for label, bad in checks:
        print(f"  [{'OK  ' if bad == 0 else 'FAIL'}] {label}" + ("" if bad == 0 else f"  ({bad:,} violations)"))

    print("\n  Matches per round (round: matches -> how many trials):")
    for (round_num, size), count in sorted(round_sizes.items()):
        print(f"    round {round_num + 1}: {size:2d} matches   {count:,} trials")

    print("\n  Games played by a team before finishing:")
    total_team_trials = TRIALS * len(team_ratings)
    for games, count in sorted(games_played.items()):
        print(f"    {games} games   {100.0 * count / total_team_trials:5.1f}%")

    print("\n=== One example simulated tournament ===")
    describeTrial(*first_log)
