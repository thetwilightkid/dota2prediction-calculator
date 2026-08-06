import json
import os
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from config import TEAM_CANONICAL, TEAM_ALL_IDS, resolveTeamId
from api_utils import openDotaGet, RateLimitExceeded, stratzPost, StratzUnavailable
from roster_utils import buildAccountToTeam

CUTOFF_TS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
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
processed_h2h_set = set(loadJson(localPath("processed_h2h_matches.json"), []))


def saveAll():
    with open(localPath("team_match_history.json"), "w", encoding="utf-8") as f:
        json.dump(team_match_history, f, ensure_ascii=False, indent=4)
    with open(localPath("h2h_matches.json"), "w", encoding="utf-8") as f:
        json.dump(h2h_matches, f, ensure_ascii=False, indent=4)
    with open(localPath("processed_h2h_matches.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(processed_h2h_set), f, ensure_ascii=False, indent=4)


print(f"=== Step A: fetching match history for {len(TEAM_CANONICAL)} teams (since 2025-01-01) ===")

h2h_candidate_ids = set()
match_id_to_teams = {}

for team_id, team_name in TEAM_CANONICAL.items():
    all_ids = TEAM_ALL_IDS[team_id]
    seen_match_ids = set()
    recent = []
    raw_total = 0

    for query_id in all_ids:
        try:
            matches = openDotaGet(f"https://api.opendota.com/api/teams/{query_id}/matches")
        except RateLimitExceeded as e:
            print(f"Rate limit exhausted while fetching {team_name}'s history: {e}. Stopping Step A.")
            saveAll()
            raise SystemExit(1)

        if not isinstance(matches, list):
            print(f"  [{team_name}] (id {query_id}) could not fetch match history: {matches}")
            continue

        raw_total += len(matches)
        for m in matches:
            if m.get("start_time", 0) >= CUTOFF_TS and m.get("leagueid") and m["match_id"] not in seen_match_ids:
                seen_match_ids.add(m["match_id"])
                recent.append(m)
        time.sleep(0.3)

    alias_note = f" (queried {len(all_ids)} registrations: {all_ids})" if len(all_ids) > 1 else ""
    print(f"  [{team_name}] {raw_total} total matches across all registrations, {len(recent)} tournament matches since 2025-01-01{alias_note}")

    history_entries = []
    for m in recent:
        opponent_raw = m.get("opposing_team_id")
        opponent_id = resolveTeamId(opponent_raw) if opponent_raw else None
        is_radiant = m.get("radiant")
        won = (m.get("radiant_win") == is_radiant) if is_radiant is not None else None

        history_entries.append({
            "match_id": m["match_id"],
            "start_time": m["start_time"],
            "league_id": m.get("leagueid"),
            "league_name": m.get("league_name"),
            "duration": m.get("duration"),
            "is_radiant": is_radiant,
            "won": won,
            "opponent_team_id": opponent_id,
            "opponent_team_name": TEAM_CANONICAL.get(opponent_id, m.get("opposing_team_name")),
        })

        if opponent_id in TEAM_CANONICAL:
            match_id_to_teams[m["match_id"]] = tuple(sorted((team_id, opponent_id)))
            h2h_candidate_ids.add(m["match_id"])

    team_match_history[str(team_id)] = {"name": team_name, "matches": history_entries}
    time.sleep(0.6)

saveAll()
print(f"\n=== Step A complete: {len(h2h_candidate_ids)} unique head-to-head matches found across all 16 teams ===\n")

already_done = h2h_candidate_ids & processed_h2h_set
to_fetch = sorted(h2h_candidate_ids - processed_h2h_set)
print(f"=== Step C: fetching full detail for {len(to_fetch)} new head-to-head matches (skipping {len(already_done)} already processed) ===")

print("Resolving tracked player account_ids for roster verification...")
account_to_team = buildAccountToTeam()
print(f"Resolved {len(account_to_team)} tracked players.\n")

for i, match_id in enumerate(to_fetch, 1):
    try:
        match_r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
    except RateLimitExceeded as e:
        print(f"Rate limit exhausted (including paid key): {e}. Stopping Step C, progress saved.")
        saveAll()
        raise SystemExit(1)

    if "players" not in match_r or "radiant_team" not in match_r or "dire_team" not in match_r:
        print(f"  match {match_id}: incomplete data, skipping ({i}/{len(to_fetch)})")
        continue

    try:
        stratzResp = stratzPost("{ match(id: %d) { predictedWinRates predictedOutcomeWeight analysisOutcome } }" % match_id)
    except StratzUnavailable as e:
        print(f"Stratz недоступен: {e}. Stopping Step C, progress saved.")
        saveAll()
        raise SystemExit(1)
    stratz_data = (stratzResp.get("data") or {}).get("match") or {}
    time.sleep(1.0)

    team_a, team_b = match_id_to_teams[match_id]
    radiant_team_id = resolveTeamId(match_r["radiant_team"]["team_id"])
    dire_team_id = resolveTeamId(match_r["dire_team"]["team_id"])

    radiant_roster_match = sum(
        1 for p in match_r["players"]
        if p.get("isRadiant") and account_to_team.get(p.get("account_id")) == radiant_team_id
    )
    dire_roster_match = sum(
        1 for p in match_r["players"]
        if not p.get("isRadiant") and account_to_team.get(p.get("account_id")) == dire_team_id
    )
    radiant_roster_valid = radiant_roster_match >= MIN_ROSTER_MATCH
    dire_roster_valid = dire_roster_match >= MIN_ROSTER_MATCH

    h2h_matches[str(match_id)] = {
        "start_time": match_r.get("start_time"),
        "league_id": match_r.get("leagueid"),
        "league_name": (match_r.get("league") or {}).get("name"),
        "duration": match_r.get("duration"),
        "radiant_team_id": radiant_team_id,
        "dire_team_id": dire_team_id,
        "radiant_win": match_r.get("radiant_win"),
        "picks_bans": match_r.get("picks_bans"),
        "predicted_win_rates": stratz_data.get("predictedWinRates"),
        "predicted_outcome_weight": stratz_data.get("predictedOutcomeWeight"),
        "analysis_outcome": stratz_data.get("analysisOutcome"),
        "radiant_roster_match": radiant_roster_match,
        "dire_roster_match": dire_roster_match,
        "radiant_roster_valid": radiant_roster_valid,
        "dire_roster_valid": dire_roster_valid,
    }
    processed_h2h_set.add(match_id)
    saveAll()

    validity_note = "" if (radiant_roster_valid and dire_roster_valid) else f" [ROSTER MISMATCH r={radiant_roster_match}/5 d={dire_roster_match}/5]"
    print(f"  match {match_id}: {TEAM_CANONICAL[team_a]} vs {TEAM_CANONICAL[team_b]} processed ({i}/{len(to_fetch)}){validity_note}")
    time.sleep(0.5)

print("\n=== Step C complete ===")
saveAll()
print(f"Final: {len(team_match_history)} teams with history, {len(h2h_matches)} head-to-head matches with full detail.")
