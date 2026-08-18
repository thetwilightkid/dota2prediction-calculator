"use client";

import { useMemo } from "react";
import Link from "next/link";
import styles from "./PlayoffBracketClient.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { playoffSimulation, playoffSimulationMeta, PLAYOFF_TEAM_IDS } from "@/data/playoffSimulation";

const REACH_COLUMNS: [string, string][] = [
  ["ub_r1_win", "Won UB R1"],
  ["ub_r2_win", "Won UB R2"],
  ["ub_final_reach", "Reached UB Final"],
  ["ub_final_win", "Won UB Final"],
  ["lb_final_reach", "Reached LB Final"],
  ["grand_final_reach", "Reached Grand Final"],
  ["champion", "Champion"],
];

const OUTCOME_COLUMNS: [string, string][] = [
  ["eliminated_lb_r1", "Out: LB R1"],
  ["eliminated_lb_r2", "Out: LB R2"],
  ["eliminated_lb_r3", "Out: LB R3"],
  ["eliminated_lb_final", "Out: LB Final"],
  ["runner_up", "Runner-up"],
  ["champion", "Champion"],
];

export default function PlayoffBracketClient() {
  const orderedTeamIds = useMemo(
    () => [...PLAYOFF_TEAM_IDS].sort((a, b) => (playoffSimulation[b]?.reach_pct.champion ?? 0) - (playoffSimulation[a]?.reach_pct.champion ?? 0)),
    []
  );

  return (
    <div>
      <div className={`${styles.seeding} card`}>
        <h3 style={{ marginBottom: 10 }}>Upper Bracket Round 1 (real, announced seeding)</h3>
        <div className={styles.seedGrid}>
          {playoffSimulationMeta.ub_r1_pairings.map(([a, b], i) => (
            <div key={i} className={styles.seedMatch}>
              <Link href={`/teams/${a}`} className={styles.seedTeam}>
                <TeamLogo teamId={a} />
                {TEAM_CANONICAL[a]}
              </Link>
              <span className="muted">vs</span>
              <Link href={`/teams/${b}`} className={styles.seedTeam}>
                <TeamLogo teamId={b} />
                {TEAM_CANONICAL[b]}
              </Link>
            </div>
          ))}
        </div>
      </div>

      <h3 style={{ margin: "20px 0 8px" }}>Chance of reaching / winning each stage</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        Based on {playoffSimulationMeta.num_trials.toLocaleString()} simulated brackets. &ldquo;Reached&rdquo; means
        played in that match (win or lose); the win columns mean they won it.
      </p>
      <div className="tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Team</th>
              {REACH_COLUMNS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orderedTeamIds.map((tid) => {
              const result = playoffSimulation[tid];
              return (
                <tr key={tid}>
                  <td>
                    <Link href={`/teams/${tid}`} className={styles.teamCell}>
                      <TeamLogo teamId={tid} />
                      {TEAM_CANONICAL[tid]}
                    </Link>
                  </td>
                  {REACH_COLUMNS.map(([key]) => (
                    <td key={key} className={key === "champion" ? "mono" : "mono muted"}>
                      {result?.reach_pct[key] != null ? `${result.reach_pct[key].toFixed(1)}%` : "-"}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h3 style={{ margin: "20px 0 8px" }}>Where each team is most likely to finish</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        Mutually exclusive - each team&apos;s row sums to ~100%. A team can only be eliminated in the lower bracket;
        losing an upper-bracket match just drops them down a round instead of knocking them out.
      </p>
      <div className="tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Team</th>
              {OUTCOME_COLUMNS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orderedTeamIds.map((tid) => {
              const result = playoffSimulation[tid];
              return (
                <tr key={tid}>
                  <td>
                    <Link href={`/teams/${tid}`} className={styles.teamCell}>
                      <TeamLogo teamId={tid} />
                      {TEAM_CANONICAL[tid]}
                    </Link>
                  </td>
                  {OUTCOME_COLUMNS.map(([key]) => (
                    <td key={key} className={key === "champion" || key === "runner_up" ? "mono" : "mono muted"}>
                      {result?.outcome_pct[key] != null ? `${result.outcome_pct[key].toFixed(1)}%` : "-"}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
