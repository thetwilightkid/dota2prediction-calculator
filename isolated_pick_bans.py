"""Shared aggregation for "isolated" (bucket-restricted, unweighted) pick/ban
stats - used by both compute_group_stage_pick_bans.py and
compute_pretournament_pick_bans.py so the two scripts stay structurally
identical and only differ in which match bucket they pass in. Each hero
entry carries both a raw count AND a rate (count / team's games in this
bucket) - "how many times" and "how often," side by side."""

from team_config import TEAM_CANONICAL


def heroNameFactory(hero_names):
    def heroName(hero_id):
        return hero_names.get(str(hero_id), f"hero_{hero_id}")
    return heroName


def newTeamBucket():
    return {"picks": {}, "bans_made": {}, "bans_against": {}, "games": 0}


def recordPick(bucket, hero_id, won):
    entry = bucket["picks"].setdefault(hero_id, {"pick_count": 0, "wins": 0})
    entry["pick_count"] += 1
    if won:
        entry["wins"] += 1


def recordBanMade(bucket, hero_id):
    entry = bucket["bans_made"].setdefault(hero_id, {"count": 0})
    entry["count"] += 1


def recordBanAgainst(bucket, hero_id, opponent_team_id):
    entry = bucket["bans_against"].setdefault(hero_id, {"count": 0, "by_opponent": {}})
    entry["count"] += 1
    opp_key = str(opponent_team_id)
    entry["by_opponent"][opp_key] = entry["by_opponent"].get(opp_key, 0) + 1


def processMatchSide(team_data, picks_bans, side_team, our_team_id, opponent_team_id, won):
    if our_team_id not in team_data:
        return
    bucket = team_data[our_team_id]
    bucket["games"] += 1
    for pb in picks_bans:
        if pb.get("team") != side_team:
            continue
        hero_id = pb.get("hero_id")
        if hero_id is None or hero_id < 0:
            continue
        if pb.get("is_pick"):
            recordPick(bucket, hero_id, won)
        else:
            recordBanMade(bucket, hero_id)

    opponent_side = 1 - side_team
    for pb in picks_bans:
        if pb.get("team") != opponent_side or pb.get("is_pick"):
            continue
        hero_id = pb.get("hero_id")
        if hero_id is None or hero_id < 0:
            continue
        recordBanAgainst(bucket, hero_id, opponent_team_id)


def computeIsolatedPickBans(matches, hero_names):
    """matches: iterable of match dicts already filtered to the desired
    bucket (each needs picks_bans, radiant_win, radiant/dire_team_id,
    radiant/dire_roster_valid). Returns (teams_out, skipped_no_pb)."""
    heroName = heroNameFactory(hero_names)
    team_data = {tid: newTeamBucket() for tid in TEAM_CANONICAL}

    skipped_no_pb = 0
    for m in matches:
        picks_bans = m.get("picks_bans")
        if not picks_bans:
            skipped_no_pb += 1
            continue
        radiant_win = bool(m.get("radiant_win"))
        if m.get("radiant_roster_valid"):
            processMatchSide(team_data, picks_bans, 0, m["radiant_team_id"], m["dire_team_id"], radiant_win)
        if m.get("dire_roster_valid"):
            processMatchSide(team_data, picks_bans, 1, m["dire_team_id"], m["radiant_team_id"], not radiant_win)

    teams_out = {}
    for tid, name in TEAM_CANONICAL.items():
        bucket = team_data[tid]
        games = bucket["games"]

        picks_out = {}
        for hero_id, v in bucket["picks"].items():
            win_rate = v["wins"] / v["pick_count"] if v["pick_count"] > 0 else None
            picks_out[str(hero_id)] = {
                "hero_name": heroName(hero_id),
                "pick_count": v["pick_count"],
                "pick_rate": round(v["pick_count"] / games, 4) if games else None,
                "wins": v["wins"],
                "win_rate": round(win_rate, 4) if win_rate is not None else None,
            }

        bans_made_out = {
            str(hero_id): {
                "hero_name": heroName(hero_id),
                "count": v["count"],
                "rate": round(v["count"] / games, 4) if games else None,
            }
            for hero_id, v in bucket["bans_made"].items()
        }

        bans_against_out = {
            str(hero_id): {
                "hero_name": heroName(hero_id),
                "count": v["count"],
                "rate": round(v["count"] / games, 4) if games else None,
                "by_opponent": {
                    opp_id: {"team_name": TEAM_CANONICAL.get(int(opp_id), f"team_{opp_id}"), "count": cnt}
                    for opp_id, cnt in v["by_opponent"].items()
                },
            }
            for hero_id, v in bucket["bans_against"].items()
        }

        teams_out[str(tid)] = {
            "team_name": name,
            "games": games,
            "picks": picks_out,
            "bans_made": bans_made_out,
            "bans_against": bans_against_out,
        }

    return teams_out, skipped_no_pb
