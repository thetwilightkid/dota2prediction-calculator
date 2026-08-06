"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import styles from "./SimulationClient.module.css";
import { TEAM_CANONICAL } from "@/data/teams";
import { precomputedSimulations } from "@/data/simulation";
import { DEFAULT_WEIGHTS, computeComposite } from "@/lib/rating";
import { runSwissSimulation } from "@/lib/simulate";

const OUTCOME_ORDER = ["4-0", "4-1", "3-2", "2-3", "1-4", "0-4"];
const PRECOMPUTED_CHOICES = [10000, 100000] as const;

export default function SimulationClient() {
  const [trialChoice, setTrialChoice] = useState<10000 | 100000>(10000);
  const [liveTrials, setLiveTrials] = useState(10000);
  const [liveResult, setLiveResult] = useState<{ trials: number; teams: Record<string, Record<string, number>> } | null>(
    null
  );
  const [running, setRunning] = useState(false);

  const precomputed = precomputedSimulations[trialChoice];

  function runLive() {
    setRunning(true);
    // Deferred so the "Simulating..." state paints before the (synchronous) run.
    setTimeout(() => {
      const composite = computeComposite(DEFAULT_WEIGHTS);
      const ratings = composite.map((c) => ({ teamId: c.teamId, mean: c.ratingScaleMean, sigma: c.ratingScaleSigma }));
      const results = runSwissSimulation(ratings, liveTrials, Date.now() & 0xffffffff);
      const teams: Record<string, Record<string, number>> = {};
      for (const r of results) teams[String(r.teamId)] = r.outcomePct;
      setLiveResult({ trials: liveTrials, teams });
      setRunning(false);
    }, 20);
  }

  function getOutcomePct(tid: number): Record<string, number> | undefined {
    return liveResult ? liveResult.teams[String(tid)] : precomputed.teams[String(tid)]?.outcome_pct;
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
  }, [liveResult, precomputed]);

  return (
    <div>
      <div className={`${styles.controls} card`}>
        <div className={styles.controlGroup}>
          <span className="muted">Precomputed run:</span>
          {PRECOMPUTED_CHOICES.map((n) => (
            <button
              key={n}
              className={trialChoice === n && !liveResult ? styles.toggleActive : styles.toggle}
              onClick={() => {
                setTrialChoice(n);
                setLiveResult(null);
              }}
            >
              {n.toLocaleString()} trials
            </button>
          ))}
        </div>
        <div className={styles.controlGroup}>
          <span className="muted">Live re-run (default weights):</span>
          <select
            value={liveTrials}
            onChange={(e) => setLiveTrials(Number(e.target.value))}
            className={styles.select}
          >
            <option value={1000}>1,000</option>
            <option value={10000}>10,000</option>
            <option value={100000}>100,000</option>
          </select>
          <button className={styles.runBtn} onClick={runLive} disabled={running}>
            {running ? "Simulating..." : "Run"}
          </button>
          {liveResult && (
            <button className={styles.toggle} onClick={() => setLiveResult(null)}>
              Clear
            </button>
          )}
        </div>
      </div>

      <p className="muted" style={{ margin: "12px 0" }}>
        {liveResult
          ? `Showing a fresh ${liveResult.trials.toLocaleString()}-trial run computed in your browser just now.`
          : `Showing the precomputed ${trialChoice.toLocaleString()}-trial run from group_stage_simulation_results${trialChoice === 100000 ? "_100000" : ""}.json.`}
      </p>

      <div className="tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Team</th>
              <th>Advance %</th>
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
