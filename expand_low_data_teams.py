import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from config import TEAM_CANONICAL, resolveTeamId
from api_utils import openDotaGet, RateLimitExceeded, stratzPost, StratzUnavailable
from roster_utils import buildAccountToTeam

# Teams outside the 16 tracked TI2026 rosters, but recognized as genuinely strong
# opponents by the external rating sources in team_ratings.json (EPT/ESL/Liquipedia/
# datdota all rank them highly). PlayTime appears under two separate registrations,
# same rebrand-fragmentation issue we've seen with our own tracked teams.
TOP_UNTRACKED_TEAM_IDS = {
    9338413: "MOUZ",
    9895392: "Virtus.pro",
    36: "Natus Vincere",
    10020555: "PlayTime",
    10207983: "PlayTime",
}

LOW_DATA_THRESHOLD = 100  # valid h2h match count below which a team gets expansion
PER_TEAM_CAP = 70
MIN_ROSTER_MATCH = 3


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


team_match_history = loadJson(localPath("team_match_history.json"), {})
h2h_matches = loadJson(localPath("h2h_matches.json"), {})
supplementary_matches = loadJson(localPath("supplementary_matches.json"), {})
processed_ids = set(loadJson(localPath("processed_supplementary_matches.json"), []))


def saveAll():
    with open(localPath("supplementary_matches.json"), "w", encoding="utf-8") as f:
        json.dump(supplementary_matches, f, ensure_ascii=False, indent=4)
    with open(localPath("processed_supplementary_matches.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(processed_ids), f, ensure_ascii=False, indent=4)


# ---- identify low-data teams from the current h2h dataset ----
valid_h2h_count = {tid: 0 for tid in TEAM_CANONICAL}
for m in h2h_matches.values():
    if m.get("radiant_roster_valid") and m.get("dire_roster_valid"):
        valid_h2h_count[m["radiant_team_id"]] += 1
        valid_h2h_count[m["dire_team_id"]] += 1

low_data_teams = {tid: cnt for tid, cnt in valid_h2h_count.items() if cnt < LOW_DATA_THRESHOLD}

print("=== Low-data teams (< %d valid h2h matches) ===" % LOW_DATA_THRESHOLD)
for tid, cnt in sorted(low_data_teams.items(), key=lambda kv: kv[1]):
    print(f"  {TEAM_CANONICAL[tid]}: {cnt} valid h2h matches")
print()

print("Resolving tracked player account_ids for roster verification...")
account_to_team = buildAccountToTeam()
print(f"Resolved {len(account_to_team)} tracked players.\n")

already_h2h_ids = set(int(mid) for mid in h2h_matches.keys())

for team_id in low_data_teams:
    team_name = TEAM_CANONICAL[team_id]
    history = team_match_history.get(str(team_id), {}).get("matches", [])

    candidates = [
        m for m in history
        if m.get("opponent_team_id") in TOP_UNTRACKED_TEAM_IDS
        and m["match_id"] not in already_h2h_ids
    ]
    candidates.sort(key=lambda m: m.get("start_time", 0), reverse=True)
    candidates = candidates[:PER_TEAM_CAP]

    to_fetch = [m for m in candidates if m["match_id"] not in processed_ids]
    print(f"=== {team_name}: {len(candidates)} candidate matches vs top untracked teams (capped at {PER_TEAM_CAP}), {len(to_fetch)} new to fetch ===")

    for i, cand in enumerate(to_fetch, 1):
        match_id = cand["match_id"]
        try:
            match_r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
        except RateLimitExceeded as e:
            print(f"Rate limit exhausted: {e}. Stopping, progress saved.")
            saveAll()
            raise SystemExit(1)

        if "players" not in match_r or "radiant_team" not in match_r or "dire_team" not in match_r:
            print(f"  match {match_id}: incomplete data, skipping ({i}/{len(to_fetch)})")
            processed_ids.add(match_id)
            saveAll()
            continue

        try:
            stratzResp = stratzPost("{ match(id: %d) { predictedWinRates predictedOutcomeWeight analysisOutcome } }" % match_id)
        except StratzUnavailable as e:
            print(f"Stratz недоступен: {e}. Stopping, progress saved.")
            saveAll()
            raise SystemExit(1)
        stratz_data = (stratzResp.get("data") or {}).get("match") or {}
        time.sleep(1.0)

        radiant_team_id = resolveTeamId(match_r["radiant_team"]["team_id"])
        dire_team_id = resolveTeamId(match_r["dire_team"]["team_id"])
        is_radiant = (radiant_team_id == team_id)
        our_team_id = radiant_team_id if is_radiant else dire_team_id
        opponent_team_id = dire_team_id if is_radiant else radiant_team_id

        our_roster_match = sum(
            1 for p in match_r["players"]
            if p.get("isRadiant") == is_radiant and account_to_team.get(p.get("account_id")) == our_team_id
        )
        our_roster_valid = our_roster_match >= MIN_ROSTER_MATCH

        supplementary_matches[str(match_id)] = {
            "team_id": team_id,
            "team_name": team_name,
            "opponent_team_id": opponent_team_id,
            "opponent_name": TOP_UNTRACKED_TEAM_IDS.get(opponent_team_id, cand.get("opponent_team_name")),
            "is_radiant": is_radiant,
            "start_time": match_r.get("start_time"),
            "league_id": match_r.get("leagueid"),
            "league_name": (match_r.get("league") or {}).get("name"),
            "duration": match_r.get("duration"),
            "radiant_win": match_r.get("radiant_win"),
            "picks_bans": match_r.get("picks_bans"),
            "predicted_win_rates": stratz_data.get("predictedWinRates"),
            "predicted_outcome_weight": stratz_data.get("predictedOutcomeWeight"),
            "analysis_outcome": stratz_data.get("analysisOutcome"),
            "our_roster_match": our_roster_match,
            "our_roster_valid": our_roster_valid,
        }
        processed_ids.add(match_id)
        saveAll()

        valid_note = "" if our_roster_valid else f" [ROSTER MISMATCH {our_roster_match}/5]"
        print(f"  match {match_id}: {team_name} vs {supplementary_matches[str(match_id)]['opponent_name']} processed ({i}/{len(to_fetch)}){valid_note}")
        time.sleep(0.5)

print("\n=== Done ===")
valid_count = sum(1 for m in supplementary_matches.values() if m.get("our_roster_valid"))
print(f"Total supplementary matches: {len(supplementary_matches)}, roster-valid: {valid_count}")
for tid in low_data_teams:
    team_total = sum(1 for m in supplementary_matches.values() if m["team_id"] == tid and m.get("our_roster_valid"))
    print(f"  {TEAM_CANONICAL[tid]}: {team_total} supplementary valid matches (+ {valid_h2h_count[tid]} h2h = {team_total + valid_h2h_count[tid]} total)")
