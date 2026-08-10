"""Shared recency/tier weighting used across every compute_*.py script in this
folder, so the formula only needs to change in one place. 2026 rosters/form are
what actually predict TI2026 - 2025 data is real signal but should never be
able to outweigh 2026 data, hence the two-segment curve below rather than a
single linear ramp back to a distant cutoff."""

from datetime import datetime, timezone

RECENCY_OLD_CUTOFF = datetime(2025, 1, 1, tzinfo=timezone.utc)   # oldest data we collect at all
RECENCY_BREAKPOINT = datetime(2026, 1, 1, tzinfo=timezone.utc)   # 2026 rosters/form start mattering a lot more here

OLD_FLOOR_WEIGHT = 0.1     # weight at/before 2025-01-01
BREAKPOINT_WEIGHT = 0.5    # weight exactly at 2026-01-01
FULL_WEIGHT = 1.0          # weight at "now"

_OLD_CUTOFF_TS = RECENCY_OLD_CUTOFF.timestamp()
_BREAKPOINT_TS = RECENCY_BREAKPOINT.timestamp()


def recencyWeight(start_time, now_ts=None):
    """Two-segment linear ramp: 0.1 -> 0.5 across all of 2025, then 0.5 -> 1.0
    from 2026-01-01 to now. A 2025 match can never outweigh a 2026 match,
    regardless of tournament tier."""
    if start_time is None:
        return OLD_FLOOR_WEIGHT

    now_ts = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()

    if start_time <= _OLD_CUTOFF_TS:
        return OLD_FLOOR_WEIGHT

    if start_time <= _BREAKPOINT_TS:
        frac = (start_time - _OLD_CUTOFF_TS) / (_BREAKPOINT_TS - _OLD_CUTOFF_TS)
        frac = max(0.0, min(1.0, frac))
        return OLD_FLOOR_WEIGHT + frac * (BREAKPOINT_WEIGHT - OLD_FLOOR_WEIGHT)

    span = now_ts - _BREAKPOINT_TS
    frac = (start_time - _BREAKPOINT_TS) / span if span > 0 else 1.0
    frac = max(0.0, min(1.0, frac))
    return BREAKPOINT_WEIGHT + frac * (FULL_WEIGHT - BREAKPOINT_WEIGHT)


def tierWeight(league_id, league_tiers):
    """league_tiers: the loaded league_tiers.json dict."""
    entry = league_tiers.get(str(league_id))
    return entry["tier_weight"] if entry else 0.5  # unrecognized league: assume mid-tier


def matchWeight(start_time, league_id, league_tiers, now_ts=None):
    return recencyWeight(start_time, now_ts) * tierWeight(league_id, league_tiers)


# Roster-integrity penalty: a flat multiplier applied to a team's WIN credit
# (not losses) when computing decayed win rate / overall win rate - i.e. every
# win this team earned across the tracked history counts for less than a full
# win. This is distinct from recency/tier weighting; it reflects that a chunk
# of a team's historical results were earned with a roster that no longer
# exists, so shouldn't fully carry over to the TI2026 win-probability estimate.
#
# 2026-08-07: LGD Gaming's TaiLung was permanently banned from competing and
# is replaced by Topson for TI2026 - user-specified -25% (0.75x) win-credit
# deduction, applied identically wherever a team's win credit feeds the rating
# pipeline (compute_ratings.py's form component, compute_overall_winrate.py)
# so it propagates through to the simulated win probability rather than being
# a one-off adjustment applied only at the end.
TEAM_WIN_CREDIT_MULTIPLIER = {
    10150538: 0.75,  # LGD Gaming
}


def winCreditMultiplier(team_id):
    return TEAM_WIN_CREDIT_MULTIPLIER.get(team_id, 1.0)
