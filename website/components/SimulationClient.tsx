"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import styles from "./SimulationClient.module.css";
import { TEAM_CANONICAL } from "@/data/teams";
import { precomputedSimulation } from "@/data/simulation";
import { useWeights } from "@/lib/WeightsContext";
import { computeComposite } from "@/lib/rating";
import { runSwissSimulation } from "@/lib/simulate";

const OUTCOME_ORDER = ["4-0", "4-1", "3-2", "2-3", "1-4", "0-4"];
const DAY1_PAIRINGS = precomputedSimulation.meta.day1_pairings as [number, number][];

export default function SimulationClient() {
  const { weights } = useWeights();
  const [liveTrials, setLiveTrials] = useState(10000);
  const [liveResult, setLiveResult] = useState<{ trials: number; teams: Record<string, Record<string, number>> } | null>(
    null
  );
  const [running, setRunning] = useState(false);

  function runLive() {
    setRunning(true);
    // Deferred so the "Simulating..." state paints before the (synchronous) run.
    setTimeout(() => {
      const composite = computeComposite(weights);
      const ratings = composite.map((c) => ({ teamId: c.teamId, mean: c.ratingScaleMean, sigma: c.ratingScaleSigma }));
      const results = runSwissSimulation(ratings, liveTrials, Date.now() & 0xffffffff, DAY1_PAIRINGS);
      const teams: Record<string, Record<string, number>> = {};
      for (const r of results) teams[String(r.teamId)] = r.outcomePct;
      setLiveResult({ trials: liveTrials, teams });
      setRunning(false);
    }, 20);
  }

  function getOutcomePct(tid: number): Record<string, number> | undefined {
    return liveResult ? liveResult.teams[String(tid)] : precomputedSimulation.teams[String(tid)]?.outcome_pct;
  }

  function advanceChance(outcomePct: Record<string, number> | undefined): number {
    if (!outcomePct) return 0;
    return (outcomePct["4-0"] ?? 0) + (outcomePct["4-1"] ?? 0) + (outcomePct["3-2"] ?? 0);
  }

  const orderedTeamIds = useMemo(() => {
    return Object.keys(TEAM_CANONICAL)
      .map(Number)
      .sort((a, b) => advanceChance(getOutcomePct(b)) - advanceChance(getOutcomePct(a)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveResult]);

  return (
    <div>
      <div className={`${styles.controls} card`}>
        <div className={styles.controlGroup}>
          <span className="muted">Run your own simulation, using your current slider settings:</span>
          <select value={liveTrials} onChange={(e) => setLiveTrials(Number(e.target.value))} className={styles.select}>
            <option value={1000}>1,000 tournaments (fastest)</option>
            <option value={10000}>10,000 tournaments</option>
            <option value={1000000}>1,000,000 tournaments (slow, most precise)</option>
          </select>
          <button className={styles.runBtn} onClick={runLive} disabled={running}>
            {running ? "Simulating..." : "Run"}
          </button>
          {liveResult && (
            <button className={styles.toggle} onClick={() => setLiveResult(null)}>
              Back to standard prediction
            </button>
          )}
        </div>
      </div>

      <p className="muted" style={{ margin: "12px 0" }}>
        {liveResult
          ? `Showing your own simulation: ${liveResult.trials.toLocaleString()} simulated tournaments, computed just now.`
          : "Showing our standard prediction: 1,000,000 simulated tournaments."}
      </p>

      <div className="tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Team</th>
              <th>Chance to advance</th>
              {OUTCOME_ORDER.map((o) => (
                <th key={o}>{o}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orderedTeamIds.map((tid) => {
              const outcomePct = getOutcomePct(tid);
              const advance = advanceChance(outcomePct);
              return (
                <tr key={tid}>
                  <td>
                    <Link href={`/teams/${tid}`}>{TEAM_CANONICAL[tid]}</Link>
                  </td>
                  <td className="mono">{advance.toFixed(1)}%</td>
                  {OUTCOME_ORDER.map((o) => (
                    <td key={o} className="mono muted">
                      {outcomePct?.[o] != null ? `${outcomePct[o].toFixed(1)}%` : "-"}
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
