// Ports the composite-rating math from prediction/compute_ratings.py so the
// slider panel can recombine components live in the browser - no server, no
// script execution, just the same formula applied to the already-baked
// z-scored components in data/teams.ts.
import { TEAM_CANONICAL, ratingsMeta, teamRatings } from "@/data/teams";
import { teamStability } from "@/data/stability";
import { teamPatchImpact } from "@/data/patchImpact";

export interface RatingWeights {
  elo: number;
  formPretournament: number;
  formGroupStage: number;
  market: number;
  stability: number;
  patchImpact: number;
}

// Matches compute_ratings.py's W_ELO/W_FORM_PRETOURNAMENT/W_FORM_GROUPSTAGE/W_MARKET
// defaults; the two extra terms default to 0 so the default-weights output exactly
// reproduces team_composite_ratings.json's precomputed composite_mean/sigma.
export const DEFAULT_WEIGHTS: RatingWeights = {
  elo: 0.5,
  formPretournament: 0.15,
  formGroupStage: 0.15,
  market: 0.2,
  stability: 0,
  patchImpact: 0,
};

export interface TeamCompositeResult {
  teamId: number;
  teamName: string;
  compositeMean: number;
  compositeSigma: number;
  ratingScaleMean: number;
  ratingScaleSigma: number;
  zElo: number;
  zFormPretournament: number;
  zFormGroupStage: number;
  zMarket: number;
  zStability: number;
  zPatchImpact: number;
}

function populationZScores(values: Record<number, number | null>): Record<number, number> {
  const nums = Object.values(values).filter((v): v is number => v !== null);
  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  const variance = nums.reduce((a, b) => a + (b - mean) ** 2, 0) / nums.length;
  const std = Math.sqrt(variance);
  const out: Record<number, number> = {};
  for (const [tid, v] of Object.entries(values)) {
    out[Number(tid)] = v !== null && std > 0 ? (v - mean) / std : 0;
  }
  return out;
}

// Stability isn't a single number in the source data (choke_rate lower-is-better,
// comeback_rate higher-is-better) - "resilience" = comeback_rate - choke_rate
// combines both into one higher-is-better signal, then z-scored across the 16 teams.
// patch_impact_score is likewise z-scored for consistent scale with elo/form/market.
// Neither has a native uncertainty measure (unlike glicko_phi or the decayed-winrate
// standard error), so a fixed moderate sigma (0.5, in z-score units) is used as a
// simplification when a slider gives them nonzero weight - documented here rather
// than presented as rigorously derived.
const STABILITY_PATCH_FIXED_SIGMA_Z = 0.5;

export function computeComposite(weights: RatingWeights = DEFAULT_WEIGHTS): TeamCompositeResult[] {
  const resilienceByTeam: Record<number, number | null> = {};
  const patchByTeam: Record<number, number | null> = {};
  for (const tidStr of Object.keys(TEAM_CANONICAL)) {
    const tid = Number(tidStr);
    const s = teamStability[String(tid)];
    resilienceByTeam[tid] =
      s?.comeback_rate != null && s?.choke_rate != null ? s.comeback_rate - s.choke_rate : null;
    const p = teamPatchImpact[String(tid)];
    patchByTeam[tid] = p?.patch_impact_score ?? null;
  }
  const zStability = populationZScores(resilienceByTeam);
  const zPatch = populationZScores(patchByTeam);

  const { glicko_mean, glicko_std } = ratingsMeta;

  return Object.entries(TEAM_CANONICAL).map(([tidStr, teamName]) => {
    const tid = Number(tidStr);
    const r = teamRatings[tidStr];

    const compositeMean =
      weights.elo * r.z_elo +
      weights.formPretournament * r.z_form_pretournament +
      weights.formGroupStage * r.z_form_groupstage +
      weights.market * r.z_market +
      weights.stability * zStability[tid] +
      weights.patchImpact * zPatch[tid];

    const compositeSigma = Math.sqrt(
      weights.elo ** 2 * r.sigma_elo_z ** 2 +
        weights.formPretournament ** 2 * r.sigma_form_pretournament_z ** 2 +
        weights.formGroupStage ** 2 * r.sigma_form_groupstage_z ** 2 +
        weights.market ** 2 * r.sigma_market_z ** 2 +
        weights.stability ** 2 * STABILITY_PATCH_FIXED_SIGMA_Z ** 2 +
        weights.patchImpact ** 2 * STABILITY_PATCH_FIXED_SIGMA_Z ** 2
    );

    return {
      teamId: tid,
      teamName,
      compositeMean,
      compositeSigma,
      ratingScaleMean: glicko_mean + compositeMean * glicko_std,
      ratingScaleSigma: compositeSigma * glicko_std,
      zElo: r.z_elo,
      zFormPretournament: r.z_form_pretournament,
      zFormGroupStage: r.z_form_groupstage,
      zMarket: r.z_market,
      zStability: zStability[tid],
      zPatchImpact: zPatch[tid],
    };
  });
}

// Standard Elo/Glicko-style logistic win probability from rating-scale values -
// mirrors simulate_group_stage.py's winProbability().
export function winProbability(ratingA: number, ratingB: number): number {
  return 1 / (1 + 10 ** (-(ratingA - ratingB) / 400));
}
