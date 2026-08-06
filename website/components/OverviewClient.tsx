"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import SliderPanel from "./SliderPanel";
import styles from "./OverviewClient.module.css";
import { DEFAULT_WEIGHTS, computeComposite, type RatingWeights } from "@/lib/rating";
import { runSwissSimulation } from "@/lib/simulate";
import { precomputedSimulations } from "@/data/simulation";

const LIVE_TRIALS = 4000;
const OUTCOME_ORDER = ["4-0", "4-1", "3-2", "2-3", "1-4", "0-4"];

function advanceChance(outcomePct: Record<string, number>): number {
  return (outcomePct["4-0"] ?? 0) + (outcomePct["4-1"] ?? 0) + (outcomePct["3-2"] ?? 0);
}

export default function OverviewClient() {
  const [weights, setWeights] = useState<RatingWeights>(DEFAULT_WEIGHTS);
  const isDefault = useMemo(
    () => (Object.keys(weights) as (keyof RatingWeights)[]).every((k) => weights[k] === DEFAULT_WEIGHTS[k]),
    [weights]
  );

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
      const results = runSwissSimulation(ratings, LIVE_TRIALS);
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

  const precomputed10k = precomputedSimulations[10000];

  const rows = useMemo(() => {
    return [...composite]
      .sort((a, b) => b.compositeMean - a.compositeMean)
      .map((c, idx) => {
        const outcomePct = displayOutcomes?.get(c.teamId) ?? precomputed10k.teams[String(c.teamId)]?.outcome_pct;
        return { rank: idx + 1, ...c, outcomePct };
      });
  }, [composite, displayOutcomes, precomputed10k]);

  return (
    <div className={styles.layout}>
      <div className={styles.tableSection}>
        <div className={styles.tableHeader}>
          <h1>Group stage ranking</h1>
          <span className={styles.sourceNote}>
            {isDefault
              ? "Showing default composite rating + precomputed 10,000-trial simulation"
              : isSimulating
                ? `Recomputing (${LIVE_TRIALS.toLocaleString()} live trials)...`
                : `Live: reweighted composite + ${LIVE_TRIALS.toLocaleString()}-trial re-simulation`}
          </span>
        </div>
        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>#</th>
                <th>Team</th>
                <th>Rating</th>
                <th title="Elo/Glicko z-score component">Elo</th>
                <th title="Own decayed win-rate z-score component">Form</th>
                <th title="EPT/ESL/Liquipedia market z-score component">Market</th>
                <th>Advance %</th>
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
        <SliderPanel weights={weights} onChange={setWeights} />
      </div>
    </div>
  );
}
