"use client";

import { useMemo, useState } from "react";
import styles from "./GroupStageClient.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { groupStagePickBans } from "@/data/groupStagePickBans";
import { groupStageStability } from "@/data/groupStageStability";
import { groupStagePlayerStats, type GSPlayerStats } from "@/data/groupStagePlayerStats";

type Tab = "draft" | "stability" | "players";
type SortKey = "kda" | "avg_gold_per_min" | "avg_xp_per_min" | "avg_rune_pickups" | "avg_kills" | "games_played";

const TEAM_IDS = Object.keys(TEAM_CANONICAL).map(Number);
const TOP_N = 10;

const SORT_OPTIONS: [SortKey, string][] = [
  ["kda", "KDA"],
  ["avg_kills", "Avg kills"],
  ["avg_gold_per_min", "Avg GPM"],
  ["avg_xp_per_min", "Avg XPM"],
  ["avg_rune_pickups", "Avg rune pickups"],
  ["games_played", "Games played"],
];

function pct(v: number | null | undefined): string {
  return v != null ? `${(v * 100).toFixed(0)}%` : "-";
}

export default function GroupStageClient() {
  const [tab, setTab] = useState<Tab>("draft");
  const [teamId, setTeamId] = useState<number>(TEAM_IDS[0]);
  const [teamFilter, setTeamFilter] = useState<number | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("kda");

  const drafts = groupStagePickBans[String(teamId)];

  const topPicks = useMemo(() => (drafts ? Object.entries(drafts.picks).sort((a, b) => b[1].pick_count - a[1].pick_count).slice(0, TOP_N) : []), [drafts]);
  const topBansMade = useMemo(() => (drafts ? Object.entries(drafts.bans_made).sort((a, b) => b[1].count - a[1].count).slice(0, TOP_N) : []), [drafts]);
  const topBansAgainst = useMemo(
    () => (drafts ? Object.entries(drafts.bans_against).sort((a, b) => b[1].count - a[1].count).slice(0, TOP_N) : []),
    [drafts]
  );

  const stabilityRows = useMemo(
    () => TEAM_IDS.map((tid) => ({ tid, s: groupStageStability[String(tid)] })).filter((r) => r.s && (r.s.group_stage_wins || r.s.group_stage_losses)),
    []
  );

  const players: [string, GSPlayerStats][] = useMemo(() => {
    let entries = Object.entries(groupStagePlayerStats);
    if (teamFilter !== "all") entries = entries.filter(([, p]) => p.team_id === teamFilter);
    return entries.sort((a, b) => (b[1][sortKey] ?? -Infinity) - (a[1][sortKey] ?? -Infinity));
  }, [teamFilter, sortKey]);

  return (
    <div>
      <div className={styles.tabs}>
        {(
          [
            ["draft", "Draft (isolated)"],
            ["stability", "Comeback & choke"],
            ["players", "Player stats"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button key={key} className={tab === key ? styles.tabActive : styles.tab} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "draft" && (
        <>
          <select className={styles.select} value={teamId} onChange={(e) => setTeamId(Number(e.target.value))}>
            {TEAM_IDS.map((tid) => (
              <option key={tid} value={tid}>
                {TEAM_CANONICAL[tid]}
              </option>
            ))}
          </select>
          <div className={styles.grid3}>
            <div className="card">
              <h3>Top picks</h3>
              <table className="dataTable">
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
                      <td className="mono">{pct(v.win_rate)}</td>
                      <td className="mono muted">{v.pick_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h3>Bans they made</h3>
              <table className="dataTable">
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
                      <td className="mono muted">{v.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h3>Banned against them</h3>
              <table className="dataTable">
                <thead>
                  <tr>
                    <th>Hero</th>
                    <th>Count</th>
                    <th>Most often by</th>
                  </tr>
                </thead>
                <tbody>
                  {topBansAgainst.map(([heroId, v]) => {
                    const topOpp = Object.entries(v.by_opponent).sort((a, b) => b[1].count - a[1].count)[0];
                    return (
                      <tr key={heroId}>
                        <td>{v.hero_name}</td>
                        <td className="mono muted">{v.count}</td>
                        <td className="muted">{topOpp ? `${topOpp[1].team_name} (${topOpp[1].count})` : "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "stability" && (
        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Team</th>
                <th>Record</th>
                <th>Comeback rate</th>
                <th>Choke rate</th>
                <th>Matches w/ gold data</th>
              </tr>
            </thead>
            <tbody>
              {stabilityRows
                .sort((a, b) => (b.s!.comeback_rate ?? 0) - (a.s!.comeback_rate ?? 0))
                .map(({ tid, s }) => (
                  <tr key={tid}>
                    <td className={styles.teamCell}>
                      <TeamLogo teamId={tid} />
                      {TEAM_CANONICAL[tid]}
                    </td>
                    <td className="mono">
                      {s!.group_stage_wins}-{s!.group_stage_losses}
                    </td>
                    <td className="mono">
                      {pct(s!.comeback_rate)} <span className="muted">({s!.comeback_wins}/{s!.group_stage_wins})</span>
                    </td>
                    <td className="mono">
                      {pct(s!.choke_rate)} <span className="muted">({s!.choke_losses}/{s!.group_stage_losses})</span>
                    </td>
                    <td className="mono muted">{s!.matches_with_comeback_data}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "players" && (
        <>
          <div className={styles.playerControls}>
            <select className={styles.select} value={teamFilter} onChange={(e) => setTeamFilter(e.target.value === "all" ? "all" : Number(e.target.value))}>
              <option value="all">All teams</option>
              {TEAM_IDS.map((tid) => (
                <option key={tid} value={tid}>
                  {TEAM_CANONICAL[tid]}
                </option>
              ))}
            </select>
            <select className={styles.select} value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
              {SORT_OPTIONS.map(([key, label]) => (
                <option key={key} value={key}>
                  Sort by {label}
                </option>
              ))}
            </select>
          </div>
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Team</th>
                  <th>Role</th>
                  <th>Games</th>
                  <th>KDA</th>
                  <th>K/D/A</th>
                  <th>GPM</th>
                  <th>XPM</th>
                  <th>LH/Denies</th>
                  <th>Obs/Sen</th>
                  <th>Rune pickups/g</th>
                </tr>
              </thead>
              <tbody>
                {players.map(([accountId, p]) => (
                  <tr key={accountId}>
                    <td>{p.player_name}</td>
                    <td className="muted">{p.team_name}</td>
                    <td className="muted">{p.primary_lane_role ?? "-"}</td>
                    <td className="mono muted">{p.games_played}</td>
                    <td className="mono">{p.kda.toFixed(2)}</td>
                    <td className="mono muted">
                      {p.avg_kills}/{p.avg_deaths}/{p.avg_assists}
                    </td>
                    <td className="mono">{p.avg_gold_per_min}</td>
                    <td className="mono muted">{p.avg_xp_per_min}</td>
                    <td className="mono muted">
                      {p.avg_last_hits}/{p.avg_denies}
                    </td>
                    <td className="mono muted">
                      {p.avg_obs_placed}/{p.avg_sen_placed}
                    </td>
                    <td className={p.primary_lane_role === "mid" ? "mono" : "mono muted"}>
                      {p.avg_rune_pickups != null ? `${p.avg_rune_pickups} (n=${p.games_with_rune_data})` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
