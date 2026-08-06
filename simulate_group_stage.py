import json
import os
import random
import sys
from collections import Counter

from team_config import TEAM_CANONICAL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NUM_TRIALS = 10000
TRIAL_CHOICES = (10000, 100000)  # the two scales the website should let a user pick between
MAX_ROUNDS = 5
WINS_TO_ADVANCE = 4
LOSSES_TO_ELIMINATE = 4


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def winProbability(rating_a, rating_b):
    """Standard Elo/Glicko-style logistic win probability from rating-scale values."""
    return 1.0 / (1.0 + 10.0 ** (-(rating_a - rating_b) / 400.0))


def isTerminal(record):
    wins, losses = record
    return wins >= WINS_TO_ADVANCE or losses >= LOSSES_TO_ELIMINATE or (wins + losses) >= MAX_ROUNDS


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


def runSwissTrial(trial_ratings, rng):
    """One full group-stage trial. trial_ratings: {team_id: sampled rating}.
    Returns {team_id: (wins, losses)} final records."""
    records = {tid: (0, 0) for tid in trial_ratings}
    played_pairs = set()
    all_teams = list(trial_ratings.keys())

    for _round_num in range(MAX_ROUNDS):
        active = [tid for tid in all_teams if not isTerminal(records[tid])]
        if not active:
            break

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


def runSwissSimulation(team_ratings, num_trials, rng=None):
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
        final_records = runSwissTrial(trial_ratings, rng)
        for tid, record in final_records.items():
            outcome_counts[tid][record] += 1

    return outcome_counts


if __name__ == "__main__":
    # usage: python simulate_group_stage.py [num_trials]
    # num_trials defaults to DEFAULT_NUM_TRIALS (10,000); pass 100000 for the higher-precision
    # run. The website is expected to offer both as a user-facing choice - see TRIAL_CHOICES.
    num_trials = DEFAULT_NUM_TRIALS
    if len(sys.argv) > 1:
        num_trials = int(sys.argv[1])

    with open(localPath("team_composite_ratings.json"), "r", encoding="utf-8") as f:
        composite = json.load(f)["teams"]

    team_ratings = {
        int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
        for tid, v in composite.items()
    }

    print(f"=== Running {num_trials} Swiss group-stage simulations ===")
    for tid, params in sorted(team_ratings.items(), key=lambda kv: -kv[1]["mean"]):
        print(f"  {TEAM_CANONICAL[tid]:16s} mean={params['mean']:.1f} sigma={params['sigma']:.1f}")

    rng = random.Random(42)
    outcomes = runSwissSimulation(team_ratings, num_trials, rng)

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

    # default trial count keeps the original filename (backward compatible); any other
    # trial count (e.g. the 100,000-trial high-precision run) gets its own suffixed file,
    # so both scales can coexist on disk for the website to offer as a choice.
    out_filename = "group_stage_simulation_results.json" if num_trials == DEFAULT_NUM_TRIALS else f"group_stage_simulation_results_{num_trials}.json"
    with open(localPath(out_filename), "w", encoding="utf-8") as f:
        json.dump({
            "_meta": {"num_trials": num_trials, "max_rounds": MAX_ROUNDS, "wins_to_advance": WINS_TO_ADVANCE, "losses_to_eliminate": LOSSES_TO_ELIMINATE},
            "teams": results,
        }, f, ensure_ascii=False, indent=4)

    print(f"\nSaved prediction/{out_filename}")
