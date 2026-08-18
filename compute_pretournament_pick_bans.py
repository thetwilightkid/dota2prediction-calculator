"""Isolated (pre-International-only) draft stats: the exact complement of
compute_group_stage_pick_bans.py - every roster-valid h2h match EXCEPT the
109 real TI2026 Group Stage games. Needs no new data collection (h2h_matches.json
already has picks_bans for all ~1900 tracked matches); this is a pure local
re-aggregation over the existing file, same shared logic as the Group Stage
script (see isolated_pick_bans.py) so both buckets stay directly comparable.

Run: python compute_pretournament_pick_bans.py
"""

import json
import os

from team_config import TEAM_CANONICAL
from isolated_pick_bans import computeIsolatedPickBans

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

pretournament_matches = [m for m in h2h_matches.values() if m.get("league_id") != GROUP_STAGE_LEAGUE_ID]
print(f"=== Isolating {len(pretournament_matches)} pre-International matches out of {len(h2h_matches)} total h2h matches ===")

teams_out, skipped_no_pb = computeIsolatedPickBans(pretournament_matches, hero_names)
print(f"(picks_bans missing on {skipped_no_pb} pre-International matches, skipped)\n")

for tid, name in TEAM_CANONICAL.items():
    t = teams_out[str(tid)]
    if not t["picks"]:
        continue
    top_picks = sorted(t["picks"].items(), key=lambda kv: -kv[1]["pick_count"])[:TOP_N_DISPLAY]
    print(f"  {name} ({t['games']} games)")
    print("    top picks: " + ", ".join(f"{v['hero_name']} (n={v['pick_count']}, {v['pick_rate']:.0%})" for _, v in top_picks))

with open(localPath("team_pick_ban_stats_pretournament.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Same picks/bans_made/bans_against shape as team_pick_ban_stats.json, but computed ONLY from "
                "matches BEFORE TI2026's Group Stage (everything except league_id 19719) - raw unweighted "
                "counts. Each hero entry carries both a raw count and a rate (count / team's games in this "
                "bucket). Complementary to team_pick_ban_stats_group_stage.json; together they partition the "
                "same underlying h2h_matches.json with no overlap."
            ),
            "group_stage_league_id": GROUP_STAGE_LEAGUE_ID,
            "matches_included": len(pretournament_matches),
        },
        "teams": teams_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_pick_ban_stats_pretournament.json")
