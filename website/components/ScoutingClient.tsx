"use client";

import { useMemo, useState } from "react";
import styles from "./ScoutingClient.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { PLAYOFF_TEAM_IDS, playoffSimulationMeta } from "@/data/playoffSimulation";
import { playoffScoutingPairings, type ScoutingTeamProfile } from "@/data/playoffScouting";

const TOP_N = 6;

function pairKey(a: number, b: number): string {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  return `${lo}_${hi}`;
}

function pct(v: number | null | undefined): string {
  return v != null ? `${(v * 100).toFixed(1)}%` : "-";
}

function ProfileCard({ profile, opponentName }: { profile: ScoutingTeamProfile; opponentName: string }) {
  return (
    <div className={`${styles.profileCard} card`}>
      <div className={styles.profileHeader}>
        <TeamLogo teamId={profile.team_id} size="md" />
        <h3>{profile.team_name}</h3>
      </div>

      <dl className={styles.statList}>
        <dt>Comeback rate</dt>
        <dd className="mono">{pct(profile.comeback_rate)}</dd>
        <dt>Choke rate</dt>
        <dd className="mono">{pct(profile.choke_rate)}</dd>
        <dt>Win rate when favored after draft</dt>
        <dd className="mono">{pct(profile.draft_favored_win_rate)}</dd>
        <dt>Win rate as draft underdog</dt>
        <dd className="mono">{pct(profile.draft_underdog_win_rate)}</dd>
      </dl>

      <h4 className={styles.subHeading}>Top picks</h4>
      <ul className={styles.heroList}>
        {profile.top_picks.slice(0, TOP_N).map((h) => (
          <li key={h.hero_id}>
            <span>{h.hero_name}</span>
            <span className="mono muted">
              {pct(h.win_rate)} (n={h.raw_pick_count})
            </span>
          </li>
        ))}
      </ul>

      <h4 className={styles.subHeading}>Top bans made</h4>
      <ul className={styles.heroList}>
        {profile.top_bans_made.slice(0, TOP_N).map((h) => (
          <li key={h.hero_id}>
            <span>{h.hero_name}</span>
            <span className="mono muted">n={h.raw_count}</span>
          </li>
        ))}
      </ul>

      <h4 className={styles.subHeading}>Bans specifically vs {opponentName}</h4>
      {profile.bans_against_this_opponent.length > 0 ? (
        <ul className={styles.heroList}>
          {profile.bans_against_this_opponent.slice(0, TOP_N).map((h) => (
            <li key={h.hero_id}>
              <span>{h.hero_name}</span>
              <span className="mono muted">n={h.raw_count}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          No recorded bans specifically against this opponent yet.
        </p>
      )}
    </div>
  );
}

export default function ScoutingClient() {
  const [defaultA, defaultB] = playoffSimulationMeta.ub_r1_pairings[0];
  const [teamA, setTeamA] = useState<number>(defaultA);
  const [teamB, setTeamB] = useState<number>(defaultB);

  const pairing = useMemo(() => playoffScoutingPairings[pairKey(teamA, teamB)], [teamA, teamB]);

  const profileA = pairing ? (pairing.team_a === teamA ? pairing.team_a_profile : pairing.team_b_profile) : null;
  const profileB = pairing ? (pairing.team_b === teamB ? pairing.team_b_profile : pairing.team_a_profile) : null;
  const probA = pairing ? (pairing.team_a === teamA ? pairing.predicted_win_probability_a : pairing.predicted_win_probability_b) : null;

  return (
    <div>
      <div className={styles.pickerRow}>
        <select className={styles.select} value={teamA} onChange={(e) => setTeamA(Number(e.target.value))}>
          {PLAYOFF_TEAM_IDS.map((tid) => (
            <option key={tid} value={tid} disabled={tid === teamB}>
              {TEAM_CANONICAL[tid]}
            </option>
          ))}
        </select>
        <span className="muted">vs</span>
        <select className={styles.select} value={teamB} onChange={(e) => setTeamB(Number(e.target.value))}>
          {PLAYOFF_TEAM_IDS.map((tid) => (
            <option key={tid} value={tid} disabled={tid === teamA}>
              {TEAM_CANONICAL[tid]}
            </option>
          ))}
        </select>
      </div>

      {pairing && probA != null && (
        <div className={`${styles.probCard} card`}>
          <div className={styles.probBar}>
            <div className={styles.probBarFillA} style={{ width: `${probA * 100}%` }} />
          </div>
          <div className={styles.probLabels}>
            <span>
              {TEAM_CANONICAL[teamA]} <span className="mono">{pct(probA)}</span>
            </span>
            <span>
              <span className="mono">{pct(1 - probA)}</span> {TEAM_CANONICAL[teamB]}
            </span>
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            {pairing.h2h_summary.never_played || pairing.h2h_summary.matches_played < 3
              ? `Based on overall team strength (not enough head-to-head history: ${pairing.h2h_summary.matches_played} matches).`
              : `Based on their head-to-head record: ${pairing.h2h_summary.matches_played} matches played` +
                (pairing.h2h_summary.last_meeting ? `, last met ${new Date(pairing.h2h_summary.last_meeting).toLocaleDateString()}.` : ".")}
          </p>
        </div>
      )}

      {profileA && profileB && (
        <div className={styles.profileGrid}>
          <ProfileCard profile={profileA} opponentName={TEAM_CANONICAL[teamB]} />
          <ProfileCard profile={profileB} opponentName={TEAM_CANONICAL[teamA]} />
        </div>
      )}
    </div>
  );
}
