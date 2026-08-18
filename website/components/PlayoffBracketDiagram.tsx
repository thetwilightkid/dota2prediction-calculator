"use client";

import Link from "next/link";
import styles from "./PlayoffBracketDiagram.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import type { PlayoffSlotDistribution } from "@/data/playoffSimulation";

interface Column {
  label: string;
  matches: string[];
}

const UB_COLUMNS: Column[] = [
  { label: "UB Quarterfinals", matches: ["ub_r1_1", "ub_r1_2", "ub_r1_3", "ub_r1_4"] },
  { label: "Upper Bracket Semifinals", matches: ["ub_r2_1", "ub_r2_2"] },
  { label: "Upper Bracket Final", matches: ["ub_final"] },
];

const LB_COLUMNS: Column[] = [
  { label: "Lower Bracket Round 1", matches: ["lb_r1_1", "lb_r1_2"] },
  { label: "Lower Bracket Quarterfinals", matches: ["lb_r2_1", "lb_r2_2"] },
  { label: "Lower Bracket Semifinals", matches: ["lb_r3"] },
  { label: "Lower Bracket Final", matches: ["lb_final"] },
];

const BEST_OF: Record<string, number> = {
  ub_r1_1: 3, ub_r1_2: 3, ub_r1_3: 3, ub_r1_4: 3,
  ub_r2_1: 3, ub_r2_2: 3, ub_final: 3,
  lb_r1_1: 3, lb_r1_2: 3, lb_r2_1: 3, lb_r2_2: 3, lb_r3: 3, lb_final: 3,
  grand_final: 5,
};

const CANDIDATES_PER_SLOT = 2;

interface Candidate {
  teamId: number;
  reachPct: number;
  winPct: number;
}

// Top N candidates for a slot, each carrying BOTH numbers directly from the
// same per-team trial data: reachPct (how often this team ends up in this
// slot at all) and winPct (how often this exact team wins this exact match,
// unconditionally across every trial). Showing more than one candidate per
// slot matters - a team that's a strong #2 almost everywhere (rather than a
// clean #1 anywhere) would otherwise vanish from the whole diagram even
// though it has real presence throughout the bracket.
function topCandidates(slotDist: Record<string, number> | undefined, winnerDist: Record<string, number> | undefined, exclude?: number): Candidate[] {
  if (!slotDist) return [];
  return Object.entries(slotDist)
    .filter(([tid]) => Number(tid) !== exclude)
    .sort((a, b) => b[1] - a[1])
    .slice(0, CANDIDATES_PER_SLOT)
    .map(([tid, pct]) => ({ teamId: Number(tid), reachPct: pct, winPct: winnerDist?.[tid] ?? 0 }));
}

function CandidateRow({ c, isTopWinner, showReach }: { c: Candidate; isTopWinner: boolean; showReach: boolean }) {
  return (
    <div className={`${styles.slotRow} ${isTopWinner ? styles.slotRowFavored : ""}`}>
      <Link href={`/teams/${c.teamId}`} className={styles.slotTeam}>
        <TeamLogo teamId={c.teamId} size="sm" />
        <span className={styles.slotName}>{TEAM_CANONICAL[c.teamId]}</span>
      </Link>
      <span className={styles.slotStats}>
        {showReach && <span className="mono muted">{c.reachPct.toFixed(0)}% reach</span>}
        <span className="mono">{c.winPct.toFixed(0)}% win</span>
      </span>
    </div>
  );
}

function SlotGroup({ candidates, topWinnerTeamId }: { candidates: Candidate[]; topWinnerTeamId: number | null }) {
  if (candidates.length === 0) {
    return (
      <div className={styles.slotRow}>
        <span className="muted">TBD</span>
      </div>
    );
  }
  // Only show the "reach" number when it's genuinely informative - a slot
  // with a single certain occupant (the real UB R1 seeding) would otherwise
  // redundantly say "100% reach" next to a team that's simply confirmed.
  const showReach = candidates.length > 1 || candidates[0].reachPct < 99.5;
  return (
    <div className={styles.slotGroup}>
      {candidates.map((c) => (
        <CandidateRow key={c.teamId} c={c} isTopWinner={c.teamId === topWinnerTeamId} showReach={showReach} />
      ))}
    </div>
  );
}

function MatchBox({ matchId, slots }: { matchId: string; slots: Record<string, PlayoffSlotDistribution> }) {
  const dist = slots[matchId];
  const candidatesA = topCandidates(dist?.a, dist?.winner);
  // Exclude slot A's top pick from slot B's candidates - the two marginal
  // distributions are computed independently across trials, so their
  // individual top picks CAN coincide (e.g. the strongest team is plausibly
  // the most likely occupant of both bracket paths into the Grand Final)
  // even though within any single trial the two slots are always different
  // teams. Showing the same team on both sides would misleadingly read as
  // "they play themselves."
  const candidatesB = topCandidates(dist?.b, dist?.winner, candidatesA[0]?.teamId);
  const bestOf = BEST_OF[matchId];

  // Highlight whichever of the ACTUALLY DISPLAYED candidates has the highest
  // win%, rather than a separately-computed global argmax that could name a
  // team not shown in either slot at all.
  const allShown = [...candidatesA, ...candidatesB];
  const topWinner = allShown.length > 0 ? allShown.reduce((best, c) => (c.winPct > best.winPct ? c : best)) : null;

  return (
    <div className={styles.matchWrap}>
      <div className={styles.matchBox}>
        <SlotGroup candidates={candidatesA} topWinnerTeamId={topWinner?.teamId ?? null} />
        <div className={styles.slotDivider} />
        <SlotGroup candidates={candidatesB} topWinnerTeamId={topWinner?.teamId ?? null} />
      </div>
      <div className={styles.matchMeta}>
        <span className="muted">Bo{bestOf}</span>
      </div>
    </div>
  );
}

export default function PlayoffBracketDiagram({ slots }: { slots: Record<string, PlayoffSlotDistribution> }) {
  return (
    <div className={styles.diagram}>
      <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        Each team shown carries two numbers: <strong>reach</strong> is how often they end up in that exact slot at
        all (win their way there); <strong>win</strong> is how often they go on to win that specific match, across
        every simulated bracket. Up to 2 likely teams are shown per slot, since a team can matter throughout the
        bracket without ever being the single most likely pick anywhere.
      </p>
      <div className={styles.section}>
        <div className={styles.columns}>
          {UB_COLUMNS.map((col) => (
            <div key={col.label} className={styles.column}>
              <div className={styles.columnHeader}>{col.label}</div>
              <div className={styles.columnBody}>
                {col.matches.map((mid) => (
                  <MatchBox key={mid} matchId={mid} slots={slots} />
                ))}
              </div>
            </div>
          ))}
          <div className={styles.column}>
            <div className={styles.columnHeader}>Grand Final</div>
            <div className={styles.columnBody}>
              <MatchBox matchId="grand_final" slots={slots} />
            </div>
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.columns}>
          {LB_COLUMNS.map((col) => (
            <div key={col.label} className={styles.column}>
              <div className={styles.columnHeader}>{col.label}</div>
              <div className={styles.columnBody}>
                {col.matches.map((mid) => (
                  <MatchBox key={mid} matchId={mid} slots={slots} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
