import json
import os
from datetime import datetime, timezone

from team_config import TEAM_CANONICAL
import weighting
from weighting import recencyWeight as _recencyWeight, tierWeight as _tierWeight

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


h2h_matches = loadJson(localPath("h2h_matches.json"), {})
league_tiers = loadJson(localPath("league_tiers.json"), {})

NOW_TS = datetime.now(timezone.utc).timestamp()


def recencyWeight(start_time):
    return _recencyWeight(start_time, NOW_TS)


def tierWeight(league_id):
    return _tierWeight(league_id, league_tiers)


def newPairBucket():
    return {
        "matches_played": 0,
        "wins": {},          # team_id -> raw win count
        "weighted_wins": {},  # team_id -> decayed/tier-weighted win total
        "weighted_total": 0.0,
        "last_meeting": None,  # unix ts of most recent match
        "match_ids": [],
        "total_duration": 0,   # seconds, summed - for a simple average
    }


pairs = {}  # (min_tid, max_tid) -> bucket

for match_id, m in h2h_matches.items():
    if not (m.get("radiant_roster_valid") and m.get("dire_roster_valid")):
        continue
    a, b = m["radiant_team_id"], m["dire_team_id"]
    if a not in TEAM_CANONICAL or b not in TEAM_CANONICAL:
        continue

    key = tuple(sorted((a, b)))
    bucket = pairs.setdefault(key, newPairBucket())

    winner = a if m.get("radiant_win") else b
    loser = b if winner == a else a
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))

    bucket["matches_played"] += 1
    bucket["wins"][winner] = bucket["wins"].get(winner, 0) + 1
    bucket["wins"].setdefault(loser, bucket["wins"].get(loser, 0))
    bucket["weighted_wins"][winner] = bucket["weighted_wins"].get(winner, 0.0) + w
    bucket["weighted_wins"].setdefault(loser, bucket["weighted_wins"].get(loser, 0.0))
    bucket["weighted_total"] += w
    st = m.get("start_time")
    if st is not None and (bucket["last_meeting"] is None or st > bucket["last_meeting"]):
        bucket["last_meeting"] = st
    bucket["match_ids"].append(match_id)
    if m.get("duration"):
        bucket["total_duration"] += m["duration"]


# ---- build the pairs list (one entry per unordered pair, symmetric data) + the directional grid ----
pairs_out = {}
grid = {str(tid): {} for tid in TEAM_CANONICAL}

team_ids_sorted = sorted(TEAM_CANONICAL)
total_pairs = len(team_ids_sorted) * (len(team_ids_sorted) - 1) // 2
played_pairs = 0

for i, a in enumerate(team_ids_sorted):
    for b in team_ids_sorted[i + 1:]:
        key = (a, b)
        bucket = pairs.get(key)
        pair_key_str = f"{a}_{b}"

        if bucket is None:
            pairs_out[pair_key_str] = {
                "team_a": a, "team_a_name": TEAM_CANONICAL[a],
                "team_b": b, "team_b_name": TEAM_CANONICAL[b],
                "matches_played": 0,
                "team_a_wins": 0, "team_b_wins": 0,
                "team_a_win_rate": None, "team_b_win_rate": None,
                "team_a_decayed_win_rate": None, "team_b_decayed_win_rate": None,
                "avg_duration_seconds": None,
                "last_meeting": None,
                "never_played": True,
            }
            for row, col in ((a, b), (b, a)):
                grid[str(row)][str(col)] = {"matches_played": 0, "wins": 0, "losses": 0, "win_rate": None, "decayed_win_rate": None, "avg_duration_seconds": None, "last_meeting": None}
            continue

        played_pairs += 1
        wa, wb = bucket["wins"].get(a, 0), bucket["wins"].get(b, 0)
        wwa, wwb = bucket["weighted_wins"].get(a, 0.0), bucket["weighted_wins"].get(b, 0.0)
        total = bucket["matches_played"]
        wtotal = bucket["weighted_total"]
        last_meeting_iso = datetime.fromtimestamp(bucket["last_meeting"], tz=timezone.utc).isoformat() if bucket["last_meeting"] else None
        avg_duration = round(bucket["total_duration"] / total) if total else None

        pairs_out[pair_key_str] = {
            "team_a": a, "team_a_name": TEAM_CANONICAL[a],
            "team_b": b, "team_b_name": TEAM_CANONICAL[b],
            "matches_played": total,
            "team_a_wins": wa, "team_b_wins": wb,
            "team_a_win_rate": round(wa / total, 4) if total else None,
            "team_b_win_rate": round(wb / total, 4) if total else None,
            "team_a_decayed_win_rate": round(wwa / wtotal, 4) if wtotal > 0 else None,
            "team_b_decayed_win_rate": round(wwb / wtotal, 4) if wtotal > 0 else None,
            "avg_duration_seconds": avg_duration,
            "last_meeting": last_meeting_iso,
            "never_played": False,
        }

        grid[str(a)][str(b)] = {
            "matches_played": total, "wins": wa, "losses": wb,
            "win_rate": round(wa / total, 4) if total else None,
            "decayed_win_rate": round(wwa / wtotal, 4) if wtotal > 0 else None,
            "avg_duration_seconds": avg_duration,
            "last_meeting": last_meeting_iso,
        }
        grid[str(b)][str(a)] = {
            "matches_played": total, "wins": wb, "losses": wa,
            "win_rate": round(wb / total, 4) if total else None,
            "decayed_win_rate": round(wwb / wtotal, 4) if wtotal > 0 else None,
            "avg_duration_seconds": avg_duration,
            "last_meeting": last_meeting_iso,
        }

print(f"=== Head-to-head grid: {played_pairs}/{total_pairs} team pairs have played (roster-valid matches only) ===\n")

# quick readable print: each team's overall h2h record against the other 15
for tid in team_ids_sorted:
    row = grid[str(tid)]
    total_matches = sum(v["matches_played"] for v in row.values())
    total_wins = sum(v["wins"] for v in row.values())
    never = sum(1 for v in row.values() if v["matches_played"] == 0)
    print(f"  {TEAM_CANONICAL[tid]:16s} {total_wins:3d}W-{total_matches - total_wins:<3d}L across {total_matches} matches ({15 - never}/15 opponents played)")

with open(localPath("team_h2h_grid.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "16x16 head-to-head grid across the tracked TI2026 teams, built only from roster-verified "
                "matches (both sides' rosters confirmed via account_id, see h2h_matches.json). win_rate is a "
                "plain historical win rate; decayed_win_rate applies the same recency x tournament-tier "
                "weighting used across the rest of this project (see weighting.py: 0.1->0.5 across all of "
                "2025, 0.5->1.0 from 2026-01-01 to now) x tier weight. 'grid' is pre-shaped for direct "
                "rendering: grid[team_id][opponent_id] gives that row team's record against that column team. "
                "'pairs' holds the same data once per unordered pair for compact storage/lookup. "
                "never_played=true pairs have no tracked matches - the Monte Carlo simulation "
                "(simulate_group_stage.py) handles these via each team's rating distribution rather than this "
                "grid."
            ),
            "teams_tracked": len(TEAM_CANONICAL),
            "pairs_with_data": played_pairs,
            "pairs_total": total_pairs,
            "recency_old_cutoff": weighting.RECENCY_OLD_CUTOFF.isoformat(),
            "recency_breakpoint": weighting.RECENCY_BREAKPOINT.isoformat(),
            "recency_weights": {"old_floor": weighting.OLD_FLOOR_WEIGHT, "breakpoint": weighting.BREAKPOINT_WEIGHT, "full": weighting.FULL_WEIGHT},
        },
        "grid": grid,
        "pairs": pairs_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_h2h_grid.json")
