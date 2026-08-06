"use client";

import { useMemo, useState } from "react";
import styles from "./DraftsClient.module.css";
import { TEAM_CANONICAL } from "@/data/teams";
import { leagueDataMode, playerHistoryMode } from "@/data/pickBans";
import { teamPatchImpact } from "@/data/patchImpact";

type Tab = "league" | "players" | "patch";

const TEAM_IDS = Object.keys(TEAM_CANONICAL).map(Number);
const TOP_N = 12;

export default function DraftsClient() {
  const [teamId, setTeamId] = useState<number>(TEAM_IDS[0]);
  const [tab, setTab] = useState<Tab>("league");

  const league = leagueDataMode[String(teamId)];
  const playerHist = playerHistoryMode[String(teamId)];
  const patch = teamPatchImpact[String(teamId)];

  const topPicks = useMemo(() => {
    if (!league) return [];
    return Object.entries(league.picks)
      .sort((a, b) => b[1].weighted_pick_count - a[1].weighted_pick_count)
      .slice(0, TOP_N);
  }, [league]);

  const topBansMade = useMemo(() => {
    if (!league) return [];
    return Object.entries(league.bans_made)
      .sort((a, b) => b[1].weighted_count - a[1].weighted_count)
      .slice(0, TOP_N);
  }, [league]);

  const topBansAgainst = useMemo(() => {
    if (!league) return [];
    return Object.entries(league.bans_against)
      .sort((a, b) => b[1].weighted_count - a[1].weighted_count)
      .slice(0, TOP_N);
  }, [league]);

  return (
    <div>
      <div className={styles.topRow}>
        <select className={styles.select} value={teamId} onChange={(e) => setTeamId(Number(e.target.value))}>
          {TEAM_IDS.map((tid) => (
            <option key={tid} value={tid}>
              {TEAM_CANONICAL[tid]}
            </option>
          ))}
        </select>
        <div className={styles.tabs}>
          {(
            [
              ["league", "League data (Mode A)"],
              ["players", "Player history (Mode B)"],
              ["patch", "Patch 7.41e impact"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button key={key} className={tab === key ? styles.tabActive : styles.tab} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === "league" && league && (
        <div className={styles.grid3}>
          <div className="card">
            <h3>Top picks</h3>
            <table className={`${styles.miniTable} dataTable`}>
              <thead>
                <tr>
                  <th>Hero</th>
                  <th>Win rate</th>
                  <th>Games</th>
                </tr>
              </thead>
              <tbody>
                {topPicks.map(([heroId, v]) => (
                  <tr key={heroId}>
                    <td>{v.hero_name}</td>
                    <td className="mono">{v.win_rate != null ? `${(v.win_rate * 100).toFixed(0)}%` : "-"}</td>
                    <td className="mono muted">{v.raw_pick_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>Bans they make</h3>
            <table className={`${styles.miniTable} dataTable`}>
              <thead>
                <tr>
                  <th>Hero</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {topBansMade.map(([heroId, v]) => (
                  <tr key={heroId}>
                    <td>{v.hero_name}</td>
                    <td className="mono muted">{v.raw_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>Banned against them</h3>
            <table className={`${styles.miniTable} dataTable`}>
              <thead>
                <tr>
                  <th>Hero</th>
                  <th>Count</th>
                  <th>Top opponent</th>
                </tr>
              </thead>
              <tbody>
                {topBansAgainst.map(([heroId, v]) => {
                  const topOpp = Object.entries(v.by_opponent).sort((a, b) => b[1].raw_count - a[1].raw_count)[0];
                  return (
                    <tr key={heroId}>
                      <td>{v.hero_name}</td>
                      <td className="mono muted">{v.raw_count}</td>
                      <td className="muted">{topOpp ? `${topOpp[1].team_name} (${topOpp[1].raw_count})` : "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "players" && playerHist && (
        <div className={styles.grid2}>
          {Object.entries(playerHist.players).map(([name, p]) => (
            <div className="card" key={name}>
              <h3>{name}</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Most recently played (independent of team drafts)
              </p>
              <ul className={styles.heroList}>
                {p.top5_recent?.map((h) => (
                  <li key={h.hero_id}>
                    <span>{h.hero}</span>
                    <span className="mono muted">
                      {h.games} games, {((h.win / h.games) * 100).toFixed(0)}% wr
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {tab === "patch" && patch && (
        <div className="card">
          <h3>
            {TEAM_CANONICAL[teamId]} - patch impact score:{" "}
            <span className="mono">{patch.patch_impact_score != null ? patch.patch_impact_score.toFixed(4) : "n/a"}</span>
          </h3>
          <p className="muted" style={{ fontSize: 12, margin: "8px 0 16px" }}>
            Weighted by how central each hero is to the team&apos;s pick pool (top {patch.pool_heroes.length} heroes).
            Positive = pool trending toward higher win rates post-7.41e.
          </p>
          <table className={`${styles.miniTable} dataTable`}>
            <thead>
              <tr>
                <th>Hero</th>
                <th>Pool share</th>
                <th>Winrate delta</th>
                <th>Contribution</th>
                <th>Patch note (context only)</th>
              </tr>
            </thead>
            <tbody>
              {patch.pool_heroes.map((h) => (
                <tr key={h.hero_id}>
                  <td>{h.hero_name}</td>
                  <td className="mono muted">{(h.pick_weight_share * 100).toFixed(1)}%</td>
                  <td className="mono">{h.winrate_delta != null ? `${(h.winrate_delta * 100).toFixed(2)}pp` : "-"}</td>
                  <td className="mono muted">{h.contribution != null ? h.contribution.toFixed(4) : "-"}</td>
                  <td className="muted" style={{ whiteSpace: "normal", maxWidth: 320 }}>
                    {h.patch_notes_context ? `${h.patch_notes_context.direction}: ${h.patch_notes_context.summary}` : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
