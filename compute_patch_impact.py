import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from team_config import TEAM_CANONICAL
from api_utils import openDotaGet, RateLimitExceeded

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TOP_N_POOL_HEROES = 8   # how many of a team's most-picked heroes count toward its patch impact score
EARLY_WINDOW = slice(0, 3)   # first 3 of the 7-bucket trend array = "earlier" in the current window
LATE_WINDOW = slice(4, 7)    # last 3 of the 7-bucket trend array = "most recent" - index 3 dropped as a buffer
MIN_BUCKET_PICKS = 200  # below this, a bucket's win rate is too noisy to trust


def localPath(filename):
    return os.path.join(SCRIPT_DIR, filename)


def loadJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


hero_names = loadJson(localPath("hero_names.json"), {})
patch_hero_context = loadJson(localPath("patch_741e_hero_changes.json"), {})
pick_ban_stats = loadJson(localPath("team_pick_ban_stats.json"), None)

if pick_ban_stats is None:
    raise SystemExit("team_pick_ban_stats.json not found - run compute_pick_ban_database.py first.")

league_data_mode = pick_ban_stats["league_data_mode"]


def heroName(hero_id):
    return hero_names.get(str(hero_id), f"hero_{hero_id}")


# ---- fetch live OpenDota heroStats (has the rolling pub_pick_trend/pub_win_trend arrays) ----
print("Fetching OpenDota heroStats (live pub pick/win trend)...")
try:
    hero_stats_raw = openDotaGet("https://api.opendota.com/api/heroStats")
except RateLimitExceeded as e:
    raise SystemExit(f"Rate limit exhausted fetching heroStats: {e}")

hero_trends = {}
for h in hero_stats_raw:
    hero_id = h["id"]
    pick_trend = h.get("pub_pick_trend") or []
    win_trend = h.get("pub_win_trend") or []
    if len(pick_trend) < 7 or len(win_trend) < 7:
        hero_trends[hero_id] = {
            "hero_name": heroName(hero_id),
            "pub_pick_trend": pick_trend,
            "pub_win_trend": win_trend,
            "winrate_delta": None,
            "note": "incomplete trend data",
        }
        continue

    early_pick = sum(pick_trend[EARLY_WINDOW])
    early_win = sum(win_trend[EARLY_WINDOW])
    late_pick = sum(pick_trend[LATE_WINDOW])
    late_win = sum(win_trend[LATE_WINDOW])

    early_wr = early_win / early_pick if early_pick >= MIN_BUCKET_PICKS else None
    late_wr = late_win / late_pick if late_pick >= MIN_BUCKET_PICKS else None
    delta = (late_wr - early_wr) if (early_wr is not None and late_wr is not None) else None

    context = patch_hero_context.get(heroName(hero_id))

    hero_trends[hero_id] = {
        "hero_name": heroName(hero_id),
        "pub_pick_trend": pick_trend,
        "pub_win_trend": win_trend,
        "early_window_pick_count": early_pick,
        "early_window_win_rate": round(early_wr, 4) if early_wr is not None else None,
        "late_window_pick_count": late_pick,
        "late_window_win_rate": round(late_wr, 4) if late_wr is not None else None,
        "winrate_delta": round(delta, 4) if delta is not None else None,
        "patch_notes_context": {"direction": context["direction"], "summary": context["summary"]} if context else None,
    }

print(f"Computed live winrate-trend delta for {len(hero_trends)} heroes.\n")


# ---- per-team patch impact: weight each team's top-picked heroes' winrate_delta by pick centrality ----
print(f"=== Patch impact score per team (top {TOP_N_POOL_HEROES} picked heroes, weighted by pick centrality) ===")
team_results = {}

for tid, name in TEAM_CANONICAL.items():
    picks = league_data_mode.get(str(tid), {}).get("picks", {})
    top_heroes = sorted(picks.items(), key=lambda kv: -kv[1]["weighted_pick_count"])[:TOP_N_POOL_HEROES]
    total_weight = sum(v["weighted_pick_count"] for _, v in top_heroes)

    breakdown = []
    score = 0.0
    scored_weight = 0.0
    for hero_id_str, v in top_heroes:
        hero_id = int(hero_id_str)
        trend = hero_trends.get(hero_id)
        delta = trend["winrate_delta"] if trend else None
        pick_weight_share = v["weighted_pick_count"] / total_weight if total_weight > 0 else 0.0
        contribution = delta * pick_weight_share if delta is not None else None

        breakdown.append({
            "hero_id": hero_id,
            "hero_name": heroName(hero_id),
            "pick_weight_share": round(pick_weight_share, 4),
            "winrate_delta": delta,
            "contribution": round(contribution, 5) if contribution is not None else None,
            "patch_notes_context": trend["patch_notes_context"] if trend else None,
        })
        if delta is not None:
            score += delta * pick_weight_share
            scored_weight += pick_weight_share

    # renormalize so missing-data heroes don't silently drag the score toward 0
    patch_impact_score = (score / scored_weight) if scored_weight > 0 else None

    team_results[str(tid)] = {
        "team_name": name,
        "patch_impact_score": round(patch_impact_score, 5) if patch_impact_score is not None else None,
        "scored_pick_weight_coverage": round(scored_weight, 4),
        "pool_heroes": breakdown,
    }

for tid in sorted(TEAM_CANONICAL, key=lambda t: -(team_results[str(t)]["patch_impact_score"] or -999)):
    r = team_results[str(tid)]
    score_str = f"{r['patch_impact_score']:+.4f}" if r["patch_impact_score"] is not None else "n/a"
    top3 = ", ".join(f"{b['hero_name']}({b['winrate_delta']:+.3f})" if b["winrate_delta"] is not None else f"{b['hero_name']}(n/a)" for b in r["pool_heroes"][:3])
    print(f"  {r['team_name']:16s} score={score_str}   top pool: {top3}")


with open(localPath("team_patch_impact.json"), "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "patch": "7.41e",
            "method": (
                "patch_impact_score is a live, data-driven signal - NOT derived from patch-notes text. "
                "For each hero, OpenDota's heroStats exposes pub_pick_trend/pub_win_trend, a rolling 7-bucket "
                "window of recent pub match pick/win counts. We split it early (buckets 0-2) vs late (buckets "
                "4-6, bucket 3 dropped as a buffer) and take the win-rate difference (late - early) as that "
                "hero's winrate_delta - a genuine 'is this hero trending up or down right now' number, not a "
                "guess from reading patch notes. Since patch 7.41e is only about a week old at collection time, "
                "this entire 7-bucket window falls within the new patch, so the early/late split captures how "
                "the pub meta is still adjusting to it, rather than a clean old-patch-vs-new-patch comparison "
                "(no reliable pre-patch baseline was available: Stratz's own per-patch winGameVersion breakdown "
                "is stale and doesn't have entries for 7.41e yet). Each team's patch_impact_score is the "
                "pick-centrality-weighted average winrate_delta across their top "
                f"{TOP_N_POOL_HEROES} most-picked heroes (league_data_mode from team_pick_ban_stats.json) - "
                "positive means their signature pool is trending toward higher win rates post-patch, negative "
                "means the opposite. This is intentionally a small-magnitude, secondary signal, not a primary "
                "rating input - it is NOT folded into compute_ratings.py's composite rating."
            ),
            "min_bucket_picks_for_reliable_winrate": MIN_BUCKET_PICKS,
            "top_n_pool_heroes": TOP_N_POOL_HEROES,
            "patch_notes_context_note": "patch_notes_context (direction/summary) on each hero is from patch_741e_hero_changes.json - a hand-curated, patch-notes-derived reference field included for human interpretability only. It is not used in the score.",
        },
        "hero_trends": {str(hid): v for hid, v in hero_trends.items()},
        "teams": team_results,
    }, f, ensure_ascii=False, indent=4)

print("\nSaved prediction/team_patch_impact.json")
