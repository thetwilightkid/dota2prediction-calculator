import json
import math
import os
import statistics
import time
from datetime import datetime, timezone

import cloudscraper

from team_config import TEAM_CANONICAL, TEAM_ALL_IDS
from weighting import recencyWeight as _recencyWeight, tierWeight as _tierWeight, winCreditMultiplier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

W_ELO = 0.5                    # default composite weight for the external Glicko-2 signal
W_FORM_PRETOURNAMENT = 0.15    # default composite weight for pre-International decayed win-rate
W_FORM_GROUPSTAGE = 0.15       # default composite weight for Group Stage decayed win-rate
W_MARKET = 0.2                 # default composite weight for the EPT/ESL/Liquipedia consensus signal
# Recent form used to be one blended 70/30 (Group Stage/pre-tournament) figure under a single
# W_FORM=0.3 weight; split into two independent signals (each defaulting to half the old total
# weight) so a slider UI can weigh "how they've done at this specific event" separately from
# "how they were doing before it" instead of only ever seeing them pre-mixed.
# All are also stored raw/unblended so a future slider UI can recombine freely.


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


h2h_matches = loadJson(localPath("h2h_matches.json"), {})
supplementary_matches = loadJson(localPath("supplementary_matches.json"), {})
league_tiers = loadJson(localPath("league_tiers.json"), {})

NOW = datetime.now(timezone.utc)
NOW_TS = NOW.timestamp()


def recencyWeight(start_time):
    return _recencyWeight(start_time, NOW_TS)


def tierWeight(league_id):
    return _tierWeight(league_id, league_tiers)


# TI2026's own league_id - used to bucket matches into "group stage" vs "everything else"
# for the 70/30 categorical blend below. More precise than a date cutoff (immune to any other
# tournament a team might play around the same dates).
GROUP_STAGE_LEAGUE_ID = 19719

# ---- gather every roster-valid match per team, weighted ----
team_matches = {tid: [] for tid in TEAM_CANONICAL}  # each entry: (weight, won: bool, is_group_stage: bool)

for m in h2h_matches.values():
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))
    is_gs = m.get("league_id") == GROUP_STAGE_LEAGUE_ID
    if m.get("radiant_roster_valid"):
        tid = m["radiant_team_id"]
        if tid in team_matches:
            team_matches[tid].append((w, bool(m.get("radiant_win")), is_gs))
    if m.get("dire_roster_valid"):
        tid = m["dire_team_id"]
        if tid in team_matches:
            team_matches[tid].append((w, not bool(m.get("radiant_win")), is_gs))

for m in supplementary_matches.values():
    if not m.get("our_roster_valid"):
        continue
    tid = m["team_id"]
    if tid not in team_matches:
        continue
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))
    is_gs = m.get("league_id") == GROUP_STAGE_LEAGUE_ID
    is_radiant = m.get("is_radiant")
    won = bool(m.get("radiant_win")) if is_radiant else not bool(m.get("radiant_win"))
    team_matches[tid].append((w, won, is_gs))


def _bucketWinRate(matches, win_credit_multiplier):
    """Plain within-bucket decayed win rate - relative weighting between matches
    inside the bucket is preserved (recency/tier still matter within a bucket),
    only the BUCKET's overall contribution is fixed by the caller."""
    total_w = sum(w for w, _, _ in matches)
    if total_w <= 0:
        return None
    win_w = sum(w for w, won, _ in matches if won) * win_credit_multiplier
    return win_w / total_w


def decayedWinRate(matches, win_credit_multiplier=1.0):
    """Splits a team's matches into the two buckets a slider UI can weigh
    independently: real TI2026 Group Stage results (2026-08-13 onward, under
    GROUP_STAGE_LEAGUE_ID) versus everything before the tournament. Each
    bucket gets its own decayed/tier-weighted win rate and its own effective_n
    (used downstream for that bucket's standard-error/uncertainty estimate) -
    unlike the old single-blended-number version, there's no fixed 70/30 mix
    baked in here anymore; the composite formula below applies its own
    (slider-adjustable) weight to each bucket's z-score independently.
    win_credit_multiplier scales WIN credit only (not the total-weight
    denominator) - a roster-integrity penalty for teams whose historical
    record was partly earned by a player no longer on the roster.
    Returns (groupstage_rate, groupstage_n, pretournament_rate, pretournament_n) -
    a rate is None when that bucket has no matches at all."""
    gs_matches = [x for x in matches if x[2]]
    pre_matches = [x for x in matches if not x[2]]
    gs_rate = _bucketWinRate(gs_matches, win_credit_multiplier)
    pre_rate = _bucketWinRate(pre_matches, win_credit_multiplier)
    gs_n = sum(w for w, _, _ in gs_matches)
    pre_n = sum(w for w, _, _ in pre_matches)
    return gs_rate, gs_n, pre_rate, pre_n


form_stats = {}
for tid, matches in team_matches.items():
    gs_rate, gs_n, pre_rate, pre_n = decayedWinRate(matches, winCreditMultiplier(tid))
    form_stats[tid] = {
        "decayed_win_rate_groupstage": gs_rate,
        "effective_n_groupstage": gs_n,
        "decayed_win_rate_pretournament": pre_rate,
        "effective_n_pretournament": pre_n,
        "raw_match_count": len(matches),
        "win_credit_multiplier": winCreditMultiplier(tid),
    }

print("=== Step 1: decayed, tier-weighted win rate (own data), split by bucket ===")
for tid in TEAM_CANONICAL:
    fs = form_stats[tid]
    print(f"  {TEAM_CANONICAL[tid]:16s} group_stage={fs['decayed_win_rate_groupstage']} (n={fs['effective_n_groupstage']:.1f})  pre_tournament={fs['decayed_win_rate_pretournament']} (n={fs['effective_n_pretournament']:.1f})  (raw {fs['raw_match_count']} matches total)")

# ---- fetch fresh datdota Glicko-2 (rating + phi) for all 16 teams ----
# Checks every known registration per team (rebrand fragmentation applies to
# datdota's ratings too, e.g. Team Vision's GLICKO_2 only exists under their
# PVISION alias id) and keeps whichever registration has the most recently
# started GLICKO_2 window.
#
# Falls back to the previous run's cached glicko_rating/glicko_phi (from the
# existing team_composite_ratings.json, if any) per-team when datdota can't be
# reached for that team - e.g. a Cloudflare block on the whole site, not just
# missing data for one team. Preserves the last known-good signal instead of
# crashing or silently zeroing every team out; each such team is flagged with
# "glicko_stale": true in the output so it's visible, not silently stale.
previous_ratings = loadJson(localPath("team_composite_ratings.json"), {}).get("teams", {})

print("\n=== Step 2: fetching datdota Glicko-2 rating + phi (checking all known registrations) ===")
scraper = cloudscraper.create_scraper()
glicko_stats = {}
datdota_unreachable_count = 0
for tid, name in TEAM_CANONICAL.items():
    best = None
    any_200 = False
    for query_id in TEAM_ALL_IDS[tid]:
        r = scraper.get(f"https://api.datdota.com/api/teams/{query_id}")
        if r.status_code == 200:
            any_200 = True
            g = (r.json().get("data", {}).get("ratings", {}) or {}).get("GLICKO_2")
            if g:
                # Prefer the newer rating window, but when two registrations'
                # windows happen to start on the same calendar day (datdota
                # refreshes windows uniformly across all teams), fall back to
                # whichever has lower phi (Glicko's own confidence measure) -
                # a brand-new registration (e.g. right after a rebrand) starts
                # from a fresh, high-phi prior and can swing wildly after just
                # a handful of games, while an established registration with
                # a long match history is far more trustworthy at an equal
                # "most recent" tiebreak. Caught 2026-08-18: Team Vision's new
                # "TEAM VISION" id (9572001, 10 games total, all this Group
                # Stage) was outranking their real "PVISION" id (9824702,
                # hundreds of games since 2024) purely because both windows
                # started on the same day - inflating their rating by ~700pts.
                candidate_key = (g["startPeriod"], -g["phi"])
                best_key = (best["startPeriod"], -best["phi"]) if best else None
                if best is None or candidate_key > best_key:
                    best = g
                    best["source_id"] = query_id
        time.sleep(0.5)

    if best:
        glicko_stats[tid] = {"rating": best["rating"], "phi": best["phi"], "stale": False}
        alias_note = f" (via id {best['source_id']})" if best["source_id"] != tid else ""
        print(f"  {name:16s} rating={best['rating']:.1f} phi={best['phi']:.1f} start={best['startPeriod']}{alias_note}")
        continue

    if not any_200:
        datdota_unreachable_count += 1
        prev = previous_ratings.get(str(tid), {})
        if prev.get("glicko_rating") is not None:
            glicko_stats[tid] = {"rating": prev["glicko_rating"], "phi": prev["glicko_phi"], "stale": True}
            print(f"  {name:16s} datdota unreachable - using cached rating={prev['glicko_rating']:.1f} phi={prev['glicko_phi']:.1f} from previous run")
            continue

    glicko_stats[tid] = {"rating": None, "phi": None, "stale": False}
    print(f"  {name:16s} GLICKO_2 missing across all {len(TEAM_ALL_IDS[tid])} known registrations (no cached fallback either)")

if datdota_unreachable_count == len(TEAM_CANONICAL):
    print("  NOTE: datdota was unreachable for all 16 teams this run (likely blocked/down) - entire glicko_stats came from the cached previous run.")

# ---- Step 3: EPT/ESL/Liquipedia "market consensus" ----
# These 3 sources have no native uncertainty measure and are missing Team
# Resilience/HULIGANI entirely, so they can't anchor the composite the way
# datdota does. But their MUTUAL DISAGREEMENT is itself a real uncertainty
# signal: if all 3 agree on a team's standing, that's corroborating evidence
# (low uncertainty); if they diverge, that divergence is genuine uncertainty,
# derived from data rather than assumed.
print("\n=== Step 3: EPT/ESL/Liquipedia market consensus ===")
team_ratings_raw = loadJson(localPath("team_ratings.json"), {})

# per source: {team_id: rating}, taking the MAX among a team's matched entries
# within that source (a team with a fragmented/newer registration shouldn't
# be dragged down by a cold-start entry when a stronger legacy entry exists).
source_ratings = {}
for source_name in ("EPT", "ESL_regional", "Liquipedia"):
    entries = team_ratings_raw.get(source_name, {}).get("ratings", [])
    per_team = {}
    for e in entries:
        tid = e.get("matched_team_id")
        if tid in TEAM_CANONICAL:
            per_team[tid] = max(per_team.get(tid, float("-inf")), e["rating"])
    source_ratings[source_name] = per_team

# z-score each source independently (population = however many of the 16 it covers)
source_z = {}
for source_name, per_team in source_ratings.items():
    vals = list(per_team.values())
    mean_, std_ = statistics.mean(vals), statistics.pstdev(vals)
    source_z[source_name] = {
        tid: ((rating - mean_) / std_ if std_ > 0 else 0.0)
        for tid, rating in per_team.items()
    }
    print(f"  {source_name}: {len(per_team)}/16 teams covered")

market_stats = {}
for tid in TEAM_CANONICAL:
    zs = [source_z[s][tid] for s in source_z if tid in source_z[s]]
    if len(zs) >= 2:
        market_stats[tid] = {"z_market": statistics.mean(zs), "sigma_market_z": statistics.pstdev(zs), "n_sources": len(zs)}
    elif len(zs) == 1:
        market_stats[tid] = {"z_market": zs[0], "sigma_market_z": 0.5, "n_sources": 1}  # single source: moderate default uncertainty
    else:
        market_stats[tid] = {"z_market": 0.0, "sigma_market_z": 1.0, "n_sources": 0}  # no coverage: neutral, max uncertainty

for tid, name in TEAM_CANONICAL.items():
    ms = market_stats[tid]
    print(f"  {name:16s} z_market={ms['z_market']:+.2f} sigma={ms['sigma_market_z']:.2f} (from {ms['n_sources']} source(s))")

# ---- convert all signals to a common z-score scale across the 16 teams ----
glicko_values = [v["rating"] for v in glicko_stats.values() if v["rating"] is not None]
glicko_mean = statistics.mean(glicko_values)
glicko_std = statistics.pstdev(glicko_values)

form_gs_values = [v["decayed_win_rate_groupstage"] for v in form_stats.values() if v["decayed_win_rate_groupstage"] is not None]
form_gs_mean = statistics.mean(form_gs_values)
form_gs_std = statistics.pstdev(form_gs_values)

form_pre_values = [v["decayed_win_rate_pretournament"] for v in form_stats.values() if v["decayed_win_rate_pretournament"] is not None]
form_pre_mean = statistics.mean(form_pre_values)
form_pre_std = statistics.pstdev(form_pre_values)

print(f"\nPopulation stats: glicko mean={glicko_mean:.1f} std={glicko_std:.1f} | group-stage form mean={form_gs_mean:.3f} std={form_gs_std:.3f} | pre-tournament form mean={form_pre_mean:.3f} std={form_pre_std:.3f}")

composite = {}
for tid, name in TEAM_CANONICAL.items():
    g = glicko_stats[tid]
    fs = form_stats[tid]

    z_elo = (g["rating"] - glicko_mean) / glicko_std if g["rating"] is not None and glicko_std > 0 else 0.0
    sigma_elo_z = (g["phi"] / glicko_std) if g["phi"] is not None and glicko_std > 0 else 1.0

    if fs["decayed_win_rate_groupstage"] is not None and form_gs_std > 0:
        z_form_gs = (fs["decayed_win_rate_groupstage"] - form_gs_mean) / form_gs_std
        p_for_var = min(max(fs["decayed_win_rate_groupstage"], 0.05), 0.95)
        se_p = math.sqrt(p_for_var * (1 - p_for_var) / fs["effective_n_groupstage"]) if fs["effective_n_groupstage"] > 0 else 1.0
        sigma_form_gs_z = se_p / form_gs_std
    else:
        z_form_gs = 0.0
        sigma_form_gs_z = 1.0  # no Group Stage data at all: maximally uncertain on this signal

    if fs["decayed_win_rate_pretournament"] is not None and form_pre_std > 0:
        z_form_pre = (fs["decayed_win_rate_pretournament"] - form_pre_mean) / form_pre_std
        p_for_var = min(max(fs["decayed_win_rate_pretournament"], 0.05), 0.95)
        se_p = math.sqrt(p_for_var * (1 - p_for_var) / fs["effective_n_pretournament"]) if fs["effective_n_pretournament"] > 0 else 1.0
        sigma_form_pre_z = se_p / form_pre_std
    else:
        z_form_pre = 0.0
        sigma_form_pre_z = 1.0  # no pre-tournament data at all: maximally uncertain on this signal

    ms = market_stats[tid]
    z_market = ms["z_market"]
    sigma_market_z = ms["sigma_market_z"]

    composite_mean = W_ELO * z_elo + W_FORM_PRETOURNAMENT * z_form_pre + W_FORM_GROUPSTAGE * z_form_gs + W_MARKET * z_market
    composite_sigma = math.sqrt(
        (W_ELO ** 2) * (sigma_elo_z ** 2)
        + (W_FORM_PRETOURNAMENT ** 2) * (sigma_form_pre_z ** 2)
        + (W_FORM_GROUPSTAGE ** 2) * (sigma_form_gs_z ** 2)
        + (W_MARKET ** 2) * (sigma_market_z ** 2)
    )

    composite[tid] = {
        "team_name": name,
        "glicko_rating": g["rating"],
        "glicko_phi": g["phi"],
        "glicko_stale": g.get("stale", False),
        "decayed_win_rate_groupstage": fs["decayed_win_rate_groupstage"],
        "effective_n_groupstage": fs["effective_n_groupstage"],
        "decayed_win_rate_pretournament": fs["decayed_win_rate_pretournament"],
        "effective_n_pretournament": fs["effective_n_pretournament"],
        "raw_match_count": fs["raw_match_count"],
        "win_credit_multiplier": fs["win_credit_multiplier"],
        "z_elo": z_elo,
        "sigma_elo_z": sigma_elo_z,
        "z_form_pretournament": z_form_pre,
        "sigma_form_pretournament_z": sigma_form_pre_z,
        "z_form_groupstage": z_form_gs,
        "sigma_form_groupstage_z": sigma_form_gs_z,
        "z_market": z_market,
        "sigma_market_z": sigma_market_z,
        "market_n_sources": ms["n_sources"],
        "w_elo": W_ELO,
        "w_form_pretournament": W_FORM_PRETOURNAMENT,
        "w_form_groupstage": W_FORM_GROUPSTAGE,
        "w_market": W_MARKET,
        "composite_mean": composite_mean,
        "composite_sigma": composite_sigma,
        # composite_mean/sigma are z-scores (population std=1) - not usable with
        # the standard Elo /400 formula directly. Converted back onto the Glicko
        # rating scale (using the datdota population mean/std as the reference)
        # so the simulator can use a standard, interpretable Elo-style formula.
        "rating_scale_mean": glicko_mean + composite_mean * glicko_std,
        "rating_scale_sigma": composite_sigma * glicko_std,
    }

print("\n=== Composite ratings (z-score scale, higher = stronger) ===")
for tid, c in sorted(composite.items(), key=lambda kv: -kv[1]["composite_mean"]):
    print(f"  {c['team_name']:16s} composite = {c['composite_mean']:+.3f} ± {c['composite_sigma']:.3f}   -> rating_scale = {c['rating_scale_mean']:.1f} ± {c['rating_scale_sigma']:.1f}   (elo_z={c['z_elo']:+.2f}, pretour_form_z={c['z_form_pretournament']:+.2f}, gs_form_z={c['z_form_groupstage']:+.2f}, market_z={c['z_market']:+.2f}, n_eff={c['effective_n_groupstage'] + c['effective_n_pretournament']:.0f})")

output = {
    "_meta": {
        "glicko_mean": glicko_mean,
        "glicko_std": glicko_std,
        "note": "rating_scale_mean/sigma is the composite z-score converted back onto the Glicko rating scale (mean + z*std) - use this for any Elo-style win-probability formula, not the raw composite_mean/sigma z-scores.",
        "win_credit_multiplier_note": "win_credit_multiplier < 1.0 means a roster-integrity penalty was applied to that team's WIN credit only (not their total match-weight) when computing decayed_win_rate - see weighting.py's TEAM_WIN_CREDIT_MULTIPLIER for which teams and why.",
    },
    "teams": {str(tid): v for tid, v in composite.items()},
}

with open(localPath("team_composite_ratings.json"), "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_composite_ratings.json")
