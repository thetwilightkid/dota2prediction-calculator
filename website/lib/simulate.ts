// Ports the Swiss-stage Monte Carlo simulator from
// prediction/simulate_group_stage.py, including the terminal-opponent-
// borrowing fix for stranded teams (verified this session: without it, a
// team can get stuck with an impossible partial record like 3-1 instead of
// reaching a valid terminal record). Runs entirely client-side.
import { Rng } from "./rng";
import { winProbability } from "./rating";

// The group stage is exactly 6 rounds (reconstructed round-by-round from real
// TI2025 results): rounds 1-3 within-pod, rounds 4-5 merged Swiss, round 6 the
// elimination day. Mirrors prediction/simulate_group_stage.py.
export const MAX_ROUNDS = 6;
export const WINS_TO_ADVANCE = 4;
export const LOSSES_TO_ELIMINATE = 4;
// TI's group stage splits teams into two hidden seeding pods for the first
// few rounds (confirmed from real TI2025 results and TI2026's announced Day 1
// pairings, which are 100% within-pod) - see PODDED_ROUNDS usage below.
export const PODDED_ROUNDS = 3;
// The last round is an elimination decider: every undecided team plays once,
// winner qualifies and loser is out regardless of record. That's what produces
// 3-3 finishes on both sides of the cut, and why 4-3/3-4 can't happen.
export const DECIDER_ROUND = MAX_ROUNDS - 1;

// Every way the group stage can end for a team, best to worst. "3-3a"/"3-3e"
// are the two sides of the elimination-day cut - same record, opposite fate -
// so the record string alone isn't a unique outcome.
export const OUTCOME_ORDER = ["4-0", "4-1", "4-2", "3-3a", "3-3e", "2-4", "1-4", "0-4"];
export const ADVANCING_OUTCOMES = ["4-0", "4-1", "4-2", "3-3a"];

/** Plain-language column header for an outcome key. */
export function outcomeLabel(key: string): string {
  if (key.endsWith("a")) return `${key.slice(0, -1)} (in)`;
  if (key.endsWith("e")) return `${key.slice(0, -1)} (out)`;
  return key;
}

/** Total % of simulated tournaments where a team made it out of the group stage. */
export function advanceChance(outcomePct: Record<string, number> | undefined): number {
  if (!outcomePct) return 0;
  return ADVANCING_OUTCOMES.reduce((sum, o) => sum + (outcomePct[o] ?? 0), 0);
}

export interface TeamRatingInput {
  teamId: number;
  mean: number;
  sigma: number;
}

type Record2 = [wins: number, losses: number];

function isTerminal([wins, losses]: Record2): boolean {
  return wins >= WINS_TO_ADVANCE || losses >= LOSSES_TO_ELIMINATE;
}

interface Pairing {
  a: number;
  b: number;
  updateB: boolean;
}

// Standard Swiss: teams only face opponents on the exact same record. Every
// record group in a 16-team, 8-advance Swiss has an even size, so pairing
// strictly inside groups is what guarantees exactly 8 qualifiers per trial.
function pairRound(
  activeTeams: number[],
  allTeams: number[],
  records: Map<number, Record2>,
  playedPairs: Set<string>,
  rng: Rng
): Pairing[] {
  const groups = new Map<string, number[]>();
  for (const tid of activeTeams) {
    const [w, l] = records.get(tid)!;
    const key = `${w}-${l}`;
    const group = groups.get(key);
    if (group) group.push(tid);
    else groups.set(key, [tid]);
  }

  const orderedKeys = [...groups.keys()].sort((x, y) => {
    const [xw, xl] = x.split("-").map(Number);
    const [yw, yl] = y.split("-").map(Number);
    return yw - yl - (xw - xl) || xw - yw;
  });

  const pairings: Pairing[] = [];
  let floated: number[] = [];

  for (const key of orderedKeys) {
    const pool = rng.shuffle([...floated, ...groups.get(key)!]);
    while (pool.length >= 2) {
      const a = pool.shift()!;
      let oppIdx = 0;
      for (let i = 0; i < pool.length; i++) {
        const b = pool[i];
        if (!playedPairs.has(`${a}_${b}`) && !playedPairs.has(`${b}_${a}`)) {
          oppIdx = i;
          break;
        }
      }
      const [b] = pool.splice(oppIdx, 1);
      pairings.push({ a, b, updateB: true });
    }
    floated = pool;
  }

  // Only reachable if rematch-avoidance skews a group: give the straggler a game
  // against an already-finished team rather than leaving it unsettled.
  if (floated.length > 0) {
    const a = floated[0];
    const terminalPool = allTeams.filter((tid) => tid !== a && isTerminal(records.get(tid)!));
    if (terminalPool.length > 0) {
      pairings.push({ a, b: terminalPool[rng.randInt(terminalPool.length)], updateB: false });
    }
  }

  return pairings;
}

// Elimination-day pairing: sort by standing, then pair the top half against the
// bottom half (best vs worst still alive), matching how TI2025's Day 4 was drawn.
function foldPair(activeTeams: number[], allTeams: number[], records: Map<number, Record2>, rng: Rng): Pairing[] {
  const keyed = activeTeams.map((tid) => {
    const [w, l] = records.get(tid)!;
    return { tid, diff: w - l, tiebreak: rng.random() };
  });
  keyed.sort((x, y) => (y.diff !== x.diff ? y.diff - x.diff : x.tiebreak - y.tiebreak));
  const ordered = keyed.map((k) => k.tid);

  const half = Math.floor(ordered.length / 2);
  const pairings: Pairing[] = [];
  for (let i = 0; i < half; i++) pairings.push({ a: ordered[i], b: ordered[half + i], updateB: true });

  if (ordered.length % 2 === 1) {
    const a = ordered[ordered.length - 1];
    const terminalPool = allTeams.filter((tid) => tid !== a && isTerminal(records.get(tid)!));
    if (terminalPool.length > 0) {
      pairings.push({ a, b: terminalPool[rng.randInt(terminalPool.length)], updateB: false });
    }
  }

  return pairings;
}

/** Final-standing label: 3-3 needs an a/e suffix since it exists on both sides. */
function outcomeKey(record: Record2, advanced: boolean): string {
  const [wins, losses] = record;
  if (isTerminal(record)) return `${wins}-${losses}`;
  return `${wins}-${losses}${advanced ? "a" : "e"}`;
}

function runSwissTrial(
  trialRatings: Map<number, number>,
  rng: Rng,
  forcedFirstRound?: [number, number][],
  teamPod?: Record<string, string>
): Map<number, string> {
  const records = new Map<number, Record2>();
  const advanced = new Map<number, boolean>();
  const allTeams = [...trialRatings.keys()];
  for (const tid of allTeams) {
    records.set(tid, [0, 0]);
    advanced.set(tid, false);
  }
  const playedPairs = new Set<string>();

  for (let round = 0; round < MAX_ROUNDS; round++) {
    const active = allTeams.filter((tid) => !isTerminal(records.get(tid)!));
    if (active.length === 0) break;

    const isDecider = round === DECIDER_ROUND;
    let pairings: Pairing[];
    if (round === 0 && forcedFirstRound) {
      pairings = forcedFirstRound.map(([a, b]) => ({ a, b, updateB: true }));
    } else if (isDecider) {
      pairings = foldPair(active, allTeams, records, rng);
    } else if (round < PODDED_ROUNDS && teamPod) {
      // within-pod only - safe to assume all 8 pod members are still active
      // this early (nobody can be terminal before round 4)
      pairings = [];
      for (const pod of ["A", "B"]) {
        const podTeams = active.filter((tid) => teamPod[String(tid)] === pod);
        pairings.push(...pairRound(podTeams, podTeams, records, playedPairs, rng));
      }
    } else {
      pairings = pairRound(active, allTeams, records, playedPairs, rng);
    }

    for (const { a, b, updateB } of pairings) {
      playedPairs.add(`${a}_${b}`);
      const pA = winProbability(trialRatings.get(a)!, trialRatings.get(b)!);
      const [aw, al] = records.get(a)!;
      const [bw, bl] = records.get(b)!;
      const aWon = rng.random() < pA;
      if (aWon) {
        records.set(a, [aw + 1, al]);
        if (updateB) records.set(b, [bw, bl + 1]);
      } else {
        if (updateB) records.set(b, [bw + 1, bl]);
        records.set(a, [aw, al + 1]);
      }
      if (isDecider) {
        // Elimination day: winner is through, loser is out, whatever the record.
        advanced.set(a, aWon);
        if (updateB) advanced.set(b, !aWon);
      }
    }

    for (const tid of allTeams) {
      if (records.get(tid)![0] >= WINS_TO_ADVANCE) advanced.set(tid, true);
    }
  }

  const outcomes = new Map<number, string>();
  for (const tid of allTeams) outcomes.set(tid, outcomeKey(records.get(tid)!, advanced.get(tid)!));
  return outcomes;
}

export interface SimulationOutcome {
  teamId: number;
  outcomePct: Record<string, number>; // outcome key ("4-0", "3-3a", ...) -> % of trials
}

export function runSwissSimulation(
  teamRatings: TeamRatingInput[],
  numTrials: number,
  seed = 42,
  forcedFirstRound?: [number, number][],
  teamPod?: Record<string, string>
): SimulationOutcome[] {
  const rng = new Rng(seed);
  const outcomeCounts = new Map<number, Map<string, number>>();
  for (const t of teamRatings) outcomeCounts.set(t.teamId, new Map());

  for (let trial = 0; trial < numTrials; trial++) {
    const trialRatings = new Map<number, number>();
    for (const t of teamRatings) trialRatings.set(t.teamId, rng.gauss(t.mean, t.sigma));

    const finalOutcomes = runSwissTrial(trialRatings, rng, forcedFirstRound, teamPod);
    for (const [tid, key] of finalOutcomes) {
      const counts = outcomeCounts.get(tid)!;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }

  return teamRatings.map((t) => {
    const counts = outcomeCounts.get(t.teamId)!;
    const outcomePct: Record<string, number> = {};
    for (const [key, count] of counts) {
      outcomePct[key] = Math.round((10000 * count) / numTrials) / 100;
    }
    return { teamId: t.teamId, outcomePct };
  });
}

// Single best-of-one matchup win probability (not a group-stage run) - samples
// both teams' rating distributions repeatedly and counts how often A beats B.
// Used for the Day 1 / custom "who wins this single match" tool, kept separate
// from the Swiss simulation above since it isn't part of the tracked group
// stage outcome distribution.
export function simulatePairwise(a: TeamRatingInput, b: TeamRatingInput, trials = 20000, seed = 42): number {
  const rng = new Rng(seed);
  let aWins = 0;
  for (let i = 0; i < trials; i++) {
    const ratingA = rng.gauss(a.mean, a.sigma);
    const ratingB = rng.gauss(b.mean, b.sigma);
    if (rng.random() < winProbability(ratingA, ratingB)) aWins++;
  }
  return aWins / trials;
}
