"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import styles from "./PlayoffBracketClient.module.css";
import TeamLogo from "./TeamLogo";
import SliderPanel from "./SliderPanel";
import MatchupGrid from "./MatchupGrid";
import PlayoffBracketDiagram from "./PlayoffBracketDiagram";
import { TEAM_CANONICAL } from "@/data/teams";
import { playoffSimulation, playoffPredictedBracket, playoffSimulationMeta, PLAYOFF_TEAM_IDS } from "@/data/playoffSimulation";
import { useWeights } from "@/lib/WeightsContext";
import { computeComposite } from "@/lib/rating";
import { runPlayoffSimulation, predictBracket, type PredictedMatch } from "@/lib/simulatePlayoffs";

// The generated data/playoffSimulation.ts mirrors Python's snake_case JSON
// (win_prob); lib/simulatePlayoffs.ts's live predictBracket() returns the
// TS-native camelCase shape (winProb). Normalized once here so
// PlayoffBracketDiagram only ever has to deal with one shape.
const DEFAULT_PREDICTED_BRACKET: Record<string, PredictedMatch> = Object.fromEntries(
  Object.entries(playoffPredictedBracket).map(([mid, m]) => [mid, { a: m.a, b: m.b, winner: m.winner, loser: m.loser, winProb: m.win_prob }])
);

const LIVE_TRIALS = 20000;
const UB_R1_PAIRINGS = playoffSimulationMeta.ub_r1_pairings as [number, number][];

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
  const { weights, isDefault } = useWeights();
  const composite = useMemo(() => computeComposite(weights).filter((c) => PLAYOFF_TEAM_IDS.includes(c.teamId)), [weights]);

  const [liveResults, setLiveResults] = useState<Map<number, { reachPct: Record<string, number>; outcomePct: Record<string, number> }> | null>(null);
  const [livePredicted, setLivePredicted] = useState<Record<string, PredictedMatch> | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  useEffect(() => {
    if (isDefault) return;
    const startHandle = setTimeout(() => setIsSimulating(true), 0);
    const runHandle = setTimeout(() => {
      const ratings = composite.map((c) => ({ teamId: c.teamId, mean: c.ratingScaleMean, sigma: c.ratingScaleSigma }));
      const outcomes = runPlayoffSimulation(ratings, LIVE_TRIALS, 2026, UB_R1_PAIRINGS);
      const map = new Map(outcomes.map((r) => [r.teamId, { reachPct: r.reachPct, outcomePct: r.outcomePct }]));
      setLiveResults(map);
      setLivePredicted(predictBracket(ratings, UB_R1_PAIRINGS));
      setIsSimulating(false);
    }, 150);
    return () => {
      clearTimeout(startHandle);
      clearTimeout(runHandle);
    };
  }, [composite, isDefault]);

  const displayResults = isDefault ? null : liveResults;
  const displayPredicted = isDefault ? DEFAULT_PREDICTED_BRACKET : livePredicted ?? DEFAULT_PREDICTED_BRACKET;

  function getResult(tid: number) {
    if (displayResults) return displayResults.get(tid);
    const r = playoffSimulation[tid];
    return r ? { reachPct: r.reach_pct, outcomePct: r.outcome_pct } : undefined;
  }

  const orderedTeamIds = useMemo(
    () => [...PLAYOFF_TEAM_IDS].sort((a, b) => (getResult(b)?.reachPct.champion ?? 0) - (getResult(a)?.reachPct.champion ?? 0)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [displayResults]
  );

  return (
    <div>
      <div className={styles.sectionHeader}>
        <h3>Bracket diagram</h3>
        <span className={styles.sourceNote}>
          {isDefault
            ? "Predicted advancement, based on the standard prediction"
            : isSimulating
              ? "Recalculating with your settings..."
              : "Updated for your settings"}
        </span>
      </div>
      <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
        UB Quarterfinals are the real, announced seeding - everything to the right of that is our most likely
        prediction for who ends up in each slot, moving as you adjust the sliders.
      </p>
      <PlayoffBracketDiagram predicted={displayPredicted} />

      <div className={styles.mainLayout}>
        <div className={styles.tablesSection}>
          <div className={styles.sectionHeader}>
            <h3>Chance of reaching / winning each stage</h3>
            <span className={styles.sourceNote}>
              {isDefault
                ? `Based on ${playoffSimulationMeta.num_trials.toLocaleString()} simulated brackets`
                : isSimulating
                  ? "Recalculating with your settings..."
                  : `Updated for your settings (${LIVE_TRIALS.toLocaleString()}-trial quick estimate)`}
            </span>
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
            &ldquo;Reached&rdquo; means played in that match (win or lose); the win columns mean they won it.
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
                  const result = getResult(tid);
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
                          {result?.reachPct[key] != null ? `${result.reachPct[key].toFixed(1)}%` : "-"}
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
            Mutually exclusive - each team&apos;s row sums to ~100%. A team can only be eliminated in the lower
            bracket; losing an upper-bracket match just drops them down a round instead of knocking them out.
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
                  const result = getResult(tid);
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
                          {result?.outcomePct[key] != null ? `${result.outcomePct[key].toFixed(1)}%` : "-"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className={styles.sliderSection}>
          <SliderPanel />
        </div>
      </div>

      <h3 style={{ margin: "28px 0 4px" }}>Head-to-head, the 8 playoff teams</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        Every recorded meeting between these 8 teams (any tournament, roster-verified). Click a cell for the detail.
      </p>
      <MatchupGrid teamIds={PLAYOFF_TEAM_IDS} />
    </div>
  );
}
