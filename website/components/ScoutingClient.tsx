"use client";

import { useMemo, useState } from "react";
import styles from "./ScoutingClient.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { PLAYOFF_TEAM_IDS, playoffSimulationMeta } from "@/data/playoffSimulation";
import {
  playoffScoutingPairings,
  type ScoutingTeamProfile,
  type ScoutingHeroPick,
  type ScoutingHeroBan,
  type ScoutingHeroBanAgainst,
  type ScoutingBanTarget,
  type ScoutingPlayerPretournament,
  type ScoutingPlayerGroupStage,
} from "@/data/playoffScouting";

const TOP_N = 6;
const ERA_TABS = [
  ["pretournament", "Pre-International"],
  ["group_stage", "Group Stage"],
] as const;
type EraKey = (typeof ERA_TABS)[number][0];

function pairKey(a: number, b: number): string {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  return `${lo}_${hi}`;
}

function pct(v: number | null | undefined, digits = 1): string {
  return v != null ? `${(v * 100).toFixed(digits)}%` : "-";
}

interface EraStats {
  games: number;
  top_picks: ScoutingHeroPick[];
  top_bans_made: ScoutingHeroBan[];
  bans_against_this_opponent: ScoutingHeroBanAgainst[];
  comeback_rate: number | null;
  choke_rate: number | null;
  draft_favored_win_rate: number | null;
  draft_underdog_win_rate: number | null;
}

function EraStatsSection({ era, opponentName }: { era: EraStats; opponentName: string }) {
  return (
    <>
      <dl className={styles.statList}>
        <dt>Games in this dataset</dt>
        <dd className="mono">{era.games}</dd>
        <dt>Comeback rate</dt>
        <dd className="mono">{pct(era.comeback_rate)}</dd>
        <dt>Choke rate</dt>
        <dd className="mono">{pct(era.choke_rate)}</dd>
        <dt>Win rate when favored after draft</dt>
        <dd className="mono">{pct(era.draft_favored_win_rate)}</dd>
        <dt>Win rate as draft underdog</dt>
        <dd className="mono">{pct(era.draft_underdog_win_rate)}</dd>
      </dl>

      <h4 className={styles.subHeading}>Top picks</h4>
      <ul className={styles.heroList}>
        {era.top_picks.slice(0, TOP_N).map((h) => (
          <li key={h.hero_id}>
            <span>{h.hero_name}</span>
            <span className="mono muted">
              n={h.pick_count} ({pct(h.pick_rate, 0)}) - {pct(h.win_rate, 0)} wr
            </span>
          </li>
        ))}
        {era.top_picks.length === 0 && <li className="muted">No data.</li>}
      </ul>

      <h4 className={styles.subHeading}>Top bans made</h4>
      <ul className={styles.heroList}>
        {era.top_bans_made.slice(0, TOP_N).map((h) => (
          <li key={h.hero_id}>
            <span>{h.hero_name}</span>
            <span className="mono muted">
              n={h.count} ({pct(h.rate, 0)})
            </span>
          </li>
        ))}
        {era.top_bans_made.length === 0 && <li className="muted">No data.</li>}
      </ul>

      <h4 className={styles.subHeading}>Bans specifically vs {opponentName}</h4>
      {era.bans_against_this_opponent.length > 0 ? (
        <ul className={styles.heroList}>
          {era.bans_against_this_opponent.slice(0, TOP_N).map((h) => (
            <li key={h.hero_id}>
              <span>{h.hero_name}</span>
              <span className="mono muted">n={h.count}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          No recorded bans specifically against this opponent yet.
        </p>
      )}
    </>
  );
}

function PretournamentPlayerPicks({ players }: { players: ScoutingPlayerPretournament[] }) {
  return (
    <div className={styles.playerGrid}>
      {players.map((p) => (
        <div key={p.player_name} className={styles.playerCard}>
          <div className={styles.playerName}>{p.player_name}</div>
          <ul className={styles.playerHeroList}>
            {p.top_picks.slice(0, 4).map((h) => (
              <li key={h.hero_id}>
                <span>{h.hero_name}</span>
                <span className="mono muted">
                  {h.games}g ({pct(h.win_rate, 0)} wr)
                </span>
              </li>
            ))}
            {p.top_picks.length === 0 && <li className="muted">No data.</li>}
          </ul>
        </div>
      ))}
      {players.length === 0 && <p className="muted" style={{ fontSize: 13 }}>No player data.</p>}
    </div>
  );
}

function GroupStagePlayerPicks({ players }: { players: ScoutingPlayerGroupStage[] }) {
  return (
    <div className={styles.playerGrid}>
      {players.map((p) => (
        <div key={p.player_name} className={styles.playerCard}>
          <div className={styles.playerName}>
            {p.player_name} <span className="muted">({p.games_played}g)</span>
          </div>
          <ul className={styles.playerHeroList}>
            {p.top_picks.slice(0, 4).map((h) => (
              <li key={h.hero_id}>
                <span>{h.hero_name}</span>
                <span className="mono muted">
                  {pct(h.pick_rate, 0)} ({pct(h.win_rate, 0)} wr)
                </span>
              </li>
            ))}
            {p.top_picks.length === 0 && <li className="muted">No data.</li>}
          </ul>
        </div>
      ))}
      {players.length === 0 && <p className="muted" style={{ fontSize: 13 }}>No player data.</p>}
    </div>
  );
}

function ProbableBanTargets({ targets, opponentName }: { targets: ScoutingBanTarget[]; opponentName: string }) {
  return (
    <div className={styles.banTargetsBox}>
      <h4 className={styles.subHeading}>Probable bans, based on {opponentName}&apos;s Group Stage picks</h4>
      <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
        Not the same as the actual-history bans above - these two teams may not have even played each other. This is
        just {opponentName}&apos;s own most-picked, best-performing Group Stage heroes, ranked by pick rate × win
        rate, as an informative extra angle on what might be worth banning.
      </p>
      {targets.length > 0 ? (
        <ul className={styles.heroList}>
          {targets.map((h) => (
            <li key={h.hero_id}>
              <span>{h.hero_name}</span>
              <span className="mono muted">
                n={h.pick_count} ({pct(h.pick_rate, 0)}) - {pct(h.win_rate, 0)} wr
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          Not enough Group Stage picks from {opponentName} yet to call out a threat.
        </p>
      )}
    </div>
  );
}

function ProfileCard({ profile, opponentName }: { profile: ScoutingTeamProfile; opponentName: string }) {
  const [era, setEra] = useState<EraKey>("group_stage");
  const current = profile[era];

  return (
    <div className={`${styles.profileCard} card`}>
      <div className={styles.profileHeader}>
        <TeamLogo teamId={profile.team_id} size="md" />
        <h3>{profile.team_name}</h3>
      </div>

      <div className={styles.eraTabs}>
        {ERA_TABS.map(([key, label]) => (
          <button key={key} className={era === key ? styles.eraTabActive : styles.eraTab} onClick={() => setEra(key)}>
            {label}
          </button>
        ))}
      </div>

      <EraStatsSection era={current} opponentName={opponentName} />

      {era === "group_stage" && profile.group_stage.probable_ban_targets && (
        <ProbableBanTargets targets={profile.group_stage.probable_ban_targets} opponentName={opponentName} />
      )}

      <h4 className={styles.subHeading}>Players' most-picked heroes</h4>
      {era === "pretournament" ? (
        <PretournamentPlayerPicks players={profile.pretournament.player_picks} />
      ) : (
        <GroupStagePlayerPicks players={profile.group_stage.player_picks} />
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
