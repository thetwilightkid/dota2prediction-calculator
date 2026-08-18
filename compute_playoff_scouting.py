"""Full scouting report for all C(8,2)=28 possible pairings among the 8 real
TI2026 playoff teams: predicted win probability, top picks/bans, bans made
specifically against a given opponent, and comeback/choke/draft-stage
context. Run this AFTER refreshing team_h2h_grid.json and
team_pick_ban_stats.json (compute_h2h_grid.py / compute_pick_ban_database.py)
so the numbers include the real Group Stage matches.

Run: python compute_playoff_scouting.py
"""

import itertools
import json
import os

from team_config import TEAM_CANONICAL
from playoff_teams import PLAYOFF_TEAM_IDS
from simulate_group_stage import winProbability

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOP_N = 10


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


h2h_grid = loadJson(localPath("team_h2h_grid.json"), {}).get("pairs", {})
pick_ban = loadJson(localPath("team_pick_ban_stats.json"), {}).get("league_data_mode", {})
stability = loadJson(localPath("team_stability_scores.json"), {}).get("teams", {})
composite = loadJson(localPath("team_composite_ratings.json"), {}).get("teams", {})

team_ratings = {
    int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
    for tid, v in composite.items()
}


def pairKey(a, b):
    lo, hi = min(a, b), max(a, b)
    return f"{lo}_{hi}"


def winProbabilityFromMean(a, b):
    return winProbability(team_ratings[a]["mean"], team_ratings[b]["mean"])


def predictedWinProbability(team_a, team_b):
    """Returns (predicted_win_probability_for_a, predicted_source, h2h_predicted_for_a, elo_predicted_for_a)."""
    elo_pred = round(winProbabilityFromMean(team_a, team_b), 4)

    entry = h2h_grid.get(pairKey(team_a, team_b))
    h2h_pred = None
    if entry and not entry.get("never_played") and entry.get("matches_played", 0) >= 3:
        # pairs are stored with a canonical team_a/team_b (min/max ordering) -
        # figure out which side of the stored entry corresponds to our team_a.
        if entry["team_a"] == team_a:
            h2h_pred = entry.get("team_a_decayed_win_rate")
        else:
            h2h_pred = entry.get("team_b_decayed_win_rate")

    if h2h_pred is not None:
        return h2h_pred, "h2h", h2h_pred, elo_pred
    return elo_pred, "elo", h2h_pred, elo_pred


def topEntries(bucket, sort_field, n=TOP_N):
    items = sorted(bucket.items(), key=lambda kv: -kv[1].get(sort_field, 0))[:n]
    return [{"hero_id": int(hid), **v} for hid, v in items]


def bansAgainstOpponent(team_id, opponent_id):
    """Invert bans_against[hero].by_opponent[opponent] into a ranked list:
    heroes this team has banned specifically when facing this opponent."""
    bucket = pick_ban.get(str(team_id), {}).get("bans_against", {})
    opp_key = str(opponent_id)
    entries = []
    for hero_id, v in bucket.items():
        count = v.get("by_opponent", {}).get(opp_key, {}).get("raw_count")
        if count:
            entries.append({"hero_id": int(hero_id), "hero_name": v["hero_name"], "raw_count": count})
    entries.sort(key=lambda e: -e["raw_count"])
    return entries


def teamProfile(team_id, opponent_id):
    team_pb = pick_ban.get(str(team_id), {"picks": {}, "bans_made": {}, "bans_against": {}})
    team_stab = stability.get(str(team_id), {})
    return {
        "team_id": team_id,
        "team_name": TEAM_CANONICAL.get(team_id, f"team_{team_id}"),
        "top_picks": topEntries(team_pb["picks"], "weighted_pick_count"),
        "top_bans_made": topEntries(team_pb["bans_made"], "weighted_count"),
        "bans_against_this_opponent": bansAgainstOpponent(team_id, opponent_id),
        "comeback_rate": team_stab.get("comeback_rate"),
        "choke_rate": team_stab.get("choke_rate"),
        "draft_favored_win_rate": team_stab.get("draft_favored_win_rate"),
        "draft_underdog_win_rate": team_stab.get("draft_underdog_win_rate"),
        "avg_draft_stage_win_rate": team_stab.get("avg_draft_stage_win_rate"),
        "avg_volatility": team_stab.get("avg_volatility"),
    }


missing_ratings = [tid for tid in PLAYOFF_TEAM_IDS if tid not in team_ratings]
if missing_ratings:
    raise SystemExit(f"Missing composite ratings for: {[TEAM_CANONICAL[t] for t in missing_ratings]}")

pairings_out = {}
print(f"=== Building scouting report for {len(PLAYOFF_TEAM_IDS) * (len(PLAYOFF_TEAM_IDS) - 1) // 2} pairings ===\n")

for team_a, team_b in itertools.combinations(sorted(PLAYOFF_TEAM_IDS), 2):
    prob_a, source, h2h_pred, elo_pred = predictedWinProbability(team_a, team_b)
    prob_b = round(1.0 - prob_a, 4) if prob_a is not None else None

    grid_entry = h2h_grid.get(pairKey(team_a, team_b), {})
    h2h_summary = {
        "matches_played": grid_entry.get("matches_played", 0),
        "team_a_wins": grid_entry.get("team_a_wins") if grid_entry.get("team_a") == team_a else grid_entry.get("team_b_wins"),
        "team_b_wins": grid_entry.get("team_b_wins") if grid_entry.get("team_a") == team_a else grid_entry.get("team_a_wins"),
        "last_meeting": grid_entry.get("last_meeting"),
        "never_played": grid_entry.get("never_played", True),
    }

    key = pairKey(team_a, team_b)
    pairings_out[key] = {
        "team_a": team_a, "team_a_name": TEAM_CANONICAL[team_a],
        "team_b": team_b, "team_b_name": TEAM_CANONICAL[team_b],
        "predicted_win_probability_a": prob_a,
        "predicted_win_probability_b": prob_b,
        "predicted_source": source,
        "h2h_predicted_a": h2h_pred,
        "elo_predicted_a": elo_pred,
        "h2h_summary": h2h_summary,
        "team_a_profile": teamProfile(team_a, team_b),
        "team_b_profile": teamProfile(team_b, team_a),
    }

    print(f"  {TEAM_CANONICAL[team_a]:16s} vs {TEAM_CANONICAL[team_b]:16s}  "
          f"P({TEAM_CANONICAL[team_a]} wins)={prob_a:.1%} [{source}]  "
          f"h2h={h2h_summary['matches_played']} matches")

with open(localPath("playoff_scouting_report.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "All C(8,2)=28 pairings among the confirmed TI2026 playoff teams. predicted_win_probability_a "
                "uses team_h2h_grid.json's decayed_win_rate when the pair has real head-to-head history "
                "(never_played=false, matches_played>=3), falling back to the Elo-style winProbability() over "
                "team_composite_ratings.json otherwise (predicted_source records which). h2h_predicted_a/"
                "elo_predicted_a are always both included regardless of which was chosen, for comparison. "
                "team_a_profile/team_b_profile hold each side's top picks/bans (from team_pick_ban_stats.json), "
                "bans_against_this_opponent (a newly-computed inversion: which heroes this team has banned "
                "specifically when facing this exact opponent, from bans_against[hero].by_opponent), and "
                "team-level (not pairing-specific) comeback/choke/draft-stage rates from team_stability_scores.json."
            ),
            "playoff_team_ids": PLAYOFF_TEAM_IDS,
            "pairing_count": len(pairings_out),
        },
        "pairings": pairings_out,
    }, f, ensure_ascii=False, indent=4)

print(f"\nSaved prediction/playoff_scouting_report.json ({len(pairings_out)} pairings)")
