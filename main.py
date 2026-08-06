import json
import time
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from config import (
    PLAYERS_LIST,
    TITLE_KEYS,
    SHRINKAGE_K,
    LEAGUE_COUNTER_FIELDS,
    TEAM_CANONICAL,
    resolveTeamId,
)
from api_utils import openDotaGet, RateLimitExceeded, stratzPost, StratzUnavailable


def rootPath(filename):
    return os.path.join(ROOT_DIR, filename)


with open(rootPath("leagues.json"), "r", encoding="utf-8") as f:
    leagues_data = json.load(f)

with open(rootPath("heroes.json"), "r", encoding="utf-8") as f:
    heroes_data = json.load(f)

try:
    with open(rootPath('players_stat.json'), 'r', encoding='utf-8') as f:
        player_stat = json.load(f)
except FileNotFoundError:
    player_stat = {}

try:
    with open(rootPath('teams_stat.json'), 'r', encoding='utf-8') as f:
        team_stat = json.load(f)
except FileNotFoundError:
    team_stat = {}

try:
    with open(rootPath('processed_matches.json'), 'r', encoding='utf-8') as f:
        processed_matches = json.load(f)
except FileNotFoundError:
    processed_matches = {}

leagues_ids = list(map(int, leagues_data.keys()))

def computeTitleDistributions():
    player_totals = {}
    global_totals = {title: 0 for title in TITLE_KEYS}
    global_games = 0

    for name, player_data in player_stat.items():
        totals = {title: 0 for title in TITLE_KEYS}
        games_played_total = 0

        for key, league_entry in player_data.items():
            if key == "general" or key not in leagues_data:
                continue
            games_played_total += league_entry.get('games_played', 0)
            for title in TITLE_KEYS:
                totals[title] += league_entry.get('titles', {}).get(title, 0)

        player_totals[name] = (totals, games_played_total)
        global_games += games_played_total
        for title in TITLE_KEYS:
            global_totals[title] += totals[title]

    global_avg_rate = {
        title: (global_totals[title] / global_games if global_games > 0 else 0)
        for title in TITLE_KEYS
    }

    for name, (totals, games_played_total) in player_totals.items():
        player_data = player_stat[name]

        distribution = {}
        if games_played_total > 0:
            ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
            for title, count in ranked:
                if count == 0:
                    continue
                distribution[title] = round(count / games_played_total * 100)

        shrunk_rates = {
            title: (totals[title] + SHRINKAGE_K * global_avg_rate[title]) / (games_played_total + SHRINKAGE_K)
            for title in TITLE_KEYS
        }
        shrunk_distribution = {}
        for title, rate in sorted(shrunk_rates.items(), key=lambda kv: kv[1], reverse=True):
            pct = round(rate * 100)
            if pct > 0:
                shrunk_distribution[title] = pct

        player_data.setdefault('general', {})
        player_data['general']['games_played_total'] = games_played_total
        player_data['general']['title_distribution'] = distribution
        player_data['general']['title_distribution_shrunk'] = shrunk_distribution
        player_data['general']['shrinkage_k'] = SHRINKAGE_K

def ensureLeagueFields(league_id):
    league_entry = leagues_data[str(league_id)]
    for field in LEAGUE_COUNTER_FIELDS:
        if field not in league_entry:
            league_entry[field] = 0

def addTeamFields(league_id, team_id):
    if team_id not in TEAM_CANONICAL:
        return

    team_key = str(team_id)
    if team_key not in team_stat:
        team_stat[team_key] = {"name": TEAM_CANONICAL[team_id]}

    if league_id not in team_stat[team_key]:
        team_stat[team_key][league_id] = {
            "games_ended_min8": 0,
            "total_deaths_from_torm": 0,
            "no_firstblood_before_10min": 0,
            "firstblood_before_horn": 0,
            "games<25min": 0,
            "total_matches_parsed": 0,
        }

def addPlayerFields(league_id, player, match_r):
    if player['name'] not in player_stat:
        player_stat[player['name']] = {}

    if league_id not in player_stat[player['name']]:
        player_stat[player['name']][league_id] = {
            "games_played": 0,
            "stats": {},
            "titles": {
                "crimson": 0,
                "cerulean": 0,
                "emerald": 0,
                "royal": 0,
                "golden": 0,
                "elemental": 0,
                "otherworldly": 0,
                "heroic": 0,
            },
            "subtitles": {
                "tormented": 0,
                "fb_horn": 0,
                "no_fb_before_10": 0,
                "match_less_25": 0,
            }
        }

        if "general" not in player_stat[player['name']]:
            player_stat[player['name']]["general"] = {}

        player_stat[player['name']]["general"]["team_logo"] = (match_r['radiant_team']['logo_url'] if player['isRadiant'] else match_r['dire_team']['logo_url'])
        player_stat[player['name']]["general"]["pos"] = PLAYERS_LIST[player['name']]['pos']
    
        if PLAYERS_LIST[player['name']]['pos'] in (0, 1):
            player_stat[player['name']][league_id]['stats']['red'] = {
                "kills": [],
                "deaths": [],
                "creep_score": [],
                "gpm": [],
                "madstone_collected": [],
                "tower_kills": [],
            }
        if PLAYERS_LIST[player['name']]['pos'] in (1, 2):
            player_stat[player['name']][league_id]['stats']['blue'] = {
                "obs_placed": [],
                "camps_stacked": [],
                "runes_grabbed": [],
                "watchers_taken": [],
                "smokes_used": [],
                "lotuses": [],
            }
        if PLAYERS_LIST[player['name']]['pos'] in (0, 1, 2):
            player_stat[player['name']][league_id]['stats']['green'] = {
                "roshan_kills": [],
                "teamfight_participation": [],
                "stuns": [],
                "courier_kills": [],
                "tormentor_kills": [],
                "firstblood": [],
            }

def saveAll():
    computeTitleDistributions()

    with open(rootPath('players_stat.json'), "w", encoding="utf-8") as f:
        json.dump(player_stat, f, ensure_ascii=False, indent=4)

    with open(rootPath('teams_stat.json'), "w", encoding="utf-8") as f:
        json.dump(team_stat, f, ensure_ascii=False, indent=4)

    with open(rootPath('leagues.json'), "w", encoding="utf-8") as f:
        json.dump(leagues_data, f, ensure_ascii=False, indent=4)

    with open(rootPath('processed_matches.json'), "w", encoding="utf-8") as f:
        json.dump(processed_matches, f, ensure_ascii=False, indent=4)

try:
    for league_id in leagues_ids:
        league_id = str(league_id)
        ensureLeagueFields(league_id)

        matches = None
        for attempt in range(3):
            matches_response = openDotaGet(f"https://api.opendota.com/api/leagues/{league_id}/matches")
            if isinstance(matches_response, list):
                matches = matches_response
                break
            print(f"Не удалось получить список матчей лиги {league_id} (попытка {attempt + 1}): {matches_response}")
            time.sleep(3)

        if matches is None:
            print(f"Пропускаем лигу {league_id}: не удалось получить список матчей после 3 попыток")
            continue

        print(f"Лига {league_id} ({leagues_data[league_id].get('name', '')}): {len(matches)} матчей всего")

        processed_ids = set(processed_matches.setdefault(league_id, []))
        time.sleep(1.2)

        for match in matches:
            match_id = match['match_id']
            if match_id in processed_ids:
                continue

            match_r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
            stratzResp = stratzPost("{ match(id: %d) { firstBloodTime } }" % match_id)
            firstbloodTime = (stratzResp.get('data') or {}).get('match', {}).get('firstBloodTime')
            time.sleep(1.2)

            max_retries = 3
            for attempt in range(max_retries):
                if "players" in match_r and "radiant_team" in match_r and "dire_team" in match_r:
                    break
                else:
                    print(f"Не удалось получить данные матча {match_id} (попытка {attempt + 1}): {match_r}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        match_r = openDotaGet(f"https://api.opendota.com/api/matches/{match_id}")
            else:
                print(f"Не удалось получить данные о матче {match_id} после {max_retries} попыток")
                continue

            duration = match_r['duration']

            is_min8_ending = duration % 10 == 8
            is_less_25min = duration < 1500
            is_no_fb_before_10 = firstbloodTime > 600
            is_fb_before_horn = firstbloodTime < 0

            firstblood_side = None
            for p in match_r['players']:
                if p.get('firstblood_claimed'):
                    firstblood_side = p['isRadiant']
                    break

            radiant_team_id = resolveTeamId(match_r['radiant_team']['team_id'])
            dire_team_id = resolveTeamId(match_r['dire_team']['team_id'])

            addTeamFields(league_id, radiant_team_id)
            addTeamFields(league_id, dire_team_id)

            # ---- league-wide tallies ----
            leagues_data[str(league_id)]['total_matches_parsed'] += 1
            leagues_data[str(league_id)]['total_deaths_from_torm'] += sum(
                p.get('killed_by', {}).get('npc_dota_miniboss', 0) for p in match_r['players']
            )
            if is_min8_ending:
                leagues_data[str(league_id)]['games_ended_min8'] += 1
            if is_no_fb_before_10:
                leagues_data[str(league_id)]['no_firstblood_before_10min'] += 1
            if is_fb_before_horn:
                leagues_data[str(league_id)]['firstblood_before_horn'] += 1
            if is_less_25min:
                leagues_data[str(league_id)]['games<25min'] += 1

            # ---- team-wide tallies ----
            for team_id, is_radiant_side in ((radiant_team_id, True), (dire_team_id, False)):
                if team_id not in TEAM_CANONICAL:
                    continue
                team_entry = team_stat[str(team_id)][league_id]
                team_entry['total_matches_parsed'] += 1
                team_entry['total_deaths_from_torm'] += sum(
                    p.get('killed_by', {}).get('npc_dota_miniboss', 0)
                    for p in match_r['players'] if p['isRadiant'] == is_radiant_side
                )
                if is_min8_ending:
                    team_entry['games_ended_min8'] += 1
                if is_no_fb_before_10:
                    team_entry['no_firstblood_before_10min'] += 1
                if is_fb_before_horn and firstblood_side == is_radiant_side:
                    team_entry['firstblood_before_horn'] += 1
                if is_less_25min:
                    team_entry['games<25min'] += 1

            # ---- per-player stats ----
            is_match_counted = False

            for player in match_r['players']:
                if player['name'] not in PLAYERS_LIST:
                    continue

                if league_id not in player_stat.get(player['name'], {}):
                    addPlayerFields(league_id, player, match_r)

                if not is_match_counted:
                    leagues_data[league_id]['tracked_team_matches'] += 1
                    is_match_counted = True

                player_entry = player_stat[player['name']][league_id]
                player_entry['games_played'] += 1

                if PLAYERS_LIST[player['name']]['pos'] in (0, 1) and 'red' in player_entry['stats']:
                    player_entry['stats']['red']['kills'].append(player['kills'])
                    player_entry['stats']['red']['deaths'].append(player['deaths'])
                    player_entry['stats']['red']['creep_score'].append(player['last_hits'] + player['denies'])
                    player_entry['stats']['red']['gpm'].append(player['gold_per_min'])
                    player_entry['stats']['red']['madstone_collected'].append(player.get('item_uses', {}).get('madstone_bundle', 0))
                    player_entry['stats']['red']['tower_kills'].append(player['towers_killed'])
                if PLAYERS_LIST[player['name']]['pos'] in (1, 2) and 'blue' in player_entry['stats']:
                    player_entry['stats']['blue']['obs_placed'].append(player['obs_placed'])
                    player_entry['stats']['blue']['camps_stacked'].append(player['camps_stacked'])
                    player_entry['stats']['blue']['runes_grabbed'].append(player['rune_pickups'])
                    player_entry['stats']['blue']['watchers_taken'].append(player.get('ability_uses', {}).get('ability_lamp_use', 0))
                    player_entry['stats']['blue']['smokes_used'].append(player.get('item_uses', {}).get('smoke_of_deceit', 0))
                    item_uses = player.get('item_uses', {})
                    lotuses_eaten = (
                        item_uses.get('famango', 0)
                        + item_uses.get('great_famango', 0) * 3
                        + item_uses.get('greater_famango', 0) * 6
                    )
                    player_entry['stats']['blue']['lotuses'].append(lotuses_eaten)
                if PLAYERS_LIST[player['name']]['pos'] in (0, 1, 2) and 'green' in player_entry['stats']:
                    player_entry['stats']['green']['roshan_kills'].append(player['roshans_killed'])
                    player_entry['stats']['green']['teamfight_participation'].append(player['teamfight_participation'])
                    player_entry['stats']['green']['stuns'].append(player['stuns'])
                    player_entry['stats']['green']['courier_kills'].append(player['courier_kills'])
                    player_entry['stats']['green']['firstblood'].append(player['firstblood_claimed'])
                    player_entry['stats']['green']['tormentor_kills'].append(player.get('killed', {}).get('npc_dota_miniboss', 0))

                hero_info = heroes_data[str(player['hero_id'])]
                for title in player_entry['titles']:
                    if hero_info.get(f'is{title}'):
                        player_entry['titles'][title] += 1

                player_torm_deaths = player.get('killed_by', {}).get('npc_dota_miniboss', 0)
                if player_torm_deaths > 0:
                    player_entry['subtitles']['tormented'] += player_torm_deaths
                if is_fb_before_horn and player['isRadiant'] == firstblood_side:
                    player_entry['subtitles']['fb_horn'] += 1
                if is_no_fb_before_10:
                    player_entry['subtitles']['no_fb_before_10'] += 1
                if is_less_25min:
                    player_entry['subtitles']['match_less_25'] += 1

            processed_ids.add(match_id)
            processed_matches[league_id] = sorted(processed_ids)
            saveAll()
            print(f"[{league_id}] матч {match_id} обработан ({len(processed_ids)}/{len(matches)})")
except RateLimitExceeded as e:
    print(f"Дневной лимит запросов OpenDota исчерпан, останавливаем работу: {e}")
    saveAll()
except StratzUnavailable as e:
    print(f"Stratz недоступен, останавливаем работу: {e}")
    saveAll()

saveAll()