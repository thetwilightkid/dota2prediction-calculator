"""Monte Carlo simulator for the real TI2026 playoff bracket (Aug 20-23):
double-elimination, 8 teams, 14 matches, best-of-3 throughout except a
best-of-5 Grand Final, no bracket reset. Mirrors simulate_group_stage.py's
conventions (winProbability() reused verbatim, random.Random seeding,
rng.gauss(mean, sigma) per-trial rating sampling, num_trials defaults to
1,000,000, _meta + teams JSON output keyed by team_id string).

Run: python simulate_playoffs.py [num_trials]
"""

import json
import os
import random
import sys
from collections import Counter

from team_config import TEAM_CANONICAL
from playoff_teams import PLAYOFF_TEAM_IDS, UB_R1_PAIRINGS
from simulate_group_stage import winProbability

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NUM_TRIALS = 1_000_000

# The 14-match bracket, encoded as data (not branching code), matching this
# project's existing convention (PODDED_ROUNDS/DECIDER_ROUND in
# simulate_group_stage.py) of naming round/bracket shape rather than
# scattering conditionals. "winner_to"/"loser_to" are "{match_id}:{slot}"
# strings identifying which slot of a later match this one's winner/loser
# feeds into - None means "feeds no further match" (the Grand Final winner).
#
# Routing (independently re-verified against the real bracket graphic):
#   UB R2: winner(ub_r1_1) vs winner(ub_r1_2) -> "E" (ub_r2_1)
#          winner(ub_r1_3) vs winner(ub_r1_4) -> "F" (ub_r2_2)
#   UB Final: winner(E) vs winner(F) -> "G" (ub_final) - loser drops to LB Final
#   LB R1: loser(ub_r1_1) vs loser(ub_r1_2) -> L1 (lb_r1_1)
#          loser(ub_r1_3) vs loser(ub_r1_4) -> L2 (lb_r1_2)
#   LB R2: loser(F) vs winner(L1); loser(E) vs winner(L2)
#   LB R3: winners of LB R2 face each other
#   LB Final: loser(G) vs winner(LB R3)
#   Grand Final: winner(G) vs winner(LB Final), best-of-5
BRACKET_MATCHES = {
    "ub_r1_1": {"best_of": 3, "winner_to": "ub_r2_1:a", "loser_to": "lb_r1_1:a"},
    "ub_r1_2": {"best_of": 3, "winner_to": "ub_r2_1:b", "loser_to": "lb_r1_1:b"},
    "ub_r1_3": {"best_of": 3, "winner_to": "ub_r2_2:a", "loser_to": "lb_r1_2:a"},
    "ub_r1_4": {"best_of": 3, "winner_to": "ub_r2_2:b", "loser_to": "lb_r1_2:b"},

    "ub_r2_1": {"best_of": 3, "winner_to": "ub_final:a", "loser_to": "lb_r2_2:a"},   # E
    "ub_r2_2": {"best_of": 3, "winner_to": "ub_final:b", "loser_to": "lb_r2_1:a"},   # F

    "lb_r1_1": {"best_of": 3, "winner_to": "lb_r2_1:b", "loser_to": None},  # L1
    "lb_r1_2": {"best_of": 3, "winner_to": "lb_r2_2:b", "loser_to": None},  # L2

    "ub_final": {"best_of": 3, "winner_to": "grand_final:a", "loser_to": "lb_final:b"},  # G

    "lb_r2_1": {"best_of": 3, "winner_to": "lb_r3:a", "loser_to": None},
    "lb_r2_2": {"best_of": 3, "winner_to": "lb_r3:b", "loser_to": None},

    "lb_r3": {"best_of": 3, "winner_to": "lb_final:a", "loser_to": None},

    "lb_final": {"best_of": 3, "winner_to": "grand_final:b", "loser_to": None},

    "grand_final": {"best_of": 5, "winner_to": None, "loser_to": None},
}

# Fixed topological order - every match's dependencies are resolved by the
# time it's processed. UB R1 slots are seeded directly from UB_R1_PAIRINGS
# before this loop starts; every other match's slots are filled by an
# earlier match's winner_to/loser_to.
MATCH_ORDER = [
    "ub_r1_1", "ub_r1_2", "ub_r1_3", "ub_r1_4",
    "ub_r2_1", "ub_r2_2", "lb_r1_1", "lb_r1_2",
    "ub_final", "lb_r2_1", "lb_r2_2",
    "lb_r3",
    "lb_final",
    "grand_final",
]

# A team's *last* appearance in MATCH_ORDER determines its fate: winning
# grand_final means champion, losing it means runner_up, losing anything else
# means eliminated at that lower-bracket stage (a team can never be
# "eliminated" by losing a upper-bracket match - it simply drops to the
# corresponding LB match and keeps playing).
ELIMINATION_LABEL = {
    "lb_r1_1": "eliminated_lb_r1", "lb_r1_2": "eliminated_lb_r1",
    "lb_r2_1": "eliminated_lb_r2", "lb_r2_2": "eliminated_lb_r2",
    "lb_r3": "eliminated_lb_r3",
    "lb_final": "eliminated_lb_final",
}


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def playSeries(rating_a, rating_b, best_of, rng):
    """Simulates individual games (not a single coin flip) until one side
    reaches best_of//2 + 1 wins. Returns True if side A wins the series."""
    wins_needed = best_of // 2 + 1
    p_a = winProbability(rating_a, rating_b)
    wins_a = wins_b = 0
    while wins_a < wins_needed and wins_b < wins_needed:
        if rng.random() < p_a:
            wins_a += 1
        else:
            wins_b += 1
    return wins_a > wins_b


def runBracketTrial(trial_ratings, rng, forced_ub_r1):
    """One full playoff bracket trial. trial_ratings: {team_id: sampled
    rating}. forced_ub_r1: the 4 real UB R1 pairings (team_a, team_b) - every
    trial uses these directly, mirroring how simulate_group_stage.py forces
    the real announced Day 1 pairings rather than approximating them.
    Returns {match_id: {"a", "b", "winner", "loser", "best_of"}}."""
    slot_fill = {}
    for i, (a, b) in enumerate(forced_ub_r1, start=1):
        slot_fill[f"ub_r1_{i}:a"] = a
        slot_fill[f"ub_r1_{i}:b"] = b

    results = {}
    for match_id in MATCH_ORDER:
        spec = BRACKET_MATCHES[match_id]
        team_a = slot_fill[f"{match_id}:a"]
        team_b = slot_fill[f"{match_id}:b"]
        a_wins = playSeries(trial_ratings[team_a], trial_ratings[team_b], spec["best_of"], rng)
        winner, loser = (team_a, team_b) if a_wins else (team_b, team_a)
        results[match_id] = {"a": team_a, "b": team_b, "winner": winner, "loser": loser, "best_of": spec["best_of"]}

        if spec["winner_to"]:
            slot_fill[spec["winner_to"]] = winner
        if spec["loser_to"]:
            slot_fill[spec["loser_to"]] = loser

    return results


def runPlayoffSimulation(team_ratings, num_trials, rng=None, forced_ub_r1=None):
    """team_ratings: {team_id: {"mean": float, "sigma": float}}. Returns
    (reach_counts, outcome_counts), both {team_id: Counter}."""
    rng = rng or random.Random()
    forced_ub_r1 = forced_ub_r1 or UB_R1_PAIRINGS
    reach_counts = {tid: Counter() for tid in team_ratings}
    outcome_counts = {tid: Counter() for tid in team_ratings}

    for _ in range(num_trials):
        trial_ratings = {tid: rng.gauss(p["mean"], p["sigma"]) for tid, p in team_ratings.items()}
        results = runBracketTrial(trial_ratings, rng, forced_ub_r1)

        for tid in team_ratings:
            appearances = [i for i, mid in enumerate(MATCH_ORDER) if tid in (results[mid]["a"], results[mid]["b"])]
            last_match = MATCH_ORDER[max(appearances)]
            won_last = results[last_match]["winner"] == tid

            ub_r1_id = next(mid for mid in ("ub_r1_1", "ub_r1_2", "ub_r1_3", "ub_r1_4") if tid in (results[mid]["a"], results[mid]["b"]))
            if results[ub_r1_id]["winner"] == tid:
                reach_counts[tid]["ub_r1_win"] += 1

            ub_r2_id = next((mid for mid in ("ub_r2_1", "ub_r2_2") if tid in (results[mid]["a"], results[mid]["b"])), None)
            if ub_r2_id and results[ub_r2_id]["winner"] == tid:
                reach_counts[tid]["ub_r2_win"] += 1

            if tid in (results["ub_final"]["a"], results["ub_final"]["b"]):
                reach_counts[tid]["ub_final_reach"] += 1
                if results["ub_final"]["winner"] == tid:
                    reach_counts[tid]["ub_final_win"] += 1

            if tid in (results["lb_final"]["a"], results["lb_final"]["b"]):
                reach_counts[tid]["lb_final_reach"] += 1

            if tid in (results["grand_final"]["a"], results["grand_final"]["b"]):
                reach_counts[tid]["grand_final_reach"] += 1
                if results["grand_final"]["winner"] == tid:
                    reach_counts[tid]["champion"] += 1

            if last_match == "grand_final":
                outcome_counts[tid]["champion" if won_last else "runner_up"] += 1
            else:
                outcome_counts[tid][ELIMINATION_LABEL[last_match]] += 1

    return reach_counts, outcome_counts


REACH_KEYS = ["ub_r1_win", "ub_r2_win", "ub_final_reach", "ub_final_win", "lb_final_reach", "grand_final_reach", "champion"]
OUTCOME_KEYS = ["eliminated_lb_r1", "eliminated_lb_r2", "eliminated_lb_r3", "eliminated_lb_final", "runner_up", "champion"]


if __name__ == "__main__":
    num_trials = DEFAULT_NUM_TRIALS
    if len(sys.argv) > 1:
        num_trials = int(sys.argv[1])

    with open(localPath("team_composite_ratings.json"), "r", encoding="utf-8") as f:
        composite = json.load(f)["teams"]

    team_ratings = {
        int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
        for tid, v in composite.items()
        if int(tid) in PLAYOFF_TEAM_IDS
    }
    missing = set(PLAYOFF_TEAM_IDS) - set(team_ratings)
    if missing:
        raise SystemExit(f"Missing composite ratings for playoff teams: {[TEAM_CANONICAL[t] for t in missing]}")

    print(f"=== Running {num_trials:,} playoff bracket simulations (UB R1 fixed to the real announced seeding) ===")
    for tid, params in sorted(team_ratings.items(), key=lambda kv: -kv[1]["mean"]):
        print(f"  {TEAM_CANONICAL[tid]:16s} mean={params['mean']:.1f} sigma={params['sigma']:.1f}")

    rng = random.Random(2026)
    reach_counts, outcome_counts = runPlayoffSimulation(team_ratings, num_trials, rng, forced_ub_r1=UB_R1_PAIRINGS)

    print("\n=== Reach %% per team (probability of being alive entering each stage) ===")
    header = "Team".ljust(16) + "".join(k.rjust(16) for k in REACH_KEYS)
    print(header)
    results = {}
    champion_total = 0.0
    for tid in sorted(team_ratings, key=lambda t: -team_ratings[t]["mean"]):
        reach = reach_counts[tid]
        outcome = outcome_counts[tid]
        reach_pct = {k: round(100.0 * reach.get(k, 0) / num_trials, 2) for k in REACH_KEYS}
        outcome_pct = {k: round(100.0 * outcome.get(k, 0) / num_trials, 2) for k in OUTCOME_KEYS}
        champion_total += reach_pct["champion"]
        row = TEAM_CANONICAL[tid].ljust(16) + "".join(f"{reach_pct[k]:5.1f}%".rjust(16) for k in REACH_KEYS)
        print(row)
        results[str(tid)] = {
            "team_name": TEAM_CANONICAL[tid],
            "reach_pct": reach_pct,
            "outcome_pct": outcome_pct,
        }
    print(f"\n  champion %% across all 8 teams sums to {champion_total:.2f}% (should be ~100%)")

    out_filename = "playoff_simulation_results.json"
    with open(localPath(out_filename), "w", encoding="utf-8") as f:
        json.dump({
            "_meta": {
                "num_trials": num_trials,
                "format": "double_elimination_8_team",
                "best_of": {"grand_final": 5, "default": 3},
                "no_bracket_reset": True,
                "ub_r1_pairings_forced": True,
                "ub_r1_pairings": [[a, b] for a, b in UB_R1_PAIRINGS],
                "bracket_routing": BRACKET_MATCHES,
                "match_order": MATCH_ORDER,
                "reach_pct_note": "Probability of being alive entering / winning each named stage. ub_r1_win/ub_r2_win/ub_final_win are P(won that specific upper-bracket match); ub_final_reach/lb_final_reach/grand_final_reach are P(played in that match, win or lose); champion is P(won the Grand Final).",
                "outcome_pct_note": "Probability of being eliminated at each specific stage (mutually exclusive, sums to ~100% per team). A team is never 'eliminated' by an upper-bracket loss - it drops to the corresponding lower-bracket match and keeps playing, so the earliest possible elimination is eliminated_lb_r1.",
            },
            "teams": results,
        }, f, ensure_ascii=False, indent=4)

    print(f"\nSaved prediction/{out_filename}")
