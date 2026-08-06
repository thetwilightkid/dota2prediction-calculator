import json
import os
import statistics
from datetime import datetime, timezone

from team_config import TEAM_CANONICAL
from weighting import recencyWeight as _recencyWeight, tierWeight as _tierWeight

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CHOKE_THRESHOLD = 0.70    # "clearly favored at some point" - did they still lose?
COMEBACK_THRESHOLD = 0.30  # "clearly the underdog at some point" - did they still win?
DRAFT_STAGE_INDEX = 0     # predicted_win_rates[0] = the pick-stage prediction, before any in-game events


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


def tierWeight(league_id):
    return _tierWeight(league_id, league_tiers)


def teamPerspectiveCurve(curve, is_radiant):
    """predictedWinRates is always from radiant's perspective - flip for dire."""
    return curve if is_radiant else [1.0 - v for v in curve]


# ---- gather per-team-match records: (weight, draft_stage, peak, trough, final, won) ----
team_records = {tid: [] for tid in TEAM_CANONICAL}

for m in h2h_matches.values():
    curve = m.get("predicted_win_rates")
    if not curve:
        continue
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))

    if m.get("radiant_roster_valid"):
        tid = m["radiant_team_id"]
        if tid in team_records:
            c = teamPerspectiveCurve(curve, True)
            team_records[tid].append((w, c[DRAFT_STAGE_INDEX], max(c), min(c), c[-1], bool(m.get("radiant_win"))))
    if m.get("dire_roster_valid"):
        tid = m["dire_team_id"]
        if tid in team_records:
            c = teamPerspectiveCurve(curve, False)
            team_records[tid].append((w, c[DRAFT_STAGE_INDEX], max(c), min(c), c[-1], not bool(m.get("radiant_win"))))

for m in supplementary_matches.values():
    if not m.get("our_roster_valid"):
        continue
    curve = m.get("predicted_win_rates")
    if not curve:
        continue
    tid = m["team_id"]
    if tid not in team_records:
        continue
    w = recencyWeight(m.get("start_time")) * tierWeight(m.get("league_id"))
    is_radiant = m.get("is_radiant")
    c = teamPerspectiveCurve(curve, is_radiant)
    won = bool(m.get("radiant_win")) if is_radiant else not bool(m.get("radiant_win"))
    team_records[tid].append((w, c[DRAFT_STAGE_INDEX], max(c), min(c), c[-1], won))


def weightedRate(records, condition):
    """Weighted P(outcome | condition) over records matching condition(draft_stage, peak, trough, final)."""
    matching = [(w, won) for w, draft_stage, peak, trough, final, won in records if condition(draft_stage, peak, trough, final)]
    total_w = sum(w for w, _ in matching)
    if total_w <= 0:
        return None, 0.0
    win_w = sum(w for w, won in matching if won)
    return win_w / total_w, total_w


results = {}
print("=== Stability / comeback scores (decayed, tier-weighted) ===")
for tid, name in TEAM_CANONICAL.items():
    records = team_records[tid]
    total_w = sum(w for w, *_ in records)

    # choke rate: was clearly favored (peak >= threshold) at some point - what fraction did they NOT win?
    win_rate_when_favored, favored_weight = weightedRate(records, lambda draft_stage, peak, trough, final: peak >= CHOKE_THRESHOLD)
    choke_rate = (1 - win_rate_when_favored) if win_rate_when_favored is not None else None

    # comeback rate: was clearly the underdog (trough <= threshold) at some point - what fraction did they WIN anyway?
    comeback_rate, underdog_weight = weightedRate(records, lambda draft_stage, peak, trough, final: trough <= COMEBACK_THRESHOLD)

    # draft-stage win rate: Stratz's predicted win% right after the draft (before any in-game events) -
    # a direct read on "how good is this team's draft," independent of how the game actually played out.
    if records:
        avg_draft_stage_win_rate = sum(w * draft_stage for w, draft_stage, *_ in records) / total_w
    else:
        avg_draft_stage_win_rate = None

    # did a good/bad draft actually translate into the result? - the draft-stage-specific analogue of
    # choke_rate/comeback_rate above (those use a 0.70/0.30 in-game-anytime threshold; these use the
    # single draft-stage value against a 0.5 threshold).
    draft_favored_win_rate, draft_favored_weight = weightedRate(records, lambda draft_stage, peak, trough, final: draft_stage > 0.5)
    draft_underdog_win_rate, draft_underdog_weight = weightedRate(records, lambda draft_stage, peak, trough, final: draft_stage <= 0.5)

    # volatility: average swing (peak - trough) across all their games - how much their predicted odds moved
    if records:
        avg_volatility = sum(w * (peak - trough) for w, draft_stage, peak, trough, final, won in records) / total_w
    else:
        avg_volatility = None

    results[str(tid)] = {
        "team_name": name,
        "matches_with_curve": len(records),
        "effective_n": total_w,
        "avg_draft_stage_win_rate": avg_draft_stage_win_rate,
        "draft_favored_win_rate": draft_favored_win_rate,
        "draft_favored_sample_weight": draft_favored_weight,
        "draft_underdog_win_rate": draft_underdog_win_rate,
        "draft_underdog_sample_weight": draft_underdog_weight,
        "choke_rate": choke_rate,
        "choke_rate_sample_weight": favored_weight,
        "comeback_rate": comeback_rate,
        "comeback_rate_sample_weight": underdog_weight,
        "avg_volatility": avg_volatility,
    }

    def fmt(x):
        return f"{x:.3f}" if x is not None else "n/a"
    print(f"  {name:16s} draft_wr={fmt(avg_draft_stage_win_rate)}  draft_favored_wr={fmt(draft_favored_win_rate)} (n={draft_favored_weight:.0f})  draft_underdog_wr={fmt(draft_underdog_win_rate)} (n={draft_underdog_weight:.0f})  choke_rate={fmt(choke_rate)} (n={favored_weight:.0f})  comeback_rate={fmt(comeback_rate)} (n={underdog_weight:.0f})  avg_volatility={fmt(avg_volatility)}  [{len(records)} matches w/ curve]")

with open(localPath("team_stability_scores.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "choke_threshold": CHOKE_THRESHOLD,
            "comeback_threshold": COMEBACK_THRESHOLD,
            "note": (
                "avg_draft_stage_win_rate = decayed/tier-weighted average of predicted_win_rates[0] - Stratz's "
                "predicted win% immediately after the draft, before any in-game events - i.e. 'how good is this "
                "team's draft' on its own. draft_favored_win_rate/draft_underdog_win_rate = P(actual win | "
                "draft-stage prediction was >0.5 / <=0.5) - whether a good draft actually converts into a win "
                "and whether they can overcome a bad one; this is the draft-stage-specific analogue of "
                "choke_rate/comeback_rate below (0.5 threshold, single draft-stage value) as opposed to those "
                "(0.70/0.30 threshold, anywhere in the match). choke_rate = P(lose | was predicted >=70% "
                "favorite at some point in the match). comeback_rate = P(win | was predicted <=30% at some "
                "point). All rates are decayed/tier-weighted like the main rating. avg_volatility = average "
                "(peak-trough) swing in predicted win% across a team's games - higher means more rollercoaster "
                "games, lower means more control/dominant closeouts."
            ),
        },
        "teams": results,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_stability_scores.json")
