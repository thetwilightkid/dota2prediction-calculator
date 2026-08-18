"""Isolated (Group-Stage-only) draft stats: same picks/bans_made/bans_against
aggregation as compute_pick_ban_database.py, but the input is restricted to
the 109 real Group Stage matches instead of the full blended history. Raw
(unweighted) counts are used here rather than the recency/tier-weighted
scheme the blended file uses - all 109 matches are from the same ~week-long
event, so weighting one over another would add noise, not signal; the whole
point of this file is to show the real, isolated Group Stage draft picture.
Each hero entry carries both a count and a rate (see isolated_pick_bans.py).

Run AFTER h2h_matches.json already has the 109 real matches merged in
(see the h2h merge done earlier this session).

Run: python compute_group_stage_pick_bans.py
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

group_stage_matches = [m for m in h2h_matches.values() if m.get("league_id") == GROUP_STAGE_LEAGUE_ID]
print(f"=== Isolating {len(group_stage_matches)} Group Stage matches out of {len(h2h_matches)} total h2h matches ===")

teams_out, skipped_no_pb = computeIsolatedPickBans(group_stage_matches, hero_names)
print(f"(picks_bans missing on {skipped_no_pb} Group Stage matches, skipped)\n")

for tid, name in TEAM_CANONICAL.items():
    t = teams_out[str(tid)]
    if not t["picks"]:
        continue
    top_picks = sorted(t["picks"].items(), key=lambda kv: -kv[1]["pick_count"])[:TOP_N_DISPLAY]
    print(f"  {name} ({t['games']} games)")
    print("    top picks: " + ", ".join(f"{v['hero_name']} (n={v['pick_count']}, {v['pick_rate']:.0%})" for _, v in top_picks))

with open(localPath("team_pick_ban_stats_group_stage.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Same picks/bans_made/bans_against shape as team_pick_ban_stats.json, but computed ONLY from "
                "the 109 real TI2026 Group Stage matches (league_id 19719) - raw unweighted counts, not "
                "recency/tier-weighted, since all matches here are from the same event. Each hero entry carries "
                "both a raw count and a rate (count / team's games in this bucket). The original blended file "
                "is untouched; this is an additive, isolated view. See team_pick_ban_stats_pretournament.json "
                "for the complementary bucket."
            ),
            "group_stage_league_id": GROUP_STAGE_LEAGUE_ID,
            "matches_included": len(group_stage_matches),
        },
        "teams": teams_out,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_pick_ban_stats_group_stage.json")
