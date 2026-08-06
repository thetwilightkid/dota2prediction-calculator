import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import TEAM_CANONICAL
from api_utils import openDotaGet, RateLimitExceeded
from roster_utils import buildAccountToTeam

MIN_ROSTER_MATCH = 3


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


with open(localPath("h2h_matches.json"), "r", encoding="utf-8") as f:
    h2h_matches = json.load(f)


def saveAll():
    with open(localPath("h2h_matches.json"), "w", encoding="utf-8") as f:
        json.dump(h2h_matches, f, ensure_ascii=False, indent=4)


print("Resolving tracked player account_ids...")
account_to_team = buildAccountToTeam()
print(f"Resolved {len(account_to_team)} tracked players to account_ids.\n")

to_verify = [mid for mid, m in h2h_matches.items() if "radiant_roster_match" not in m]
print(f"Verifying rosters for {len(to_verify)} of {len(h2h_matches)} matches "
      f"(re-fetching OpenDota only, no Stratz call needed)...\n")

both_valid = 0
excluded = 0

for i, match_id in enumerate(to_verify, 1):
    entry = h2h_matches[match_id]
    try:
        match_r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
    except RateLimitExceeded as e:
        print(f"Rate limit exhausted: {e}. Stopping, progress saved.")
        saveAll()
        raise SystemExit(1)

    if "players" not in match_r:
        print(f"  match {match_id}: could not re-fetch players, skipping ({i}/{len(to_verify)})")
        continue

    radiant_matches = sum(
        1 for p in match_r["players"]
        if p.get("isRadiant") and account_to_team.get(p.get("account_id")) == entry["radiant_team_id"]
    )
    dire_matches = sum(
        1 for p in match_r["players"]
        if not p.get("isRadiant") and account_to_team.get(p.get("account_id")) == entry["dire_team_id"]
    )

    entry["radiant_roster_match"] = radiant_matches
    entry["dire_roster_match"] = dire_matches
    entry["radiant_roster_valid"] = radiant_matches >= MIN_ROSTER_MATCH
    entry["dire_roster_valid"] = dire_matches >= MIN_ROSTER_MATCH

    if entry["radiant_roster_valid"] and entry["dire_roster_valid"]:
        both_valid += 1
    else:
        excluded += 1
        r_name = TEAM_CANONICAL.get(entry["radiant_team_id"], "?")
        d_name = TEAM_CANONICAL.get(entry["dire_team_id"], "?")
        print(f"  match {match_id}: {r_name} ({radiant_matches}/5) vs {d_name} ({dire_matches}/5) -> roster mismatch, EXCLUDED")

    saveAll()
    if i % 100 == 0:
        print(f"  ... {i}/{len(to_verify)} verified so far")
    time.sleep(0.5)

print(f"\nDone. {both_valid} matches with both rosters verified (>={MIN_ROSTER_MATCH}/5), "
      f"{excluded} flagged as roster mismatch (should be excluded from team stats).")
