// Ports the playoff bracket Monte Carlo simulator from prediction/
// simulate_playoffs.py so it can be re-run client-side with the user's own
// slider weights (mirrors how lib/simulate.ts's runSwissSimulation backs the
// Group Stage page's live re-simulation). Runs entirely in the browser.
import { Rng } from "./rng";
import { winProbability } from "./rating";

interface MatchSpec {
  bestOf: number;
  winnerTo: string | null;
  loserTo: string | null;
}

// Same 14-match routing as simulate_playoffs.py's BRACKET_MATCHES - see that
// file's module docstring for the full routing derivation from the real
// bracket graphic.
export const BRACKET_MATCHES: Record<string, MatchSpec> = {
  ub_r1_1: { bestOf: 3, winnerTo: "ub_r2_1:a", loserTo: "lb_r1_1:a" },
  ub_r1_2: { bestOf: 3, winnerTo: "ub_r2_1:b", loserTo: "lb_r1_1:b" },
  ub_r1_3: { bestOf: 3, winnerTo: "ub_r2_2:a", loserTo: "lb_r1_2:a" },
  ub_r1_4: { bestOf: 3, winnerTo: "ub_r2_2:b", loserTo: "lb_r1_2:b" },

  ub_r2_1: { bestOf: 3, winnerTo: "ub_final:a", loserTo: "lb_r2_2:a" },
  ub_r2_2: { bestOf: 3, winnerTo: "ub_final:b", loserTo: "lb_r2_1:a" },

  lb_r1_1: { bestOf: 3, winnerTo: "lb_r2_1:b", loserTo: null },
  lb_r1_2: { bestOf: 3, winnerTo: "lb_r2_2:b", loserTo: null },

  ub_final: { bestOf: 3, winnerTo: "grand_final:a", loserTo: "lb_final:b" },

  lb_r2_1: { bestOf: 3, winnerTo: "lb_r3:a", loserTo: null },
  lb_r2_2: { bestOf: 3, winnerTo: "lb_r3:b", loserTo: null },

  lb_r3: { bestOf: 3, winnerTo: "lb_final:a", loserTo: null },

  lb_final: { bestOf: 3, winnerTo: "grand_final:b", loserTo: null },

  grand_final: { bestOf: 5, winnerTo: null, loserTo: null },
};

export const MATCH_ORDER = [
  "ub_r1_1", "ub_r1_2", "ub_r1_3", "ub_r1_4",
  "ub_r2_1", "ub_r2_2", "lb_r1_1", "lb_r1_2",
  "ub_final", "lb_r2_1", "lb_r2_2",
  "lb_r3",
  "lb_final",
  "grand_final",
];

const ELIMINATION_LABEL: Record<string, string> = {
  lb_r1_1: "eliminated_lb_r1", lb_r1_2: "eliminated_lb_r1",
  lb_r2_1: "eliminated_lb_r2", lb_r2_2: "eliminated_lb_r2",
  lb_r3: "eliminated_lb_r3",
  lb_final: "eliminated_lb_final",
};

export const REACH_KEYS = ["ub_r1_win", "ub_r2_win", "ub_final_reach", "ub_final_win", "lb_final_reach", "grand_final_reach", "champion"];
export const OUTCOME_KEYS = ["eliminated_lb_r1", "eliminated_lb_r2", "eliminated_lb_r3", "eliminated_lb_final", "runner_up", "champion"];

interface MatchResult {
  a: number;
  b: number;
  winner: number;
  loser: number;
}

function playSeries(ratingA: number, ratingB: number, bestOf: number, rng: Rng): boolean {
  const winsNeeded = Math.floor(bestOf / 2) + 1;
  const pA = winProbability(ratingA, ratingB);
  let winsA = 0;
  let winsB = 0;
  while (winsA < winsNeeded && winsB < winsNeeded) {
    if (rng.random() < pA) winsA++;
    else winsB++;
  }
  return winsA > winsB;
}

function runBracketTrial(trialRatings: Map<number, number>, rng: Rng, forcedUbR1: [number, number][]): Record<string, MatchResult> {
  const slotFill = new Map<string, number>();
  forcedUbR1.forEach(([a, b], i) => {
    slotFill.set(`ub_r1_${i + 1}:a`, a);
    slotFill.set(`ub_r1_${i + 1}:b`, b);
  });

  const results: Record<string, MatchResult> = {};
  for (const matchId of MATCH_ORDER) {
    const spec = BRACKET_MATCHES[matchId];
    const teamA = slotFill.get(`${matchId}:a`)!;
    const teamB = slotFill.get(`${matchId}:b`)!;
    const aWins = playSeries(trialRatings.get(teamA)!, trialRatings.get(teamB)!, spec.bestOf, rng);
    const winner = aWins ? teamA : teamB;
    const loser = aWins ? teamB : teamA;
    results[matchId] = { a: teamA, b: teamB, winner, loser };

    if (spec.winnerTo) slotFill.set(spec.winnerTo, winner);
    if (spec.loserTo) slotFill.set(spec.loserTo, loser);
  }
  return results;
}

export interface TeamRatingInput {
  teamId: number;
  mean: number;
  sigma: number;
}

export interface PlayoffOutcome {
  teamId: number;
  reachPct: Record<string, number>;
  outcomePct: Record<string, number>;
}

export interface PredictedMatch {
  a: number;
  b: number;
  winner: number;
  loser: number;
  winProb: number;
}

// A single deterministic walk through the bracket - at every match, the side
// with the higher win probability (compared using each team's MEAN rating
// only, no sampling) is taken as the winner, and that exact team is what
// fills the next slot they're routed to. Mirrors simulate_playoffs.py's
// predictBracket() - see that function's docstring for why this (one
// coherent path) is used for the diagram instead of aggregating independent
// per-slot Monte Carlo marginals, which don't have to agree with each other
// at all (a team shown losing a match wouldn't necessarily be the same team
// shown occupying the next slot they drop to).
export function predictBracket(teamRatings: TeamRatingInput[], forcedUbR1: [number, number][]): Record<string, PredictedMatch> {
  const ratingByTeam = new Map(teamRatings.map((t) => [t.teamId, t.mean]));
  const slotFill = new Map<string, number>();
  forcedUbR1.forEach(([a, b], i) => {
    slotFill.set(`ub_r1_${i + 1}:a`, a);
    slotFill.set(`ub_r1_${i + 1}:b`, b);
  });

  const predicted: Record<string, PredictedMatch> = {};
  for (const matchId of MATCH_ORDER) {
    const spec = BRACKET_MATCHES[matchId];
    const teamA = slotFill.get(`${matchId}:a`)!;
    const teamB = slotFill.get(`${matchId}:b`)!;
    const pA = winProbability(ratingByTeam.get(teamA)!, ratingByTeam.get(teamB)!);
    const aWins = pA >= 0.5;
    const winner = aWins ? teamA : teamB;
    const loser = aWins ? teamB : teamA;
    const winProb = aWins ? pA : 1 - pA;
    predicted[matchId] = { a: teamA, b: teamB, winner, loser, winProb };

    if (spec.winnerTo) slotFill.set(spec.winnerTo, winner);
    if (spec.loserTo) slotFill.set(spec.loserTo, loser);
  }
  return predicted;
}

export function runPlayoffSimulation(
  teamRatings: TeamRatingInput[],
  numTrials: number,
  seed: number,
  forcedUbR1: [number, number][]
): PlayoffOutcome[] {
  const rng = new Rng(seed);
  const reachCounts = new Map<number, Map<string, number>>();
  const outcomeCounts = new Map<number, Map<string, number>>();
  for (const t of teamRatings) {
    reachCounts.set(t.teamId, new Map());
    outcomeCounts.set(t.teamId, new Map());
  }

  for (let trial = 0; trial < numTrials; trial++) {
    const trialRatings = new Map<number, number>();
    for (const t of teamRatings) trialRatings.set(t.teamId, rng.gauss(t.mean, t.sigma));

    const results = runBracketTrial(trialRatings, rng, forcedUbR1);

    for (const t of teamRatings) {
      const tid = t.teamId;
      const appearances = MATCH_ORDER.map((mid, i) => (results[mid].a === tid || results[mid].b === tid ? i : -1)).filter((i) => i >= 0);
      const lastMatch = MATCH_ORDER[Math.max(...appearances)];
      const wonLast = results[lastMatch].winner === tid;

      const reach = reachCounts.get(tid)!;
      const bump = (key: string) => reach.set(key, (reach.get(key) ?? 0) + 1);

      const ubR1Id = ["ub_r1_1", "ub_r1_2", "ub_r1_3", "ub_r1_4"].find((mid) => results[mid].a === tid || results[mid].b === tid)!;
      if (results[ubR1Id].winner === tid) bump("ub_r1_win");

      const ubR2Id = ["ub_r2_1", "ub_r2_2"].find((mid) => results[mid].a === tid || results[mid].b === tid);
      if (ubR2Id && results[ubR2Id].winner === tid) bump("ub_r2_win");

      if (results.ub_final.a === tid || results.ub_final.b === tid) {
        bump("ub_final_reach");
        if (results.ub_final.winner === tid) bump("ub_final_win");
      }
      if (results.lb_final.a === tid || results.lb_final.b === tid) bump("lb_final_reach");
      if (results.grand_final.a === tid || results.grand_final.b === tid) {
        bump("grand_final_reach");
        if (results.grand_final.winner === tid) bump("champion");
      }

      const outcome = outcomeCounts.get(tid)!;
      if (lastMatch === "grand_final") {
        const key = wonLast ? "champion" : "runner_up";
        outcome.set(key, (outcome.get(key) ?? 0) + 1);
      } else {
        const key = ELIMINATION_LABEL[lastMatch];
        outcome.set(key, (outcome.get(key) ?? 0) + 1);
      }
    }
  }

  return teamRatings.map((t) => {
    const reach = reachCounts.get(t.teamId)!;
    const outcome = outcomeCounts.get(t.teamId)!;
    const reachPct: Record<string, number> = {};
    for (const k of REACH_KEYS) reachPct[k] = Math.round((10000 * (reach.get(k) ?? 0)) / numTrials) / 100;
    const outcomePct: Record<string, number> = {};
    for (const k of OUTCOME_KEYS) outcomePct[k] = Math.round((10000 * (outcome.get(k) ?? 0)) / numTrials) / 100;
    return { teamId: t.teamId, reachPct, outcomePct };
  });
}
