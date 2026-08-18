"""Isolated (Group-Stage-only) draft stats: same picks/bans_made/bans_against
aggregation as compute_pick_ban_database.py, but the input is restricted to
the 109 real Group Stage matches instead of the full blended history. Raw
(unweighted) counts are used here rather than the recency/tier-weighted
scheme the blended file uses - all 109 matches are from the same ~week-long
event, so weighting one over another would add noise, not signal; the whole
point of this file is to show the real, isolated Group Stage draft picture.

Run AFTER h2h_matches.json already has the 109 real matches merged in
(see the h2h merge done earlier this session).

Run: python compute_group_stage_pick_bans.py
"""

import json
import os

from team_config import TEAM_CANONICAL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GROUP_STAGE_LEAGUE_ID = 19719  # same constant as compute_ratings.py
TOP_N_DISPLAY = 5


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


h2h_matches = loadJson(localPath("h2h_matches.json"), {})
hero_names = loadJson(localPath("hero_names.json"), {})

group_stage_matches = {
    mid: m for mid, m in h2h_matches.items()
    if m.get("league_id") == GROUP_STAGE_LEAGUE_ID
}
print(f"=== Isolating {len(group_stage_matches)} Group Stage matches out of {len(h2h_matches)} total h2h matches ===")


def heroName(hero_id):
    return hero_names.get(str(hero_id), f"hero_{hero_id}")


def newTeamBucket():
    return {"picks": {}, "bans_made": {}, "bans_against": {}}


team_data = {tid: newTeamBucket() for tid in TEAM_CANONICAL}


def recordPick(bucket, hero_id, won):
    entry = bucket["picks"].setdefault(hero_id, {"pick_count": 0, "wins": 0})
    entry["pick_count"] += 1
    if won:
        entry["wins"] += 1


def recordBanMade(bucket, hero_id):
    entry = bucket["bans_made"].setdefault(hero_id, {"count": 0})
    entry["count"] += 1


def recordBanAgainst(bucket, hero_id, opponent_team_id):
    entry = bucket["bans_against"].setdefault(hero_id, {"count": 0, "by_opponent": {}})
    entry["count"] += 1
    opp_key = str(opponent_team_id)
    entry["by_opponent"][opp_key] = entry["by_opponent"].get(opp_key, 0) + 1


def processMatchSide(picks_bans, side_team, our_team_id, opponent_team_id, won):
    if our_team_id not in team_data:
        return
    bucket = team_data[our_team_id]
    for pb in picks_bans:
        if pb.get("team") != side_team:
            continue
        hero_id = pb.get("hero_id")
        if hero_id is None or hero_id < 0:
            continue
        if pb.get("is_pick"):
            recordPick(bucket, hero_id, won)
        else:
            recordBanMade(bucket, hero_id)

    opponent_side = 1 - side_team
    for pb in picks_bans:
        if pb.get("team") != opponent_side or pb.get("is_pick"):
            continue
        hero_id = pb.get("hero_id")
        if hero_id is None or hero_id < 0:
            continue
        recordBanAgainst(bucket, hero_id, opponent_team_id)


skipped_no_pb = 0
for m in group_stage_matches.values():
    picks_bans = m.get("picks_bans")
    if not picks_bans:
        skipped_no_pb += 1
        continue
    radiant_win = bool(m.get("radiant_win"))
    if m.get("radiant_roster_valid"):
        processMatchSide(picks_bans, 0, m["radiant_team_id"], m["dire_team_id"], radiant_win)
    if m.get("dire_roster_valid"):
        processMatchSide(picks_bans, 1, m["dire_team_id"], m["radiant_team_id"], not radiant_win)

print(f"(picks_bans missing on {skipped_no_pb} Group Stage matches, skipped)\n")

teams_out = {}
for tid, name in TEAM_CANONICAL.items():
    bucket = team_data[tid]

    picks_out = {}
    for hero_id, v in bucket["picks"].items():
        win_rate = v["wins"] / v["pick_count"] if v["pick_count"] > 0 else None
        picks_out[str(hero_id)] = {
            "hero_name": heroName(hero_id),
            "pick_count": v["pick_count"],
            "wins": v["wins"],
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
        }

    bans_made_out = {
        str(hero_id): {"hero_name": heroName(hero_id), "count": v["count"]}
        for hero_id, v in bucket["bans_made"].items()
    }

    bans_against_out = {
        str(hero_id): {
            "hero_name": heroName(hero_id),
            "count": v["count"],
            "by_opponent": {
                opp_id: {"team_name": TEAM_CANONICAL.get(int(opp_id), f"team_{opp_id}"), "count": cnt}
                for opp_id, cnt in v["by_opponent"].items()
            },
        }
        for hero_id, v in bucket["bans_against"].items()
    }

    teams_out[str(tid)] = {
        "team_name": name,
        "picks": picks_out,
        "bans_made": bans_made_out,
        "bans_against": bans_against_out,
    }

    if picks_out or bans_made_out:
        top_picks = sorted(bucket["picks"].items(), key=lambda kv: -kv[1]["pick_count"])[:TOP_N_DISPLAY]
        print(f"  {name}")
        print(f"    top picks: " + ", ".join(f"{heroName(hid)} (n={v['pick_count']})" for hid, v in top_picks))

with open(localPath("team_pick_ban_stats_group_stage.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Same picks/bans_made/bans_against shape as team_pick_ban_stats.json, but computed ONLY from "
                "the 109 real TI2026 Group Stage matches (league_id 19719) - raw unweighted counts, not "
                "recency/tier-weighted, since all matches here are from the same event. The original blended "
                "file is untouched; this is an additive, isolated view."
            ),
            "group_stage_league_id": GROUP_STAGE_LEAGUE_ID,
            "matches_included": len(group_stage_matches),
        },
        "teams": teams_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_pick_ban_stats_group_stage.json")
