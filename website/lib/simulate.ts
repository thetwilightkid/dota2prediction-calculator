// Ports the Swiss-stage Monte Carlo simulator from
// prediction/simulate_group_stage.py, including the terminal-opponent-
// borrowing fix for stranded teams (verified this session: without it, a
// team can get stuck with an impossible partial record like 3-1 instead of
// reaching a valid terminal record). Runs entirely client-side.
import { Rng } from "./rng";
import { winProbability } from "./rating";

export const MAX_ROUNDS = 5;
export const WINS_TO_ADVANCE = 4;
export const LOSSES_TO_ELIMINATE = 4;

export interface TeamRatingInput {
  teamId: number;
  mean: number;
  sigma: number;
}

type Record2 = [wins: number, losses: number];

function isTerminal([wins, losses]: Record2): boolean {
  return wins >= WINS_TO_ADVANCE || losses >= LOSSES_TO_ELIMINATE || wins + losses >= MAX_ROUNDS;
}

interface Pairing {
  a: number;
  b: number;
  updateB: boolean;
}

function pairRound(
  activeTeams: number[],
  allTeams: number[],
  records: Map<number, Record2>,
  playedPairs: Set<string>,
  rng: Rng
): Pairing[] {
  // Python's sorted(key=lambda tid: (-(diff), rng.random())) evaluates the key
  // (including one rng.random() call) exactly once per element before sorting -
  // replicate that by precomputing the tiebreak values first, then sorting.
  const keyed = activeTeams.map((tid) => {
    const [w, l] = records.get(tid)!;
    return { tid, diff: w - l, tiebreak: rng.random() };
  });
  keyed.sort((x, y) => (y.diff !== x.diff ? y.diff - x.diff : x.tiebreak - y.tiebreak));
  const ordered = keyed.map((k) => k.tid);

  const pairings: Pairing[] = [];
  const unpaired = [...ordered];

  while (unpaired.length > 0) {
    const a = unpaired.shift()!;
    if (unpaired.length === 0) {
      const terminalPool = allTeams.filter((tid) => tid !== a && isTerminal(records.get(tid)!));
      if (terminalPool.length > 0) {
        const b = terminalPool[rng.randInt(terminalPool.length)];
        pairings.push({ a, b, updateB: false });
      }
      break;
    }

    let oppIdx = 0;
    for (let i = 0; i < unpaired.length; i++) {
      const b = unpaired[i];
      if (!playedPairs.has(`${a}_${b}`) && !playedPairs.has(`${b}_${a}`)) {
        oppIdx = i;
        break;
      }
    }
    const [b] = unpaired.splice(oppIdx, 1);
    pairings.push({ a, b, updateB: true });
  }

  return pairings;
}

function runSwissTrial(trialRatings: Map<number, number>, rng: Rng): Map<number, Record2> {
  const records = new Map<number, Record2>();
  const allTeams = [...trialRatings.keys()];
  for (const tid of allTeams) records.set(tid, [0, 0]);
  const playedPairs = new Set<string>();

  for (let round = 0; round < MAX_ROUNDS; round++) {
    const active = allTeams.filter((tid) => !isTerminal(records.get(tid)!));
    if (active.length === 0) break;

    const pairings = pairRound(active, allTeams, records, playedPairs, rng);
    for (const { a, b, updateB } of pairings) {
      playedPairs.add(`${a}_${b}`);
      const pA = winProbability(trialRatings.get(a)!, trialRatings.get(b)!);
      const [aw, al] = records.get(a)!;
      const [bw, bl] = records.get(b)!;
      if (rng.random() < pA) {
        records.set(a, [aw + 1, al]);
        if (updateB) records.set(b, [bw, bl + 1]);
      } else {
        if (updateB) records.set(b, [bw + 1, bl]);
        records.set(a, [aw, al + 1]);
      }
    }
  }

  return records;
}

export interface SimulationOutcome {
  teamId: number;
  outcomePct: Record<string, number>; // "4-0" -> percentage of trials
}

export function runSwissSimulation(
  teamRatings: TeamRatingInput[],
  numTrials: number,
  seed = 42
): SimulationOutcome[] {
  const rng = new Rng(seed);
  const outcomeCounts = new Map<number, Map<string, number>>();
  for (const t of teamRatings) outcomeCounts.set(t.teamId, new Map());

  for (let trial = 0; trial < numTrials; trial++) {
    const trialRatings = new Map<number, number>();
    for (const t of teamRatings) trialRatings.set(t.teamId, rng.gauss(t.mean, t.sigma));

    const finalRecords = runSwissTrial(trialRatings, rng);
    for (const [tid, [w, l]] of finalRecords) {
      const key = `${w}-${l}`;
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
