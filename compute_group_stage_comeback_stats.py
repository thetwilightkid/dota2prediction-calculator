"""Isolated (Group-Stage-only) comeback_rate/choke_rate. The existing
compute_stability_scores.py derives these from Stratz predicted_win_rates
curves, but all 109 real Group Stage matches carry predicted_win_rates=null
(Stratz had no analysis at merge time) - so today they're silently excluded
from that calculation entirely, not just unisolated.

Instead this uses OpenDota's own per-match `comeback` field (collected by
collect_group_stage_match_details.py) - the biggest gold deficit the winning
team overcame at any point in the game. If that deficit exceeds
COMEBACK_GOLD_THRESHOLD: the winner gets credit for a comeback win, and the
loser (who therefore held that same lead before losing it) gets charged a
choke loss - both signals fall out of the same single number per match.

Run AFTER collect_group_stage_match_details.py.

Run: python compute_group_stage_comeback_stats.py
"""

import json
import os

from team_config import TEAM_CANONICAL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMEBACK_GOLD_THRESHOLD = 5000  # a notable deficit-and-recovery bar, in gold


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


details = loadJson(localPath("group_stage_2026_match_details.json"), {})
if not details:
    raise SystemExit("group_stage_2026_match_details.json is empty - run collect_group_stage_match_details.py first.")

print(f"=== Computing isolated Group Stage comeback/choke rates from {len(details)} matches ===")

team_stats = {tid: {"wins": 0, "losses": 0, "comeback_wins": 0, "choke_losses": 0, "matches_with_comeback_data": 0} for tid in TEAM_CANONICAL}

skipped_no_comeback_field = 0
for match_id, m in details.items():
    radiant_tid, dire_tid = m.get("radiant_team_id"), m.get("dire_team_id")
    if radiant_tid not in TEAM_CANONICAL or dire_tid not in TEAM_CANONICAL:
        continue
    winner_tid = radiant_tid if m.get("radiant_win") else dire_tid
    loser_tid = dire_tid if m.get("radiant_win") else radiant_tid

    team_stats[winner_tid]["wins"] += 1
    team_stats[loser_tid]["losses"] += 1

    comeback = m.get("comeback")
    if comeback is None:
        skipped_no_comeback_field += 1
        continue

    team_stats[winner_tid]["matches_with_comeback_data"] += 1
    team_stats[loser_tid]["matches_with_comeback_data"] += 1
    if comeback >= COMEBACK_GOLD_THRESHOLD:
        team_stats[winner_tid]["comeback_wins"] += 1
        team_stats[loser_tid]["choke_losses"] += 1

teams_out = {}
for tid, name in TEAM_CANONICAL.items():
    s = team_stats[tid]
    comeback_rate = round(s["comeback_wins"] / s["wins"], 4) if s["wins"] else None
    choke_rate = round(s["choke_losses"] / s["losses"], 4) if s["losses"] else None
    teams_out[str(tid)] = {
        "team_name": name,
        "group_stage_wins": s["wins"],
        "group_stage_losses": s["losses"],
        "comeback_rate": comeback_rate,
        "comeback_wins": s["comeback_wins"],
        "choke_rate": choke_rate,
        "choke_losses": s["choke_losses"],
        "matches_with_comeback_data": s["matches_with_comeback_data"],
    }
    if s["wins"] or s["losses"]:
        def fmt(x):
            return f"{x:.0%}" if x is not None else "n/a"
        print(f"  {name:16s} {s['wins']}W-{s['losses']}L  comeback_rate={fmt(comeback_rate)} ({s['comeback_wins']}/{s['wins']})  choke_rate={fmt(choke_rate)} ({s['choke_losses']}/{s['losses']})")

with open(localPath("team_stability_scores_group_stage.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Isolated (Group-Stage-only) comeback_rate/choke_rate, derived from OpenDota's own per-match "
                "`comeback` field (the winning team's biggest gold deficit overcome at any point) instead of "
                "Stratz predicted_win_rates curves (unavailable for these matches - see module docstring). "
                "comeback_rate = fraction of a team's Group Stage WINS where they overcame a deficit of at "
                "least comeback_gold_threshold gold. choke_rate = fraction of a team's Group Stage LOSSES "
                "where their opponent's comeback value crossed that same threshold - i.e. they held that "
                "lead and lost anyway. Field names match team_stability_scores.json for easy comparison, "
                "but this file's comeback_rate/choke_rate are NOT directly comparable in method to that file's."
            ),
            "comeback_gold_threshold": COMEBACK_GOLD_THRESHOLD,
            "matches_included": len(details),
            "matches_skipped_no_comeback_field": skipped_no_comeback_field,
        },
        "teams": teams_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_stability_scores_group_stage.json")
