"""Fetches full per-player detail for the 109 real TI2026 Group Stage matches
(collect_h2h_data.py already calls this same OpenDota endpoint for these
matches, but only extracts picks_bans/roster-match counts and discards the
rest of the payload). This script persists the full players array (raw KDA,
GPM/XPM, wards, rune pickups, etc.) plus OpenDota's own `comeback`/`stomp`
fields, which give an authoritative per-match "how big a gold deficit did the
winner overcome" signal - used by compute_group_stage_comeback_stats.py
instead of re-deriving comeback/choke from a raw gold-advantage time series.

Run: python collect_group_stage_match_details.py
"""

import json
import os
import time

from api_utils import openDotaGet, RateLimitExceeded

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


PLAYER_FIELDS = [
    "account_id", "isRadiant", "hero_id", "kills", "deaths", "assists",
    "gold_per_min", "xp_per_min", "last_hits", "denies",
    "obs_placed", "sen_placed", "hero_damage", "hero_healing", "tower_damage",
    "lane_role", "rune_pickups", "runes_log",
]

group_stage_matches = loadJson(localPath("group_stage_2026_h2h_matches.json"), {})
match_ids = sorted(group_stage_matches.keys(), key=int)
print(f"=== Fetching full player detail for {len(match_ids)} real Group Stage matches ===")

output_path = localPath("group_stage_2026_match_details.json")
details = loadJson(output_path, {})
already_done = [mid for mid in match_ids if mid in details]
to_fetch = [mid for mid in match_ids if mid not in details]
print(f"  {len(already_done)} already collected, {len(to_fetch)} to fetch\n")

for i, match_id in enumerate(to_fetch, 1):
    try:
        r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
    except RateLimitExceeded as e:
        print(f"Rate limit exhausted: {e}. Stopping, progress saved.")
        break

    if "players" not in r:
        print(f"  match {match_id}: incomplete data, skipping ({i}/{len(to_fetch)})")
        continue

    is_parsed = r.get("radiant_gold_adv") is not None
    players = []
    for p in r["players"]:
        entry = {field: p.get(field) for field in PLAYER_FIELDS}
        players.append(entry)

    details[match_id] = {
        "league_id": r.get("leagueid"),
        "duration": r.get("duration"),
        "radiant_team_id": group_stage_matches[match_id].get("radiant_team_id"),
        "dire_team_id": group_stage_matches[match_id].get("dire_team_id"),
        "radiant_win": r.get("radiant_win"),
        "comeback": r.get("comeback"),
        "stomp": r.get("stomp"),
        "is_parsed": is_parsed,
        "players": players,
    }

    if i % 10 == 0 or i == len(to_fetch):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(details, f, ensure_ascii=False, indent=4)

    parsed_note = "" if is_parsed else " [NOT PARSED - advanced fields unavailable]"
    print(f"  match {match_id}: {len(players)} players collected ({i}/{len(to_fetch)}){parsed_note}")
    time.sleep(0.5)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(details, f, ensure_ascii=False, indent=4)

parsed_count = sum(1 for d in details.values() if d.get("is_parsed"))
print(f"\n=== Done: {len(details)}/{len(match_ids)} matches collected, {parsed_count} fully parsed ===")
print(f"Saved prediction/group_stage_2026_match_details.json")
