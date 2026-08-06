import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from config import PLAYERS_LIST, PLAYER_TO_TEAM, resolveTeamId
from api_utils import openDotaGet, RateLimitExceeded

with open(os.path.join(ROOT_DIR, "heroes.json"), "r", encoding="utf-8") as f:
    heroes_data = json.load(f)


def heroName(hero_id):
    return heroes_data.get(str(hero_id), {}).get("name", f"hero_{hero_id}")


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


print("Fetching proPlayers to resolve account_ids...")
proplayers = openDotaGet("https://api.opendota.com/api/proPlayers")

candidates_by_name = {}
for p in proplayers:
    if isinstance(p, dict) and p.get("name"):
        candidates_by_name.setdefault(p["name"], []).append(p)


def pickAccount(name):
    candidates = candidates_by_name.get(name, [])
    if not candidates:
        return None, None

    expected_team = PLAYER_TO_TEAM.get(name)
    for p in candidates:
        if p.get("team_id") and resolveTeamId(p["team_id"]) == expected_team:
            return p["account_id"], "matched_team"

    best = max(candidates, key=lambda p: p.get("last_match_time") or "")
    return best["account_id"], "fallback_most_recent_activity"


player_recent_heroes = {}
unresolved = []

for i, name in enumerate(PLAYERS_LIST, 1):
    account_id, method = pickAccount(name)
    if account_id is None:
        print(f"  [{i}/{len(PLAYERS_LIST)}] {name}: no account_id found at all, skipping")
        unresolved.append(name)
        continue

    try:
        heroes = openDotaGet(f"https://api.opendota.com/api/players/{account_id}/heroes")
    except RateLimitExceeded as e:
        print(f"Rate limit exhausted: {e}. Stopping, progress saved so far.")
        break

    if not isinstance(heroes, list):
        print(f"  [{i}/{len(PLAYERS_LIST)}] {name}: failed to fetch heroes: {heroes}")
        continue

    top_recent = sorted(heroes, key=lambda h: h.get("last_played", 0), reverse=True)[:5]
    top_volume = sorted(heroes, key=lambda h: h.get("games", 0), reverse=True)[:5]

    player_recent_heroes[name] = {
        "account_id": account_id,
        "resolution_method": method,
        "top5_recent": [
            {
                "hero": heroName(h["hero_id"]),
                "hero_id": h["hero_id"],
                "last_played": h["last_played"],
                "games": h["games"],
                "win": h["win"],
            }
            for h in top_recent
        ],
        "top5_by_volume": [
            {
                "hero": heroName(h["hero_id"]),
                "hero_id": h["hero_id"],
                "games": h["games"],
                "win": h["win"],
                "last_played": h["last_played"],
            }
            for h in top_volume
        ],
    }
    print(f"  [{i}/{len(PLAYERS_LIST)}] {name}: ok ({method})")
    time.sleep(0.4)

with open(localPath("player_recent_heroes.json"), "w", encoding="utf-8") as f:
    json.dump(player_recent_heroes, f, ensure_ascii=False, indent=4)

print(f"\nDone. {len(player_recent_heroes)}/{len(PLAYERS_LIST)} players resolved.")
if unresolved:
    print(f"Unresolved (no account_id at all): {unresolved}")
