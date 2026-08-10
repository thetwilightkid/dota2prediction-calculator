"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import SliderPanel from "./SliderPanel";
import styles from "./OverviewClient.module.css";
import { useWeights } from "@/lib/WeightsContext";
import { computeComposite } from "@/lib/rating";
import { runSwissSimulation } from "@/lib/simulate";
import { precomputedSimulation } from "@/data/simulation";

const LIVE_TRIALS = 4000;
const OUTCOME_ORDER = ["4-0", "4-1", "3-2", "2-3", "1-4", "0-4"];
const DAY1_PAIRINGS = precomputedSimulation.meta.day1_pairings as [number, number][];

function advanceChance(outcomePct: Record<string, number>): number {
  return (outcomePct["4-0"] ?? 0) + (outcomePct["4-1"] ?? 0) + (outcomePct["3-2"] ?? 0);
}

export default function OverviewClient() {
  const { weights, isDefault } = useWeights();
  const composite = useMemo(() => computeComposite(weights), [weights]);

  const [liveOutcomes, setLiveOutcomes] = useState<Map<number, Record<string, number>> | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  useEffect(() => {
    if (isDefault) return;
    // setState calls deferred into callbacks (not called directly in the effect
    // body) per react-hooks/set-state-in-effect.
    const startHandle = setTimeout(() => setIsSimulating(true), 0);
    const runHandle = setTimeout(() => {
      const ratings = composite.map((c) => ({ teamId: c.teamId, mean: c.ratingScaleMean, sigma: c.ratingScaleSigma }));
      const results = runSwissSimulation(ratings, LIVE_TRIALS, 42, DAY1_PAIRINGS);
      const map = new Map(results.map((r) => [r.teamId, r.outcomePct]));
      setLiveOutcomes(map);
      setIsSimulating(false);
    }, 150);
    return () => {
      clearTimeout(startHandle);
      clearTimeout(runHandle);
    };
  }, [composite, isDefault]);

  // Falls back to null (precomputed data) when back at default weights, rather
  // than clearing liveOutcomes state from inside the effect above.
  const displayOutcomes = isDefault ? null : liveOutcomes;

  const rows = useMemo(() => {
    return [...composite]
      .sort((a, b) => b.compositeMean - a.compositeMean)
      .map((c, idx) => {
        const outcomePct = displayOutcomes?.get(c.teamId) ?? precomputedSimulation.teams[String(c.teamId)]?.outcome_pct;
        return { rank: idx + 1, ...c, outcomePct };
      });
  }, [composite, displayOutcomes]);

  return (
    <div className={styles.layout}>
      <div className={styles.tableSection}>
        <div className={styles.tableHeader}>
          <h1>Team rankings</h1>
          <span className={styles.sourceNote}>
            {isDefault
              ? "Our standard prediction, based on 1,000,000 simulated tournaments"
              : isSimulating
                ? "Recalculating with your settings..."
                : "Updated for your settings (quick estimate)"}
          </span>
        </div>
        <p className={styles.legend}>
          Records show wins-losses. 4-0 through 3-2 advance to the next stage; 2-3 through 0-4 are eliminated.
        </p>
        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>#</th>
                <th>Team</th>
                <th title="A single combined strength score - higher is better">Power score</th>
                <th title="Based on an independent rating service that tracks pro matches">Track record</th>
                <th title="How well they've played recently">Recent form</th>
                <th title="What other prediction sites think of them">Experts</th>
                <th title="Chance of finishing 3-2 or better">Chance to advance</th>
                {OUTCOME_ORDER.map((o) => (
                  <th key={o}>{o}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.teamId}>
                  <td className="muted">{r.rank}</td>
                  <td>
                    <Link href={`/teams/${r.teamId}`}>{r.teamName}</Link>
                  </td>
                  <td className="mono">
                    {r.ratingScaleMean.toFixed(0)} <span className="muted">± {r.ratingScaleSigma.toFixed(0)}</span>
                  </td>
                  <td className="mono muted">{r.zElo.toFixed(2)}</td>
                  <td className="mono muted">{r.zForm.toFixed(2)}</td>
                  <td className="mono muted">{r.zMarket.toFixed(2)}</td>
                  <td className="mono">{r.outcomePct ? `${advanceChance(r.outcomePct).toFixed(1)}%` : "-"}</td>
                  {OUTCOME_ORDER.map((o) => (
                    <td key={o} className="mono muted">
                      {r.outcomePct?.[o] != null ? `${r.outcomePct[o].toFixed(1)}%` : "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className={styles.sliderSection}>
        <SliderPanel />
      </div>
    </div>
  );
}
