import json
import os
from datetime import datetime, timezone

from team_config import TEAM_CANONICAL
from weighting import recencyWeight as _recencyWeight, RECENCY_OLD_CUTOFF, OLD_FLOOR_WEIGHT, winCreditMultiplier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TIER_ORDER = ["S", "A", "B", "C", "excluded", "unknown"]


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

NOW_TS = datetime.now(timezone.utc).timestamp()


def recencyWeight(start_time):
    return _recencyWeight(start_time, NOW_TS)


def tierInfo(league_id):
    entry = league_tiers.get(str(league_id))
    if entry:
        return entry["tier"], entry["tier_weight"]
    return "unknown", 0.5  # unrecognized league: treat as mid-tier, matches compute_ratings.py's default


# each entry: (won: bool, tier: str, tier_weight: float, recency_weight: float, duration: int|None)
team_matches = {tid: [] for tid in TEAM_CANONICAL}

for m in h2h_matches.values():
    tier, tw = tierInfo(m.get("league_id"))
    rw = recencyWeight(m.get("start_time"))
    dur = m.get("duration")
    if m.get("radiant_roster_valid"):
        tid = m["radiant_team_id"]
        if tid in team_matches:
            team_matches[tid].append((bool(m.get("radiant_win")), tier, tw, rw, dur))
    if m.get("dire_roster_valid"):
        tid = m["dire_team_id"]
        if tid in team_matches:
            team_matches[tid].append((not bool(m.get("radiant_win")), tier, tw, rw, dur))

for m in supplementary_matches.values():
    if not m.get("our_roster_valid"):
        continue
    tid = m["team_id"]
    if tid not in team_matches:
        continue
    tier, tw = tierInfo(m.get("league_id"))
    rw = recencyWeight(m.get("start_time"))
    is_radiant = m.get("is_radiant")
    won = bool(m.get("radiant_win")) if is_radiant else not bool(m.get("radiant_win"))
    team_matches[tid].append((won, tier, tw, rw, m.get("duration")))


def weightedRate(entries, weight_fn, win_credit_multiplier=1.0):
    """weight_fn(tier, tier_weight, recency_weight) -> the weight to use for this match.
    win_credit_multiplier scales WIN credit only, same roster-integrity penalty
    mechanism as compute_ratings.py's decayedWinRate."""
    total_w = 0.0
    win_w = 0.0
    for won, tier, tw, rw, _dur in entries:
        w = weight_fn(tw, rw)
        total_w += w
        if won:
            win_w += w * win_credit_multiplier
    return (win_w / total_w if total_w > 0 else None), total_w


results = {}
print("=== Item H: tournament-tier-weighted overall win rate ===\n")
for tid, name in TEAM_CANONICAL.items():
    entries = team_matches[tid]
    raw_total = len(entries)
    raw_wins = sum(1 for won, *_ in entries if won)
    raw_win_rate = raw_wins / raw_total if raw_total > 0 else None

    wcm = winCreditMultiplier(tid)
    tier_weighted_rate, tier_effective_n = weightedRate(entries, lambda tw, rw: tw, wcm)
    decayed_rate, decayed_effective_n = weightedRate(entries, lambda tw, rw: tw * rw, wcm)

    durations = [dur for *_, dur in entries if dur]
    avg_duration = round(sum(durations) / len(durations)) if durations else None

    by_tier = {t: {"matches": 0, "wins": 0} for t in TIER_ORDER}
    for won, tier, _tw, _rw, _dur in entries:
        by_tier[tier]["matches"] += 1
        if won:
            by_tier[tier]["wins"] += 1
    for t in TIER_ORDER:
        b = by_tier[t]
        b["win_rate"] = round(b["wins"] / b["matches"], 4) if b["matches"] > 0 else None

    results[str(tid)] = {
        "team_name": name,
        "raw_match_count": raw_total,
        "raw_win_count": raw_wins,
        "raw_win_rate": round(raw_win_rate, 4) if raw_win_rate is not None else None,
        "tier_weighted_win_rate": round(tier_weighted_rate, 4) if tier_weighted_rate is not None else None,
        "tier_weighted_effective_n": round(tier_effective_n, 2),
        "tier_and_recency_weighted_win_rate": round(decayed_rate, 4) if decayed_rate is not None else None,
        "tier_and_recency_weighted_effective_n": round(decayed_effective_n, 2),
        "avg_match_duration_seconds": avg_duration,
        "win_credit_multiplier": wcm,
        "by_tier": by_tier,
    }

    print(f"  {name:16s} raw={raw_win_rate:.3f} ({raw_wins}/{raw_total})" if raw_win_rate is not None else f"  {name:16s} raw=n/a (0 matches)", end="")
    print(f"   tier_weighted={tier_weighted_rate:.3f}" if tier_weighted_rate is not None else "   tier_weighted=n/a", end="")
    print(f"   tier+recency={decayed_rate:.3f}" if decayed_rate is not None else "   tier+recency=n/a")

with open(localPath("team_overall_winrate.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "note": (
                "Standalone tournament-tier-weighted overall win rate report (Item H), built from the same "
                "roster-verified match pool as compute_ratings.py's 'form' signal, but exposed here on its own "
                "with the intermediate weighting stages shown separately for transparency: raw_win_rate (no "
                "weighting at all), tier_weighted_win_rate (each match weighted only by its tournament tier: "
                "S=1.0/A=0.8/B=0.5/C=0.25/excluded=0.0, unknown leagues default to 0.5), and "
                "tier_and_recency_weighted_win_rate (tier weight x recency weight, see weighting.py: 0.1->0.5 "
                "across all of 2025, 0.5->1.0 from 2026-01-01 to now - this last figure is the exact same "
                "'decayed_win_rate' value used as the form component inside team_composite_ratings.json). "
                "'excluded' tier (weight 0.0) covers leagues that predate 2025-10-14, the earliest match date "
                "among the originally-curated leagues.json tournaments - discarded entirely per user decision "
                "rather than merely recency-floored (see league_tiers.json's excluded_reason fields). by_tier "
                "breaks a team's raw record down per tournament tier so you can see e.g. whether a team's "
                "strong overall record leans on S-tier results or is padded by lower-tier/excluded events."
            ),
            "tier_weights": {"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.25, "excluded": 0.0, "unknown": 0.5},
            "recency_old_cutoff": RECENCY_OLD_CUTOFF.isoformat(),
            "recency_old_floor_weight": OLD_FLOOR_WEIGHT,
            "win_credit_multiplier_note": "win_credit_multiplier < 1.0 applies a roster-integrity penalty to that team's WIN credit only, in tier_weighted_win_rate and tier_and_recency_weighted_win_rate (raw_win_rate stays a true unadjusted historical figure) - see weighting.py's TEAM_WIN_CREDIT_MULTIPLIER.",
        },
        "teams": results,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_overall_winrate.json")
