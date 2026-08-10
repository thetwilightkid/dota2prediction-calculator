import json
import os
import random
import sys
from collections import Counter

from team_config import TEAM_CANONICAL, TEAM_POD

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NUM_TRIALS = 1_000_000
# The group stage runs exactly 6 rounds, reconstructed round-by-round from the
# real TI2025 results the user compiled:
#   rounds 1-3  within-pod (Day 1 x2, Day 2 R1)
#   rounds 4-5  merged 16-team Swiss (Day 2 R2 + Day 3 R1 form one round; Day 3 R2)
#   round 6     the elimination day (Day 4) - see DECIDER_ROUND below
# A team that reaches 4 wins or 4 losses before round 6 is already done and stops
# playing; everyone else is settled in round 6 regardless of record.
MAX_ROUNDS = 6
WINS_TO_ADVANCE = 4
LOSSES_TO_ELIMINATE = 4
# The final round is an elimination decider, not just another Swiss round: every
# team still undecided plays one match, the winner qualifies and the loser is
# out, whatever their record. That's what produces TI2025's 3-3 finishes on BOTH
# sides of the cut (Tundra/Nigma/Heroic advanced at 3-3, Aurora/Liquid went home
# at 3-3) alongside 4-2 and 2-4. Records like 4-3 or 3-4 are impossible - there
# is no 7th round to produce them.
DECIDER_ROUND = MAX_ROUNDS - 1
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


def outcomeKey(record, advanced):
    """Final-standing label. A record alone is ambiguous after the decider round:
    3-3 can mean either qualified or eliminated, so those get an 'a'/'e' suffix."""
    wins, losses = record
    if isTerminal(record):
        return f"{wins}-{losses}"
    return f"{wins}-{losses}{'a' if advanced else 'e'}"


def outcomeSortKey(key):
    """Best to worst: everyone who advanced (most wins first), then everyone who
    didn't. Keeps the two 3-3 outcomes on the correct sides of the cut."""
    suffix = key[-1] if key[-1] in ("a", "e") else ""
    base = key[: -len(suffix)] if suffix else key
    wins, losses = (int(x) for x in base.split("-"))
    advanced = wins >= WINS_TO_ADVANCE or suffix == "a"
    return (0 if advanced else 1, -wins, losses)


def outcomeLabel(key):
    """Plain-language label for the website's column headers."""
    if key.endswith("a"):
        return f"{key[:-1]} (in)"
    if key.endswith("e"):
        return f"{key[:-1]} (out)"
    return key


def foldPair(active_teams, all_teams, records, rng):
    """Decider-round pairing: sort by standing, then pair the top half against
    the bottom half (best vs worst still alive), which is how TI2025's Day 4 was
    drawn - 3-2 teams were matched against 2-3 teams, with the leftover 2-3 teams
    paired together once the 3-2 pool ran out."""
    ordered = sorted(active_teams, key=lambda tid: (-(records[tid][0] - records[tid][1]), rng.random()))
    half = len(ordered) // 2
    pairings = [(a, b, True) for a, b in zip(ordered[:half], ordered[half : 2 * half])]

    # Proper Swiss pairing always leaves an even number of undecided teams here,
    # but never leave a straggler unsettled if rematch-avoidance skewed a group.
    if len(ordered) % 2:
        a = ordered[-1]
        terminal_pool = [tid for tid in all_teams if tid != a and isTerminal(records[tid])]
        if terminal_pool:
            pairings.append((a, terminal_pool[rng.randrange(len(terminal_pool))], False))

    return pairings


def pairRound(active_teams, all_teams, records, played_pairs, rng):
    """Standard Swiss: teams only face opponents on the exact same record, with
    rematches avoided where the group offers an alternative. Pairing strictly
    inside record groups (rather than sorting everyone by wins-losses and pairing
    adjacent, which this used to do) is what keeps the bracket balanced - every
    record group in a 16-team, 8-advance Swiss has an even size, so the field
    splits into exactly 8 qualifiers and 8 eliminations. Loose pairing across
    group boundaries used to break that, letting ~12% of trials finish with 7 or
    9 teams through. Verified against TI2025, where every round-2-to-5 match was
    between teams on identical records.

    An odd leftover (only reachable if rematch-avoidance skews a group) floats
    down to the next record group, and a straggler at the very bottom is given a
    game against an already-finished team rather than being skipped."""
    groups = {}
    for tid in active_teams:
        groups.setdefault(records[tid], []).append(tid)

    pairings = []  # (a, b, update_b_record)
    floated = []
    for record in sorted(groups, key=lambda r: (-(r[0] - r[1]), r[0])):
        pool = floated + groups[record]
        rng.shuffle(pool)
        while len(pool) >= 2:
            a = pool.pop(0)
            opp_idx = 0
            for i, b in enumerate(pool):
                if (a, b) not in played_pairs and (b, a) not in played_pairs:
                    opp_idx = i
                    break
            b = pool.pop(opp_idx)
            pairings.append((a, b, True))
        floated = pool

    if floated:
        a = floated[0]
        terminal_pool = [tid for tid in all_teams if tid != a and isTerminal(records[tid])]
        if terminal_pool:
            pairings.append((a, terminal_pool[rng.randrange(len(terminal_pool))], False))

    return pairings


def runSwissTrial(trial_ratings, rng, forced_first_round=None, trace=None):
    """One full group-stage trial. trial_ratings: {team_id: sampled rating}.
    forced_first_round: optional list of (team_a, team_b) - if given, round 1
    uses these exact pairings (the real announced Day 1 matches) instead of the
    standings-based approximation. trace: optional callback
    (round_index, pairings, records_before) used by verify_format.py to audit
    the pairing structure against real TI2025 rounds.
    Returns {team_id: ((wins, losses), advanced)}."""
    records = {tid: (0, 0) for tid in trial_ratings}
    advanced = {tid: False for tid in trial_ratings}
    played_pairs = set()
    all_teams = list(trial_ratings.keys())

    for round_num in range(MAX_ROUNDS):
        active = [tid for tid in all_teams if not isTerminal(records[tid])]
        if not active:
            break

        is_decider = round_num == DECIDER_ROUND
        if round_num == 0 and forced_first_round:
            pairings = [(a, b, True) for a, b in forced_first_round]
        elif is_decider:
            pairings = foldPair(active, all_teams, records, rng)
        elif round_num < PODDED_ROUNDS:
            # within-pod only - safe to assume all 8 pod members are still
            # active this early (nobody can be terminal before round 4)
            pairings = []
            for pod in ("A", "B"):
                pod_teams = [tid for tid in active if TEAM_POD.get(tid) == pod]
                pairings += pairRound(pod_teams, pod_teams, records, played_pairs, rng)
        else:
            pairings = pairRound(active, all_teams, records, played_pairs, rng)

        if trace is not None:
            trace(round_num, pairings, dict(records))

        for a, b, update_b in pairings:
            played_pairs.add((a, b))
            p_a = winProbability(trial_ratings[a], trial_ratings[b])
            a_won = rng.random() < p_a
            if a_won:
                records[a] = (records[a][0] + 1, records[a][1])
                if update_b:
                    records[b] = (records[b][0], records[b][1] + 1)
            else:
                if update_b:
                    records[b] = (records[b][0] + 1, records[b][1])
                records[a] = (records[a][0], records[a][1] + 1)
            if is_decider:
                # Elimination day: winner is through, loser is out, regardless
                # of whether either reached 4 wins / 4 losses.
                advanced[a] = a_won
                if update_b:
                    advanced[b] = not a_won

        for tid in all_teams:
            if records[tid][0] >= WINS_TO_ADVANCE:
                advanced[tid] = True

    return {tid: (records[tid], advanced[tid]) for tid in all_teams}


def runSwissSimulation(team_ratings, num_trials, rng=None, forced_first_round=None):
    """team_ratings: {team_id: {"mean": float, "sigma": float}}.
    Runs num_trials independent group-stage simulations, sampling a fresh
    rating per team per trial from Normal(mean, sigma). Returns
    {team_id: Counter({outcome_key: count, ...})}."""
    rng = rng or random.Random()
    outcome_counts = {tid: Counter() for tid in team_ratings}

    for _ in range(num_trials):
        trial_ratings = {
            tid: rng.gauss(params["mean"], params["sigma"])
            for tid, params in team_ratings.items()
        }
        final_records = runSwissTrial(trial_ratings, rng, forced_first_round)
        for tid, (record, advanced) in final_records.items():
            outcome_counts[tid][outcomeKey(record, advanced)] += 1

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

    all_keys = sorted({k for counts in outcomes.values() for k in counts}, key=outcomeSortKey)

    print("\n=== Outcome distribution per team (% of trials) ===")
    header = "Team".ljust(16) + "".join(outcomeLabel(k).rjust(11) for k in all_keys) + "advance".rjust(11)
    print(header)
    results = {}
    for tid in sorted(team_ratings, key=lambda t: -team_ratings[t]["mean"]):
        counts = outcomes[tid]
        row_pcts = {}
        row = TEAM_CANONICAL[tid].ljust(16)
        advance_pct = 0.0
        for k in all_keys:
            pct = 100.0 * counts.get(k, 0) / num_trials
            row_pcts[k] = round(pct, 2)
            if outcomeSortKey(k)[0] == 0:
                advance_pct += pct
            row += f"{pct:6.1f}%".rjust(11)
        row += f"{advance_pct:6.1f}%".rjust(11)
        print(row)
        results[str(tid)] = {
            "team_name": TEAM_CANONICAL[tid],
            "outcome_pct": row_pcts,
            "advance_pct": round(advance_pct, 2),
        }

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
                "pod_note": "Rounds 1-3 (0-indexed 0..2) pair teams only against others in their own pod (A/B, confirmed from real TI2025 results and TI2026's announced Day 1 pairings). Rounds 4-5 are a single merged 16-team Swiss.",
                "decider_round": DECIDER_ROUND + 1,
                "decider_note": "Round 6 is the elimination day: every team not already at 4 wins or 4 losses plays one final match - the winner qualifies and the loser is out, whatever their record. This is why 3-3 appears as both a qualifying and an eliminating outcome, and why 4-3/3-4 are impossible (there is no 7th round). Reconstructed from real TI2025 Day 4 results.",
                "outcome_order": all_keys,
                "outcome_labels": {k: outcomeLabel(k) for k in all_keys},
                "advancing_outcomes": [k for k in all_keys if outcomeSortKey(k)[0] == 0],
            },
            "teams": results,
        }, f, ensure_ascii=False, indent=4)

    print(f"\nSaved prediction/{out_filename}")
