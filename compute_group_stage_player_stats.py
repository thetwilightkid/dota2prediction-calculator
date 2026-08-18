"""Per-player raw performance stats (KDA, GPM/XPM, wards, rune pickups),
averaged across each tracked player's real TI2026 Group Stage games only.
No file in this project persisted per-player raw stats before
collect_group_stage_match_details.py - collect_h2h_data.py already fetches
each match's full OpenDota payload but discards the players array after
pulling picks_bans/roster-match counts.

Rune pickups per game are called out specifically for mid players, since
power-rune control (the river runes that spawn every 2 minutes) is a
mid-specific skill signal - a mid player who reliably out-runes their lane
opponent has a real informational/tempo edge that raw KDA doesn't capture.

Run AFTER collect_group_stage_match_details.py.

Run: python compute_group_stage_player_stats.py
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from team_config import TEAM_CANONICAL, PLAYER_TO_TEAM
from roster_utils import resolvePlayerAccountIds

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LANE_ROLE_LABELS = {1: "safe", 2: "mid", 3: "off", 4: "jungle"}
TOP_N_HEROES = 8


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

hero_names = loadJson(localPath("hero_names.json"), {})


def heroName(hero_id):
    return hero_names.get(str(hero_id), f"hero_{hero_id}")

print("Resolving tracked player account_ids...")
name_to_account = resolvePlayerAccountIds()
account_to_player = {
    account_id: name for name, account_id in name_to_account.items() if name in PLAYER_TO_TEAM
}
print(f"Resolved {len(account_to_player)} tracked players.\n")

STAT_FIELDS = ["kills", "deaths", "assists", "gold_per_min", "xp_per_min", "last_hits", "denies",
               "obs_placed", "sen_placed", "hero_damage", "hero_healing", "tower_damage"]


def newPlayerBucket():
    return {
        "games_played": 0,
        "sums": {field: 0 for field in STAT_FIELDS},
        "games_with_rune_data": 0,
        "rune_pickups_sum": 0,
        "lane_role_counts": {},
        "hero_picks": {},  # hero_id -> {"count": int, "wins": int}
    }


players_agg = {}

matches_scanned = 0
for match_id, m in details.items():
    matches_scanned += 1
    for p in m.get("players", []):
        account_id = p.get("account_id")
        player_name = account_to_player.get(account_id)
        if player_name is None:
            continue

        bucket = players_agg.setdefault(account_id, newPlayerBucket())
        bucket["games_played"] += 1
        for field in STAT_FIELDS:
            v = p.get(field)
            if v is not None:
                bucket["sums"][field] += v

        lane_role = p.get("lane_role")
        if lane_role is not None:
            bucket["lane_role_counts"][lane_role] = bucket["lane_role_counts"].get(lane_role, 0) + 1

        rune_pickups = p.get("rune_pickups")
        if m.get("is_parsed") and rune_pickups is not None:
            bucket["games_with_rune_data"] += 1
            bucket["rune_pickups_sum"] += rune_pickups

        hero_id = p.get("hero_id")
        if hero_id is not None:
            is_radiant = p.get("isRadiant")
            won = bool(m.get("radiant_win")) if is_radiant else not bool(m.get("radiant_win"))
            entry = bucket["hero_picks"].setdefault(hero_id, {"count": 0, "wins": 0})
            entry["count"] += 1
            if won:
                entry["wins"] += 1

print(f"=== Aggregated stats for {len(players_agg)} tracked players across {matches_scanned} Group Stage matches ===\n")

players_out = {}
for account_id, bucket in players_agg.items():
    player_name = account_to_player[account_id]
    team_id = PLAYER_TO_TEAM.get(player_name)
    n = bucket["games_played"]

    avgs = {field: round(bucket["sums"][field] / n, 2) for field in STAT_FIELDS}
    kda = round((avgs["kills"] + avgs["assists"]) / max(avgs["deaths"], 1.0), 2)

    lane_role_counts = bucket["lane_role_counts"]
    primary_lane_role = max(lane_role_counts, key=lane_role_counts.get) if lane_role_counts else None

    avg_rune_pickups = round(bucket["rune_pickups_sum"] / bucket["games_with_rune_data"], 2) if bucket["games_with_rune_data"] else None

    top_picks = sorted(bucket["hero_picks"].items(), key=lambda kv: -kv[1]["count"])[:TOP_N_HEROES]
    top_picks_out = [
        {
            "hero_id": hid,
            "hero_name": heroName(hid),
            "pick_count": v["count"],
            "pick_rate": round(v["count"] / n, 4),
            "win_rate": round(v["wins"] / v["count"], 4),
        }
        for hid, v in top_picks
    ]

    players_out[str(account_id)] = {
        "player_name": player_name,
        "team_id": team_id,
        "team_name": TEAM_CANONICAL.get(team_id, f"team_{team_id}"),
        "games_played": n,
        "kda": kda,
        "avg_kills": avgs["kills"],
        "avg_deaths": avgs["deaths"],
        "avg_assists": avgs["assists"],
        "avg_gold_per_min": avgs["gold_per_min"],
        "avg_xp_per_min": avgs["xp_per_min"],
        "avg_last_hits": avgs["last_hits"],
        "avg_denies": avgs["denies"],
        "avg_obs_placed": avgs["obs_placed"],
        "avg_sen_placed": avgs["sen_placed"],
        "avg_hero_damage": avgs["hero_damage"],
        "avg_hero_healing": avgs["hero_healing"],
        "avg_tower_damage": avgs["tower_damage"],
        "primary_lane_role": LANE_ROLE_LABELS.get(primary_lane_role),
        "avg_rune_pickups": avg_rune_pickups,
        "games_with_rune_data": bucket["games_with_rune_data"],
        "top_picks": top_picks_out,
    }

for tid, team_name in TEAM_CANONICAL.items():
    roster = sorted(
        (v for v in players_out.values() if v["team_id"] == tid),
        key=lambda v: -v["games_played"],
    )
    if not roster:
        continue
    print(f"  {team_name}")
    for v in roster:
        rune_note = f", runes/g={v['avg_rune_pickups']} (mid)" if v["primary_lane_role"] == "mid" and v["avg_rune_pickups"] is not None else ""
        print(f"    {v['player_name']:16s} [{v['primary_lane_role'] or '?':6s}] n={v['games_played']:2d}  KDA={v['kda']:.2f} ({v['avg_kills']}/{v['avg_deaths']}/{v['avg_assists']})  gpm={v['avg_gold_per_min']}{rune_note}")

with open(localPath("player_group_stage_stats.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Per-player raw performance averages across each tracked player's real TI2026 Group Stage "
                "games only (109 matches). avg_rune_pickups/games_with_rune_data are computed only over games "
                "where the match was fully parsed by OpenDota (is_parsed=true) and the field was present - "
                "never silently averaged over missing data. primary_lane_role is the most common OpenDota "
                "lane_role across the player's games (1=safe, 2=mid, 3=off, 4=jungle) - power-rune control "
                "(avg_rune_pickups) is most meaningful for mid players specifically. top_picks is this player's "
                "own most-played heroes across their Group Stage games (from the actual match roster, not the "
                "team-level draft order, since picks_bans doesn't attribute a pick to a specific player)."
            ),
            "matches_scanned": matches_scanned,
            "players_resolved": len(players_out),
        },
        "players": players_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/player_group_stage_stats.json")
