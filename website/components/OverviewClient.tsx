"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import SliderPanel from "./SliderPanel";
import GroupsCard from "./GroupsCard";
import TeamLogo from "./TeamLogo";
import styles from "./OverviewClient.module.css";
import { useWeights } from "@/lib/WeightsContext";
import { computeComposite } from "@/lib/rating";
import { advanceChance, OUTCOME_ORDER, outcomeLabel, runSwissSimulation } from "@/lib/simulate";
import { precomputedSimulation } from "@/data/simulation";

const LIVE_TRIALS = 4000;
const DAY1_PAIRINGS = precomputedSimulation.meta.day1_pairings as [number, number][];
const TEAM_POD = precomputedSimulation.meta.team_pod;

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
      const results = runSwissSimulation(ratings, LIVE_TRIALS, 42, DAY1_PAIRINGS, TEAM_POD);
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

  // Keeps the groups card in step with whatever the rankings table is showing
  // (precomputed by default, live re-simulation/re-rating once a slider moves).
  const advanceByTeam = useMemo(() => {
    const map = new Map<number, number>();
    for (const r of rows) map.set(r.teamId, advanceChance(r.outcomePct));
    return map;
  }, [rows]);
  const powerByTeam = useMemo(() => {
    const map = new Map<number, number>();
    for (const c of composite) map.set(c.teamId, c.ratingScaleMean);
    return map;
  }, [composite]);

  return (
    <>
      <GroupsCard advanceByTeam={advanceByTeam} powerByTeam={powerByTeam} />
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
            Records show wins-losses. 4 wins gets a team through, 4 losses knocks them out. Anyone still undecided
            after 5 rounds plays a final do-or-die match, which is why 3-3 appears twice: once for teams who won that
            match and got through <strong>(in)</strong>, once for teams who lost it and went home <strong>(out)</strong>.
          </p>
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th title="Which half of the draw they play in">Group</th>
                  <th title="A single combined strength score - higher is better">Power score</th>
                  <th title="Their datdota Glicko-2 rating, based on pro matches worldwide">Datdota</th>
                  <th title="How they were doing before TI2026 started">Pre-Int form</th>
                  <th title="How they've done in TI2026's real Group Stage">GS form</th>
                  <th title="Liquipedia / EPT / ESL pre-tournament ranking consensus">Experts</th>
                  <th title="Chance of making it out of the group stage">Chance to advance</th>
                  {OUTCOME_ORDER.map((o) => (
                    <th key={o}>{outcomeLabel(o)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.teamId}>
                    <td className="muted">{r.rank}</td>
                    <td>
                      <Link href={`/teams/${r.teamId}`} className={styles.teamCell}>
                        <TeamLogo teamId={r.teamId} />
                        {r.teamName}
                      </Link>
                    </td>
                    <td className="muted">{TEAM_POD[String(r.teamId)] ?? "-"}</td>
                    <td className="mono">
                      {r.ratingScaleMean.toFixed(0)} <span className="muted">± {r.ratingScaleSigma.toFixed(0)}</span>
                    </td>
                    <td className="mono muted">{r.zElo.toFixed(2)}</td>
                    <td className="mono muted">{r.zFormPretournament.toFixed(2)}</td>
                    <td className="mono muted">{r.zFormGroupStage.toFixed(2)}</td>
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
    </>
  );
}
