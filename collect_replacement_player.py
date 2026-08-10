"""One-off targeted fetch for a single roster swap, rather than rerunning the
full collect_player_heroes.py (which still depends on root config.py's
PLAYERS_LIST/PLAYER_TO_TEAM - out of scope to fix here). Removes the outgoing
player and adds the incoming one to player_recent_heroes.json using the exact
same shape/fields collect_player_heroes.py produces.

2026-08-07: LGD's TaiLung was permanently banned; replaced by Topson for TI2026.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

from api_utils import openDotaGet

OUTGOING_PLAYER = "TaiLung"
INCOMING_PLAYER = "Topson"
INCOMING_ACCOUNT_ID = 94054712  # confirmed via proPlayers: name="Topson", personaname="TOPSON"


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


with open(localPath("hero_names.json"), "r", encoding="utf-8") as f:
    hero_names = json.load(f)


def heroName(hero_id):
    return hero_names.get(str(hero_id), f"hero_{hero_id}")


with open(localPath("player_recent_heroes.json"), "r", encoding="utf-8") as f:
    player_recent_heroes = json.load(f)

removed = player_recent_heroes.pop(OUTGOING_PLAYER, None)
print(f"Removed {OUTGOING_PLAYER}: {'ok' if removed else 'was not present'}")

heroes = openDotaGet(f"https://api.opendota.com/api/players/{INCOMING_ACCOUNT_ID}/heroes")
if not isinstance(heroes, list):
    raise SystemExit(f"Failed to fetch heroes for {INCOMING_PLAYER}: {heroes}")

top_recent = sorted(heroes, key=lambda h: h.get("last_played", 0), reverse=True)[:5]
top_volume = sorted(heroes, key=lambda h: h.get("games", 0), reverse=True)[:5]

player_recent_heroes[INCOMING_PLAYER] = {
    "account_id": INCOMING_ACCOUNT_ID,
    "resolution_method": "manual_roster_swap",
    "top5_recent": [
        {"hero": heroName(h["hero_id"]), "hero_id": h["hero_id"], "last_played": h["last_played"], "games": h["games"], "win": h["win"]}
        for h in top_recent
    ],
    "top5_by_volume": [
        {"hero": heroName(h["hero_id"]), "hero_id": h["hero_id"], "games": h["games"], "win": h["win"], "last_played": h["last_played"]}
        for h in top_volume
    ],
}

with open(localPath("player_recent_heroes.json"), "w", encoding="utf-8") as f:
    json.dump(player_recent_heroes, f, ensure_ascii=False, indent=4)

print(f"Added {INCOMING_PLAYER} (account_id={INCOMING_ACCOUNT_ID}).")
print(f"Top 5 recent: {[h['hero'] for h in player_recent_heroes[INCOMING_PLAYER]['top5_recent']]}")
print(f"\nSaved prediction/player_recent_heroes.json ({len(player_recent_heroes)} players)")
