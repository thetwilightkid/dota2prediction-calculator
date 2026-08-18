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

function topEntry(dist: Record<string, number> | undefined, exclude?: number): { teamId: number; pct: number } | null {
  if (!dist) return null;
  const entries = Object.entries(dist).filter(([tid]) => Number(tid) !== exclude);
  if (entries.length === 0) return null;
  const [tid, pct] = entries.reduce((best, cur) => (cur[1] > best[1] ? cur : best));
  return { teamId: Number(tid), pct };
}

function SlotRow({ top, isWinner }: { top: { teamId: number; pct: number } | null; isWinner: boolean }) {
  if (!top) {
    return (
      <div className={styles.slotRow}>
        <span className="muted">TBD</span>
      </div>
    );
  }
  return (
    <div className={`${styles.slotRow} ${isWinner ? styles.slotRowFavored : ""}`}>
      <Link href={`/teams/${top.teamId}`} className={styles.slotTeam}>
        <TeamLogo teamId={top.teamId} size="sm" />
        <span className={styles.slotName}>{TEAM_CANONICAL[top.teamId]}</span>
      </Link>
      <span className="mono muted">{top.pct.toFixed(0)}%</span>
    </div>
  );
}

function MatchBox({ matchId, slots }: { matchId: string; slots: Record<string, PlayoffSlotDistribution> }) {
  const dist = slots[matchId];
  const topA = topEntry(dist?.a);
  // Exclude slot A's pick from slot B's - the two marginal distributions are
  // computed independently across trials, so their individual argmax CAN
  // coincide (e.g. the strongest team is plausibly the most likely occupant
  // of both bracket paths into the Grand Final) even though within any single
  // trial the two slots are always different teams. Showing the same team
  // twice would misleadingly read as "they play themselves."
  const topB = topEntry(dist?.b, topA?.teamId);
  const topWinner = topEntry(dist?.winner);
  const bestOf = BEST_OF[matchId];

  return (
    <div className={styles.matchWrap}>
      <div className={styles.matchBox}>
        <SlotRow top={topA} isWinner={!!topA && topWinner?.teamId === topA.teamId} />
        <SlotRow top={topB} isWinner={!!topB && topWinner?.teamId === topB.teamId} />
      </div>
      <div className={styles.matchMeta}>
        <span className="muted">Bo{bestOf}</span>
        {topWinner && (
          <span className="muted">
            {TEAM_CANONICAL[topWinner.teamId]} favored ({topWinner.pct.toFixed(0)}%)
          </span>
        )}
      </div>
    </div>
  );
}

export default function PlayoffBracketDiagram({ slots }: { slots: Record<string, PlayoffSlotDistribution> }) {
  return (
    <div className={styles.diagram}>
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
