import json
import os
import random
import sys
from collections import Counter

from team_config import TEAM_CANONICAL, TEAM_POD

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NUM_TRIALS = 1_000_000
# Real TI Swiss format has no fixed round cap - a team keeps playing until it
# hits 4 wins or 4 losses. 7 is a safe upper bound, not a termination trigger:
# after 7 games a team can no longer be at a non-terminal 3-3 (pigeonhole -
# someone must have reached 4 by then), confirmed against real TI2025 results
# (final records included 4:2 and 3:3, i.e. 6-7 games - a fixed 5-game cap,
# which this script used to have, was cutting those trials off too early).
MAX_ROUNDS = 7
WINS_TO_ADVANCE = 4
LOSSES_TO_ELIMINATE = 4
# TI's group stage splits teams into two hidden seeding pods (confirmed from
# TI2025 results and cross-checked against TI2026's real announced Day 1
# pairings - every one of the 8 matches is within-pod). Swiss pairing stays
# within a team's own pod for these first PODDED_ROUNDS rounds; from then on
# it's a single merged 16-team Swiss. No team can be terminal before round 4
# (impossible to reach 4 wins/losses in under 4 games), so pods are guaranteed
# to still have all 8 members active throughout the podded phase.
PODDED_ROUNDS = 3

# TI2026 group-stage Round 1 pairings, announced for August 13 - these are real,
# not simulated, so every trial's first round uses them directly instead of the
# standings-based pairing approximation (which round 1 would otherwise reduce to
# an arbitrary pairing anyway, since every team starts 0-0). This measurably
# shifts the 4-0/4-1/.../0-4 placement odds versus a fully random draw, since a
# team's actual first opponent is now known rather than averaged over.
DAY1_PAIRINGS = [
    (9247354, 10150538),   # Team Falcons vs LGD Gaming
    (10150413, 10136357),  # Iron Wing vs Nigma Galaxy
    (8255888, 2586976),    # BoomBoys vs OG
    (9572001, 5017210),    # Team Vision vs Team Resilience
    (7119388, 8261500),    # Team Spirit vs Xtreme Gaming
    (2163, 726228),        # Team Liquid vs Vici Gaming
    (9467224, 9964962),    # Aurora Gaming vs GamerLegion
    (9823272, 10149530),   # Team Yandex vs HULIGANI
]


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def winProbability(rating_a, rating_b):
    """Standard Elo/Glicko-style logistic win probability from rating-scale values."""
    return 1.0 / (1.0 + 10.0 ** (-(rating_a - rating_b) / 400.0))


def isTerminal(record):
    wins, losses = record
    return wins >= WINS_TO_ADVANCE or losses >= LOSSES_TO_ELIMINATE


def pairRound(active_teams, all_teams, records, played_pairs, rng):
    """Sort still-active teams by current standing (wins-losses desc) and pair
    adjacent teams - a standard simplified Swiss approximation. Avoids exact
    rematches where an alternative is available. If a team has no valid active
    opponent left this round (odd leftover, or the last team standing), it's
    paired against an already-terminal team instead of skipped - every
    non-terminal team is guaranteed a game each round, so no team can get
    stuck below 5 total games without reaching 4W/4L (which would otherwise
    produce an impossible "final" record like 3-1)."""
    ordered = sorted(active_teams, key=lambda tid: (-(records[tid][0] - records[tid][1]), rng.random()))

    pairings = []  # (a, b, update_b_record)
    unpaired = list(ordered)
    while unpaired:
        a = unpaired.pop(0)
        if not unpaired:
            terminal_pool = [tid for tid in all_teams if tid != a and isTerminal(records[tid])]
            if terminal_pool:
                b = terminal_pool[rng.randrange(len(terminal_pool))]
                pairings.append((a, b, False))
            break

        opp_idx = 0
        for i, b in enumerate(unpaired):
            if (a, b) not in played_pairs and (b, a) not in played_pairs:
                opp_idx = i
                break
        b = unpaired.pop(opp_idx)
        pairings.append((a, b, True))

    return pairings


def runSwissTrial(trial_ratings, rng, forced_first_round=None):
    """One full group-stage trial. trial_ratings: {team_id: sampled rating}.
    forced_first_round: optional list of (team_a, team_b) - if given, round 1
    uses these exact pairings (the real announced Day 1 matches) instead of the
    standings-based approximation. Returns {team_id: (wins, losses)} final records."""
    records = {tid: (0, 0) for tid in trial_ratings}
    played_pairs = set()
    all_teams = list(trial_ratings.keys())

    for round_num in range(MAX_ROUNDS):
        active = [tid for tid in all_teams if not isTerminal(records[tid])]
        if not active:
            break

        if round_num == 0 and forced_first_round:
            pairings = [(a, b, True) for a, b in forced_first_round]
        elif round_num < PODDED_ROUNDS:
            # within-pod only - safe to assume all 8 pod members are still
            # active this early (nobody can be terminal before round 4)
            pairings = []
            for pod in ("A", "B"):
                pod_teams = [tid for tid in active if TEAM_POD.get(tid) == pod]
                pairings += pairRound(pod_teams, pod_teams, records, played_pairs, rng)
        else:
            pairings = pairRound(active, all_teams, records, played_pairs, rng)
        for a, b, update_b in pairings:
            played_pairs.add((a, b))
            p_a = winProbability(trial_ratings[a], trial_ratings[b])
            if rng.random() < p_a:
                records[a] = (records[a][0] + 1, records[a][1])
                if update_b:
                    records[b] = (records[b][0], records[b][1] + 1)
            else:
                if update_b:
                    records[b] = (records[b][0] + 1, records[b][1])
                records[a] = (records[a][0], records[a][1] + 1)

    return records


def runSwissSimulation(team_ratings, num_trials, rng=None, forced_first_round=None):
    """team_ratings: {team_id: {"mean": float, "sigma": float}}.
    Runs num_trials independent group-stage simulations, sampling a fresh
    rating per team per trial from Normal(mean, sigma). Returns
    {team_id: Counter({(wins, losses): count, ...})}."""
    rng = rng or random.Random()
    outcome_counts = {tid: Counter() for tid in team_ratings}

    for _ in range(num_trials):
        trial_ratings = {
            tid: rng.gauss(params["mean"], params["sigma"])
            for tid, params in team_ratings.items()
        }
        final_records = runSwissTrial(trial_ratings, rng, forced_first_round)
        for tid, record in final_records.items():
            outcome_counts[tid][record] += 1

    return outcome_counts


if __name__ == "__main__":
    # usage: python simulate_group_stage.py [num_trials]
    # num_trials defaults to DEFAULT_NUM_TRIALS (1,000,000) - the single canonical
    # precision the website's precomputed data uses. A CLI override is for local
    # experimentation only and still writes to the same canonical output file.
    num_trials = DEFAULT_NUM_TRIALS
    if len(sys.argv) > 1:
        num_trials = int(sys.argv[1])

    with open(localPath("team_composite_ratings.json"), "r", encoding="utf-8") as f:
        composite = json.load(f)["teams"]

    team_ratings = {
        int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
        for tid, v in composite.items()
    }

    print(f"=== Running {num_trials} Swiss group-stage simulations (Round 1 fixed to announced Day 1 pairings) ===")
    for tid, params in sorted(team_ratings.items(), key=lambda kv: -kv[1]["mean"]):
        print(f"  {TEAM_CANONICAL[tid]:16s} mean={params['mean']:.1f} sigma={params['sigma']:.1f}")

    rng = random.Random(42)
    outcomes = runSwissSimulation(team_ratings, num_trials, rng, forced_first_round=DAY1_PAIRINGS)

    all_records = sorted({r for counts in outcomes.values() for r in counts}, key=lambda r: (-r[0], r[1]))

    print("\n=== Outcome distribution per team (% of trials) ===")
    header = "Team".ljust(16) + "".join(f"{w}-{l}".rjust(7) for w, l in all_records)
    print(header)
    results = {}
    for tid in sorted(team_ratings, key=lambda t: -team_ratings[t]["mean"]):
        counts = outcomes[tid]
        row_pcts = {}
        row = TEAM_CANONICAL[tid].ljust(16)
        for r in all_records:
            pct = 100.0 * counts.get(r, 0) / num_trials
            row_pcts[f"{r[0]}-{r[1]}"] = round(pct, 2)
            row += f"{pct:6.1f}%".rjust(7)
        print(row)
        results[str(tid)] = {"team_name": TEAM_CANONICAL[tid], "outcome_pct": row_pcts}

    out_filename = "group_stage_simulation_results.json"
    with open(localPath(out_filename), "w", encoding="utf-8") as f:
        json.dump({
            "_meta": {
                "num_trials": num_trials,
                "max_rounds": MAX_ROUNDS,
                "wins_to_advance": WINS_TO_ADVANCE,
                "losses_to_eliminate": LOSSES_TO_ELIMINATE,
                "day1_pairings_forced": True,
                "day1_pairings": [[a, b] for a, b in DAY1_PAIRINGS],
                "day1_note": "Round 1 of every trial uses these announced Day 1 (Aug 13) pairings directly instead of the standings-based approximation, so the outcome distribution already reflects each team's real first opponent.",
                "podded_rounds": PODDED_ROUNDS,
                "team_pod": {str(tid): pod for tid, pod in TEAM_POD.items()},
                "pod_note": "Rounds 1-3 (0-indexed 0..2) pair teams only against others in their own pod (A/B, confirmed from real TI2025 results and TI2026's announced Day 1 pairings). From round 4 on it's a single merged 16-team Swiss. No fixed round cap - a team plays until it reaches 4 wins or 4 losses (up to 7 rounds).",
            },
            "teams": results,
        }, f, ensure_ascii=False, indent=4)

    print(f"\nSaved prediction/{out_filename}")
