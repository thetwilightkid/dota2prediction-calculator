"""Full scouting report for all C(8,2)=28 possible pairings among the 8 real
TI2026 playoff teams. Each side's profile is now split into two eras -
pre-International (everything before the real Group Stage) and Group Stage
(the 109 real TI2026 games) - each with its own picks/bans/bans-against-
opponent/comeback-choke/draft stats, plus each team's players' own most-
picked heroes in that era. Run this AFTER refreshing team_h2h_grid.json,
team_pick_ban_stats_pretournament.json, and team_pick_ban_stats_group_stage.json.

Run: python compute_playoff_scouting.py
"""

import itertools
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from team_config import TEAM_CANONICAL, PLAYER_TO_TEAM
from playoff_teams import PLAYOFF_TEAM_IDS
from simulate_group_stage import winProbability

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOP_N = 10
TOP_N_PLAYER = 6


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


h2h_grid = loadJson(localPath("team_h2h_grid.json"), {}).get("pairs", {})
pretour_pick_ban = loadJson(localPath("team_pick_ban_stats_pretournament.json"), {}).get("teams", {})
gs_pick_ban = loadJson(localPath("team_pick_ban_stats_group_stage.json"), {}).get("teams", {})
pretour_stability = loadJson(localPath("team_stability_scores.json"), {}).get("teams", {})
gs_stability = loadJson(localPath("team_stability_scores_group_stage.json"), {}).get("teams", {})
composite = loadJson(localPath("team_composite_ratings.json"), {}).get("teams", {})
gs_player_stats = loadJson(localPath("player_group_stage_stats.json"), {}).get("players", {})
player_recent_heroes = loadJson(localPath("player_recent_heroes.json"), {})

team_ratings = {
    int(tid): {"mean": v["rating_scale_mean"], "sigma": v["rating_scale_sigma"]}
    for tid, v in composite.items()
}

# account_id -> player_name, built from player_group_stage_stats.json (already
# resolved this session) - used to find each team's roster's pre-International
# hero pool in player_recent_heroes.json (keyed by player name, not account_id).
account_to_name = {int(aid): v["player_name"] for aid, v in gs_player_stats.items()}
team_to_players = {}
for player_name, tid in PLAYER_TO_TEAM.items():
    team_to_players.setdefault(tid, []).append(player_name)


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
        if entry["team_a"] == team_a:
            h2h_pred = entry.get("team_a_decayed_win_rate")
        else:
            h2h_pred = entry.get("team_b_decayed_win_rate")

    if h2h_pred is not None:
        return h2h_pred, "h2h", h2h_pred, elo_pred
    return elo_pred, "elo", h2h_pred, elo_pred


def topPicks(team_drafts, n=TOP_N):
    if not team_drafts:
        return []
    items = sorted(team_drafts.get("picks", {}).items(), key=lambda kv: -kv[1]["pick_count"])[:n]
    return [{"hero_id": int(hid), **v} for hid, v in items]


def topBansMade(team_drafts, n=TOP_N):
    if not team_drafts:
        return []
    items = sorted(team_drafts.get("bans_made", {}).items(), key=lambda kv: -kv[1]["count"])[:n]
    return [{"hero_id": int(hid), **v} for hid, v in items]


def bansAgainstOpponent(team_drafts, opponent_id, n=TOP_N):
    if not team_drafts:
        return []
    bucket = team_drafts.get("bans_against", {})
    opp_key = str(opponent_id)
    entries = []
    for hero_id, v in bucket.items():
        count = v.get("by_opponent", {}).get(opp_key, {}).get("count")
        if count:
            entries.append({"hero_id": int(hero_id), "hero_name": v["hero_name"], "count": count})
    entries.sort(key=lambda e: -e["count"])
    return entries[:n]


MIN_PICKS_FOR_BAN_TARGET = 2  # ignore one-off picks - too little signal to call them a "threat"


def probableBanTargets(opponent_drafts, n=TOP_N):
    """Heroes the OPPONENT leaned on this Group Stage that a team facing them
    would want to consider banning - independent of whether these two teams
    have actually played each other (unlike bans_against_this_opponent, which
    only shows bans that already happened in a real match between them, and
    can be empty if they never met). Ranked by threat_score = pick_rate *
    win_rate, so a hero that's both commonly picked AND winning for them
    ranks above one that's just frequently picked or just high-win-rate on a
    tiny sample - both signals are still shown per entry so it's not a black
    box. This is purely informative alongside bans_against_this_opponent, not
    a replacement for it."""
    if not opponent_drafts:
        return []
    entries = []
    for hero_id, v in opponent_drafts.get("picks", {}).items():
        if v["pick_count"] < MIN_PICKS_FOR_BAN_TARGET or v.get("win_rate") is None:
            continue
        threat_score = v["pick_rate"] * v["win_rate"]
        entries.append({
            "hero_id": int(hero_id),
            "hero_name": v["hero_name"],
            "pick_count": v["pick_count"],
            "pick_rate": v["pick_rate"],
            "win_rate": v["win_rate"],
            "threat_score": round(threat_score, 4),
        })
    entries.sort(key=lambda e: -e["threat_score"])
    return entries[:n]


def teamPlayerPretournamentPicks(team_id):
    """Each roster player's own recent hero pool (from player_recent_heroes.json,
    top5_recent - any match type, not draft-attributed, since this predates the
    Group Stage entirely and reflects individual comfort picks going into it)."""
    out = []
    for player_name in team_to_players.get(team_id, []):
        entry = player_recent_heroes.get(player_name)
        if not entry:
            continue
        top5 = entry.get("top5_recent") or []
        out.append({
            "player_name": player_name,
            "top_picks": [
                {
                    "hero_id": h["hero_id"],
                    "hero_name": h["hero"],
                    "games": h["games"],
                    "win_rate": round(h["win"] / h["games"], 4) if h["games"] else None,
                }
                for h in top5[:TOP_N_PLAYER]
            ],
        })
    return out


def teamPlayerGroupStagePicks(team_id):
    """Each roster player's own most-played heroes across their real Group
    Stage games (from player_group_stage_stats.json's top_picks, already
    scoped to actual TI2026 competitive games)."""
    out = []
    for account_id, p in gs_player_stats.items():
        if p.get("team_id") != team_id:
            continue
        out.append({
            "player_name": p["player_name"],
            "games_played": p["games_played"],
            "top_picks": p.get("top_picks", [])[:TOP_N_PLAYER],
        })
    out.sort(key=lambda p: -p["games_played"])
    return out


def eraProfile(team_id, opponent_id, pick_ban_source, stability_source, player_picks_fn, opponent_drafts_for_ban_targets=None):
    team_drafts = pick_ban_source.get(str(team_id))
    team_stab = stability_source.get(str(team_id), {})
    profile = {
        "games": team_drafts.get("games", 0) if team_drafts else 0,
        "top_picks": topPicks(team_drafts),
        "top_bans_made": topBansMade(team_drafts),
        "bans_against_this_opponent": bansAgainstOpponent(team_drafts, opponent_id),
        "comeback_rate": team_stab.get("comeback_rate"),
        "choke_rate": team_stab.get("choke_rate"),
        "draft_favored_win_rate": team_stab.get("draft_favored_win_rate"),
        "draft_underdog_win_rate": team_stab.get("draft_underdog_win_rate"),
        "avg_draft_stage_win_rate": team_stab.get("avg_draft_stage_win_rate"),
        "player_picks": player_picks_fn(team_id),
    }
    if opponent_drafts_for_ban_targets is not None:
        # "probable ban targets" for THIS team, informed by the OPPONENT's Group
        # Stage picks - only meaningful for the group_stage era (see
        # probableBanTargets's docstring), so pretournament calls omit this arg
        # entirely and the field is left off rather than populated with None.
        profile["probable_ban_targets"] = probableBanTargets(opponent_drafts_for_ban_targets)
    return profile


def teamProfile(team_id, opponent_id):
    return {
        "team_id": team_id,
        "team_name": TEAM_CANONICAL.get(team_id, f"team_{team_id}"),
        "pretournament": eraProfile(team_id, opponent_id, pretour_pick_ban, pretour_stability, teamPlayerPretournamentPicks),
        "group_stage": eraProfile(
            team_id, opponent_id, gs_pick_ban, gs_stability, teamPlayerGroupStagePicks,
            opponent_drafts_for_ban_targets=gs_pick_ban.get(str(opponent_id)),
        ),
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
                "elo_predicted_a are always both included regardless of which was chosen. team_a_profile/"
                "team_b_profile are each split into 'pretournament' and 'group_stage' eras - separate picks, "
                "bans made, bans made specifically against this opponent, comeback/choke/draft-stage rates, "
                "and each roster player's own most-picked heroes in that era. pretournament stability numbers "
                "come from team_stability_scores.json, which (as documented there) only contains matches with "
                "a Stratz predicted-win-rate curve - none of the 109 real Group Stage matches have one, so that "
                "file is already exclusively pre-International in practice. group_stage stability numbers come "
                "from team_stability_scores_group_stage.json (derived from OpenDota's own comeback field "
                "instead, since Stratz has no curves for these matches). Every hero pick/ban entry in both eras "
                "carries both a raw count and a rate (see team_pick_ban_stats_pretournament.json / "
                "team_pick_ban_stats_group_stage.json for the exact denominators). group_stage.probable_ban_targets "
                "is a separate, purely informative signal - independent of bans_against_this_opponent (which only "
                "reflects bans that already happened in a real match between these two teams, and can be empty if "
                "they never met): it's the OPPONENT's own Group Stage picks, ranked by pick_rate*win_rate, i.e. "
                "'heroes this opponent leaned on and won with, that you might want to consider banning' - not a "
                "replacement for the actual-history list, just an additional angle."
            ),
            "playoff_team_ids": PLAYOFF_TEAM_IDS,
            "pairing_count": len(pairings_out),
        },
        "pairings": pairings_out,
    }, f, ensure_ascii=False, indent=4)

print(f"\nSaved prediction/playoff_scouting_report.json ({len(pairings_out)} pairings)")
