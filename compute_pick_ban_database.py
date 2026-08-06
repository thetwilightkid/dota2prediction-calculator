import json
import os
from datetime import datetime, timezone

from team_config import TEAM_CANONICAL, PLAYER_TO_TEAM
import weighting
from weighting import recencyWeight as _recencyWeight, tierWeight as _tierWeight

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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
supplementary_matches = loadJson(localPath("supplementary_matches.json"), {})
league_tiers = loadJson(localPath("league_tiers.json"), {})
hero_names = loadJson(localPath("hero_names.json"), {})
player_recent_heroes = loadJson(localPath("player_recent_heroes.json"), {})

NOW_TS = datetime.now(timezone.utc).timestamp()


def recencyWeight(start_time):
    return _recencyWeight(start_time, NOW_TS)


def tierWeight(league_id):
    return _tierWeight(league_id, league_tiers)


def heroName(hero_id):
    return hero_names.get(str(hero_id), f"hero_{hero_id}")


def newTeamBucket():
    return {
        "picks": {},   # hero_id -> {weighted_pick_count, raw_pick_count, weighted_wins}
        "bans_made": {},  # hero_id -> {weighted_count, raw_count}
        "bans_against": {},  # hero_id -> {weighted_count, raw_count, by_opponent: {team_id: raw_count}}
    }


team_data = {tid: newTeamBucket() for tid in TEAM_CANONICAL}


def recordPick(bucket, hero_id, weight, won):
    entry = bucket["picks"].setdefault(hero_id, {"weighted_pick_count": 0.0, "raw_pick_count": 0, "weighted_wins": 0.0})
    entry["weighted_pick_count"] += weight
    entry["raw_pick_count"] += 1
    if won:
        entry["weighted_wins"] += weight


def recordBanMade(bucket, hero_id, weight):
    entry = bucket["bans_made"].setdefault(hero_id, {"weighted_count": 0.0, "raw_count": 0})
    entry["weighted_count"] += weight
    entry["raw_count"] += 1


def recordBanAgainst(bucket, hero_id, weight, opponent_team_id):
    entry = bucket["bans_against"].setdefault(hero_id, {"weighted_count": 0.0, "raw_count": 0, "by_opponent": {}})
    entry["weighted_count"] += weight
    entry["raw_count"] += 1
    opp_key = str(opponent_team_id)
    entry["by_opponent"][opp_key] = entry["by_opponent"].get(opp_key, 0) + 1


def processMatchSide(picks_bans, side_team, weight, our_team_id, opponent_team_id, won):
    """side_team: 0 (radiant) or 1 (dire) - the picks_bans 'team' value for OUR team."""
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
            recordPick(bucket, hero_id, weight, won)
        else:
            recordBanMade(bucket, hero_id, weight)

    # opponent's bans, attributed to us as "banned against"
    opponent_side = 1 - side_team
    for pb in picks_bans:
        if pb.get("team") != opponent_side:
            continue
        if pb.get("is_pick"):
            continue
        hero_id = pb.get("hero_id")
        if hero_id is None or hero_id < 0:
            continue
        recordBanAgainst(bucket, hero_id, weight, opponent_team_id)


# ---- Mode A: league/tournament draft data ----
skipped_no_pb = 0
for m in h2h_matches.values():
    picks_bans = m.get("picks_bans")
    if not picks_bans:
        skipped_no_pb += 1
        continue
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))
    radiant_win = bool(m.get("radiant_win"))

    if m.get("radiant_roster_valid"):
        processMatchSide(picks_bans, 0, w, m["radiant_team_id"], m["dire_team_id"], radiant_win)
    if m.get("dire_roster_valid"):
        processMatchSide(picks_bans, 1, w, m["dire_team_id"], m["radiant_team_id"], not radiant_win)

for m in supplementary_matches.values():
    if not m.get("our_roster_valid"):
        continue
    picks_bans = m.get("picks_bans")
    if not picks_bans:
        skipped_no_pb += 1
        continue
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))
    is_radiant = m.get("is_radiant")
    our_side = 0 if is_radiant else 1
    won = bool(m.get("radiant_win")) if is_radiant else not bool(m.get("radiant_win"))
    processMatchSide(picks_bans, our_side, w, m["team_id"], m["opponent_team_id"], won)

print(f"=== Mode A: league draft data (picks_bans missing on {skipped_no_pb} matches, skipped) ===")

league_data_mode = {}
for tid, name in TEAM_CANONICAL.items():
    bucket = team_data[tid]

    picks_out = {}
    for hero_id, v in bucket["picks"].items():
        win_rate = v["weighted_wins"] / v["weighted_pick_count"] if v["weighted_pick_count"] > 0 else None
        picks_out[str(hero_id)] = {
            "hero_name": heroName(hero_id),
            "weighted_pick_count": round(v["weighted_pick_count"], 3),
            "raw_pick_count": v["raw_pick_count"],
            "weighted_wins": round(v["weighted_wins"], 3),
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
        }

    bans_made_out = {}
    for hero_id, v in bucket["bans_made"].items():
        bans_made_out[str(hero_id)] = {
            "hero_name": heroName(hero_id),
            "weighted_count": round(v["weighted_count"], 3),
            "raw_count": v["raw_count"],
        }

    bans_against_out = {}
    for hero_id, v in bucket["bans_against"].items():
        bans_against_out[str(hero_id)] = {
            "hero_name": heroName(hero_id),
            "weighted_count": round(v["weighted_count"], 3),
            "raw_count": v["raw_count"],
            "by_opponent": {
                opp_id: {"team_name": TEAM_CANONICAL.get(int(opp_id), f"team_{opp_id}"), "raw_count": cnt}
                for opp_id, cnt in v["by_opponent"].items()
            },
        }

    league_data_mode[str(tid)] = {
        "team_name": name,
        "picks": picks_out,
        "bans_made": bans_made_out,
        "bans_against": bans_against_out,
    }

    top_picks = sorted(bucket["picks"].items(), key=lambda kv: -kv[1]["weighted_pick_count"])[:TOP_N_DISPLAY]
    top_banned_against = sorted(bucket["bans_against"].items(), key=lambda kv: -kv[1]["weighted_count"])[:TOP_N_DISPLAY]

    print(f"\n  {name}")
    print(f"    top picks: " + ", ".join(
        f"{heroName(hid)} ({wr:.0%} wr, n={v['raw_pick_count']})" if (wr := (v['weighted_wins'] / v['weighted_pick_count'] if v['weighted_pick_count'] > 0 else None)) is not None else f"{heroName(hid)} (n={v['raw_pick_count']})"
        for hid, v in top_picks
    ))
    print(f"    top banned against them: " + ", ".join(f"{heroName(hid)} (n={v['raw_count']})" for hid, v in top_banned_against))


# ---- Mode B: individual player recent-hero history rolled up to team ----
print("\n=== Mode B: player-history rollup ===")
player_history_mode = {str(tid): {"team_name": name, "players": {}} for tid, name in TEAM_CANONICAL.items()}

for player_name, entry in player_recent_heroes.items():
    tid = PLAYER_TO_TEAM.get(player_name)
    if tid is None or tid not in TEAM_CANONICAL:
        continue
    player_history_mode[str(tid)]["players"][player_name] = {
        "account_id": entry.get("account_id"),
        "top5_recent": entry.get("top5_recent"),
        "top5_by_volume": entry.get("top5_by_volume"),
    }

for tid, name in TEAM_CANONICAL.items():
    players = player_history_mode[str(tid)]["players"]
    print(f"  {name}: {len(players)}/5 players resolved")


with open(localPath("team_pick_ban_stats.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "league_data_mode: decayed/tier-weighted picks & bans from actual tracked tournament "
                "matches (h2h_matches.json + supplementary_matches.json), split by team. bans_against[hero] "
                "= how often opponents ban that hero specifically against this team, broken down by which "
                "opponent did it (by_opponent). player_history_mode: independent rollup of each team's 5 "
                "players' most-recent hero history (player_recent_heroes.json) - reflects individual comfort "
                "picks, not necessarily what shows up in the team's actual tournament drafts."
            ),
            "recency_old_cutoff": weighting.RECENCY_OLD_CUTOFF.isoformat(),
            "recency_breakpoint": weighting.RECENCY_BREAKPOINT.isoformat(),
            "recency_weights": {"old_floor": weighting.OLD_FLOOR_WEIGHT, "breakpoint": weighting.BREAKPOINT_WEIGHT, "full": weighting.FULL_WEIGHT},
        },
        "league_data_mode": league_data_mode,
        "player_history_mode": player_history_mode,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_pick_ban_stats.json")
