"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import styles from "./PlayoffPredictClient.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { PLAYOFF_TEAM_IDS, playoffSimulationMeta } from "@/data/playoffSimulation";
import { useWeights } from "@/lib/WeightsContext";
import { computeComposite } from "@/lib/rating";
import { simulatePairwise } from "@/lib/simulate";

const UB_R1_PAIRINGS = playoffSimulationMeta.ub_r1_pairings as [number, number][];
const CUSTOM_MATCHES_KEY = "ti2026-playoff-custom-matches-v1";

interface CustomMatch {
  teamA: number;
  teamB: number;
}

function loadCustomMatches(): CustomMatch[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(CUSTOM_MATCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function PlayoffPredictClient() {
  const { weights } = useWeights();
  const composite = useMemo(() => computeComposite(weights).filter((c) => PLAYOFF_TEAM_IDS.includes(c.teamId)), [weights]);
  const ratingByTeam = useMemo(() => {
    const map = new Map<number, { teamId: number; mean: number; sigma: number }>();
    for (const c of composite) map.set(c.teamId, { teamId: c.teamId, mean: c.ratingScaleMean, sigma: c.ratingScaleSigma });
    return map;
  }, [composite]);

  const [customMatches, setCustomMatches] = useState<CustomMatch[]>([]);
  const [newTeamA, setNewTeamA] = useState(PLAYOFF_TEAM_IDS[0]);
  const [newTeamB, setNewTeamB] = useState(PLAYOFF_TEAM_IDS[1]);

  useEffect(() => {
    const handle = setTimeout(() => setCustomMatches(loadCustomMatches()), 0);
    return () => clearTimeout(handle);
  }, []);

  function persist(matches: CustomMatch[]) {
    setCustomMatches(matches);
    window.localStorage.setItem(CUSTOM_MATCHES_KEY, JSON.stringify(matches));
  }

  function addMatch() {
    if (newTeamA === newTeamB) return;
    const exists = customMatches.some(
      (m) => (m.teamA === newTeamA && m.teamB === newTeamB) || (m.teamA === newTeamB && m.teamB === newTeamA)
    );
    if (exists) return;
    persist([...customMatches, { teamA: newTeamA, teamB: newTeamB }]);
  }

  function removeMatch(idx: number) {
    persist(customMatches.filter((_, i) => i !== idx));
  }

  function winChance(teamA: number, teamB: number): number | null {
    const a = ratingByTeam.get(teamA);
    const b = ratingByTeam.get(teamB);
    if (!a || !b) return null;
    return simulatePairwise(a, b) * 100;
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>Upper Bracket Round 1 (announced)</h2>
        <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
          Single-game win chance for each announced UB R1 matchup - not the same as the series-level odds on the
          bracket page, which account for best-of-3 format and everything downstream.
        </p>
        <div className={styles.matchList}>
          {UB_R1_PAIRINGS.map(([a, b], idx) => (
            <MatchRow key={idx} teamA={a} teamB={b} winChanceA={winChance(a, b)} />
          ))}
        </div>
      </div>

      <div className="card">
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>Predict any matchup</h2>
        <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
          Pick any two of the 8 playoff teams to see who&apos;s favored in a single game - useful for hypothetical
          later-round matchups the bracket hasn&apos;t produced yet. Saved on this device only.
        </p>
        <div className={styles.addRow}>
          <select value={newTeamA} onChange={(e) => setNewTeamA(Number(e.target.value))} className={styles.select}>
            {PLAYOFF_TEAM_IDS.map((tid) => (
              <option key={tid} value={tid}>
                {TEAM_CANONICAL[tid]}
              </option>
            ))}
          </select>
          <span className="muted">vs</span>
          <select value={newTeamB} onChange={(e) => setNewTeamB(Number(e.target.value))} className={styles.select}>
            {PLAYOFF_TEAM_IDS.map((tid) => (
              <option key={tid} value={tid}>
                {TEAM_CANONICAL[tid]}
              </option>
            ))}
          </select>
          <button className={styles.addBtn} onClick={addMatch} disabled={newTeamA === newTeamB}>
            Add match
          </button>
        </div>

        {customMatches.length > 0 ? (
          <div className={styles.matchList} style={{ marginTop: 16 }}>
            {customMatches.map((m, idx) => (
              <MatchRow key={idx} teamA={m.teamA} teamB={m.teamB} winChanceA={winChance(m.teamA, m.teamB)} onRemove={() => removeMatch(idx)} />
            ))}
          </div>
        ) : (
          <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
            No matches added yet.
          </p>
        )}
      </div>
    </div>
  );
}

function MatchRow({
  teamA,
  teamB,
  winChanceA,
  onRemove,
}: {
  teamA: number;
  teamB: number;
  winChanceA: number | null;
  onRemove?: () => void;
}) {
  const pctA = winChanceA ?? 50;
  const pctB = 100 - pctA;
  const favored = pctA >= pctB ? teamA : teamB;

  return (
    <div className={styles.matchRow}>
      <div className={styles.teamSide}>
        <Link href={`/teams/${teamA}`} className={`${styles.teamLink} ${favored === teamA ? styles.favored : ""}`}>
          <TeamLogo teamId={teamA} size="md" />
          {TEAM_CANONICAL[teamA]}
        </Link>
        <span className="mono muted">{pctA.toFixed(0)}%</span>
      </div>
      <div className={styles.bar}>
        <div className={styles.barFillA} style={{ width: `${pctA}%` }} />
      </div>
      <div className={styles.teamSide}>
        <span className="mono muted">{pctB.toFixed(0)}%</span>
        <Link href={`/teams/${teamB}`} className={`${styles.teamLink} ${favored === teamB ? styles.favored : ""}`}>
          <TeamLogo teamId={teamB} size="md" />
          {TEAM_CANONICAL[teamB]}
        </Link>
      </div>
      {onRemove && (
        <button className={styles.removeBtn} onClick={onRemove} aria-label="Remove match">
          &times;
        </button>
      )}
    </div>
  );
}
