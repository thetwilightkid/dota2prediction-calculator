import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from config import PLAYERS_LIST, PLAYER_TO_TEAM, resolveTeamId
from api_utils import openDotaGet


def resolvePlayerAccountIds():
    """{player_name: account_id} for all tracked players. Disambiguates nickname
    collisions by matching each candidate's registered team_id against the
    player's known team; falls back to the most recently active candidate."""
    proplayers = openDotaGet("https://api.opendota.com/api/proPlayers")
    candidates_by_name = {}
    for p in proplayers:
        if isinstance(p, dict) and p.get("name"):
            candidates_by_name.setdefault(p["name"], []).append(p)

    result = {}
    for name in PLAYERS_LIST:
        candidates = candidates_by_name.get(name, [])
        if not candidates:
            continue
        expected_team = PLAYER_TO_TEAM.get(name)
        matched = None
        for p in candidates:
            if p.get("team_id") and resolveTeamId(p["team_id"]) == expected_team:
                matched = p
                break
        if matched is None:
            matched = max(candidates, key=lambda p: p.get("last_match_time") or "")
        result[name] = matched["account_id"]
    return result


def buildAccountToTeam():
    """{account_id: canonical_team_id} for all tracked players - the ground
    truth used to verify a match's actual roster, independent of which
    team_id the match was recorded under."""
    name_to_account = resolvePlayerAccountIds()
    return {account_id: PLAYER_TO_TEAM[name] for name, account_id in name_to_account.items()}
