"use client";

import Link from "next/link";
import styles from "./PlayoffBracketDiagram.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import type { PredictedMatch } from "@/lib/simulatePlayoffs";

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

function TeamRow({ teamId, winProb, isWinner }: { teamId: number; winProb: number; isWinner: boolean }) {
  return (
    <div className={`${styles.slotRow} ${isWinner ? styles.slotRowFavored : ""}`}>
      <Link href={`/teams/${teamId}`} className={styles.slotTeam}>
        <TeamLogo teamId={teamId} size="sm" />
        <span className={styles.slotName}>{TEAM_CANONICAL[teamId]}</span>
      </Link>
      <span className="mono muted">{(winProb * 100).toFixed(0)}%</span>
    </div>
  );
}

function MatchBox({ matchId, predicted }: { matchId: string; predicted: Record<string, PredictedMatch> }) {
  const m = predicted[matchId];
  const bestOf = BEST_OF[matchId];
  if (!m) {
    return (
      <div className={styles.matchWrap}>
        <div className={styles.matchBox}>
          <div className={styles.slotRow}>
            <span className="muted">TBD</span>
          </div>
        </div>
      </div>
    );
  }
  const winProbA = m.winner === m.a ? m.winProb : 1 - m.winProb;
  const winProbB = m.winner === m.b ? m.winProb : 1 - m.winProb;

  return (
    <div className={styles.matchWrap}>
      <div className={styles.matchBox}>
        <TeamRow teamId={m.a} winProb={winProbA} isWinner={m.winner === m.a} />
        <TeamRow teamId={m.b} winProb={winProbB} isWinner={m.winner === m.b} />
      </div>
      <div className={styles.matchMeta}>
        <span className="muted">Bo{bestOf}</span>
      </div>
    </div>
  );
}

export default function PlayoffBracketDiagram({ predicted }: { predicted: Record<string, PredictedMatch> }) {
  return (
    <div className={styles.diagram}>
      <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        One coherent predicted path through the bracket - at every match, whoever&apos;s favored is taken as the
        winner and is exactly who moves on, so a team shown losing here is always the same team you&apos;ll see in
        the lower bracket slot they drop to. The percentage is that match&apos;s win chance.
      </p>
      <div className={styles.section}>
        <div className={styles.columns}>
          {UB_COLUMNS.map((col) => (
            <div key={col.label} className={styles.column}>
              <div className={styles.columnHeader}>{col.label}</div>
              <div className={styles.columnBody}>
                {col.matches.map((mid) => (
                  <MatchBox key={mid} matchId={mid} predicted={predicted} />
                ))}
              </div>
            </div>
          ))}
          <div className={styles.column}>
            <div className={styles.columnHeader}>Grand Final</div>
            <div className={styles.columnBody}>
              <MatchBox matchId="grand_final" predicted={predicted} />
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
                  <MatchBox key={mid} matchId={mid} predicted={predicted} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
