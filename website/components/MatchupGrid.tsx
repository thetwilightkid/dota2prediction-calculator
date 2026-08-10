"use client";

import { useState } from "react";
import Link from "next/link";
import styles from "./MatchupGrid.module.css";
import { TEAM_CANONICAL } from "@/data/teams";
import { h2hGrid, type H2HCell } from "@/data/h2hGrid";

const TEAM_IDS = Object.keys(TEAM_CANONICAL).map(Number);

function cellColor(cell: H2HCell | undefined): string {
  if (!cell || cell.matches_played === 0 || cell.decayed_win_rate == null) return "transparent";
  // 0.0 -> red, 0.5 -> neutral surface, 1.0 -> green
  const wr = cell.decayed_win_rate;
  if (wr >= 0.5) {
    const t = Math.min(1, (wr - 0.5) / 0.5);
    return `rgba(63, 185, 80, ${0.12 + t * 0.45})`;
  }
  const t = Math.min(1, (0.5 - wr) / 0.5);
  return `rgba(248, 81, 73, ${0.12 + t * 0.45})`;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function MatchupGrid() {
  const [selected, setSelected] = useState<{ row: number; col: number } | null>(null);

  const selectedCell = selected ? h2hGrid[String(selected.row)]?.[String(selected.col)] : null;

  return (
    <div className={styles.wrap}>
      <div className={`${styles.gridScroll} tableWrap`}>
        <table className={styles.grid}>
          <thead>
            <tr>
              <th className={styles.corner} />
              {TEAM_IDS.map((tid) => (
                <th key={tid} className={styles.colHeader}>
                  {TEAM_CANONICAL[tid]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TEAM_IDS.map((rowId) => (
              <tr key={rowId}>
                <th className={styles.rowHeader}>
                  <Link href={`/teams/${rowId}`}>{TEAM_CANONICAL[rowId]}</Link>
                </th>
                {TEAM_IDS.map((colId) => {
                  if (rowId === colId) return <td key={colId} className={styles.diagonal} />;
                  const cell = h2hGrid[String(rowId)]?.[String(colId)];
                  const isSelected = selected?.row === rowId && selected?.col === colId;
                  return (
                    <td
                      key={colId}
                      className={`${styles.cell} ${isSelected ? styles.cellSelected : ""}`}
                      style={{ background: cellColor(cell) }}
                      onClick={() => setSelected({ row: rowId, col: colId })}
                    >
                      {cell && cell.matches_played > 0 ? (
                        <>
                          <div className={styles.record}>
                            {cell.wins}-{cell.losses}
                          </div>
                          <div className={styles.winRate}>{(cell.win_rate! * 100).toFixed(0)}%</div>
                        </>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={`${styles.detail} card`}>
        {selected && selectedCell ? (
          <>
            <h3>
              {TEAM_CANONICAL[selected.row]} vs {TEAM_CANONICAL[selected.col]}
            </h3>
            {selectedCell.matches_played > 0 ? (
              <dl className={styles.detailList}>
                <dt>Head-to-head record</dt>
                <dd>
                  {selectedCell.wins}W - {selectedCell.losses}L ({selectedCell.matches_played} matches)
                </dd>
                <dt>Win rate, all matches</dt>
                <dd>{(selectedCell.win_rate! * 100).toFixed(1)}%</dd>
                <dt>Win rate, weighted toward recent matches</dt>
                <dd>{(selectedCell.decayed_win_rate! * 100).toFixed(1)}%</dd>
                <dt>Average match length</dt>
                <dd>{formatDuration(selectedCell.avg_duration_seconds)}</dd>
                <dt>Last time they played</dt>
                <dd>{selectedCell.last_meeting ? new Date(selectedCell.last_meeting).toLocaleDateString() : "-"}</dd>
              </dl>
            ) : (
              <p className="muted">These two teams haven&apos;t played each other with their current rosters in the matches we&apos;ve tracked.</p>
            )}
          </>
        ) : (
          <p className="muted">Click a cell to see the matchup detail. Numbers are from the row team&apos;s perspective; green means they&apos;re favored.</p>
        )}
      </div>
    </div>
  );
}
