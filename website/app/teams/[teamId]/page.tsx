import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import styles from "./page.module.css";
import { TEAM_CANONICAL, teamRatings } from "@/data/teams";
import { h2hGrid } from "@/data/h2hGrid";
import { teamStability } from "@/data/stability";
import { leagueDataMode } from "@/data/pickBans";
import { teamPatchImpact } from "@/data/patchImpact";
import { overallWinrate } from "@/data/overallWinrate";
import { precomputedSimulation } from "@/data/simulation";
import TeamLogo from "@/components/TeamLogo";

export function generateStaticParams() {
  return Object.keys(TEAM_CANONICAL).map((teamId) => ({ teamId }));
}

export async function generateMetadata({ params }: PageProps<"/teams/[teamId]">): Promise<Metadata> {
  const { teamId } = await params;
  const name = TEAM_CANONICAL[Number(teamId)];
  return { title: name ? `${name} - TI2026 Group Stage` : "Team - TI2026 Group Stage" };
}

function pct(v: number | null | undefined, digits = 1): string {
  return v != null ? `${(v * 100).toFixed(digits)}%` : "-";
}

export default async function TeamDetailPage({ params }: PageProps<"/teams/[teamId]">) {
  const { teamId: teamIdStr } = await params;
  const teamId = Number(teamIdStr);
  const teamName = TEAM_CANONICAL[teamId];
  if (!teamName) notFound();

  const rating = teamRatings[teamIdStr];
  const stability = teamStability[teamIdStr];
  const drafts = leagueDataMode[teamIdStr];
  const patch = teamPatchImpact[teamIdStr];
  const winrate = overallWinrate[teamIdStr];
  const h2hRow = h2hGrid[teamIdStr] ?? {};
  const pod = precomputedSimulation.meta.team_pod[teamIdStr];

  const topPicks = Object.entries(drafts?.picks ?? {})
    .sort((a, b) => b[1].weighted_pick_count - a[1].weighted_pick_count)
    .slice(0, 5);

  return (
    <div className="page">
      <div className={styles.header}>
        <div className={styles.identity}>
          <TeamLogo teamId={teamId} size="lg" />
          <div>
            <h1>{teamName}</h1>
            {pod && <span className="muted">Group {pod}</span>}
          </div>
        </div>
        <Link href="/" className="pill">
          &larr; back to ranking
        </Link>
      </div>

      <div className={styles.grid}>
        <div className="card">
          <h3>Power score</h3>
          <div className={styles.bigNumber}>
            {rating.rating_scale_mean.toFixed(0)} <span className="muted">± {rating.rating_scale_sigma.toFixed(0)}</span>
          </div>
          <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            One combined strength number (higher is better), with a ± range showing how uncertain we are.
          </p>
          <dl className={styles.detailList}>
            <dt>Track record</dt>
            <dd className="mono">{rating.z_elo.toFixed(2)}</dd>
            <dt>Recent form</dt>
            <dd className="mono">{rating.z_form.toFixed(2)}</dd>
            <dt>Expert opinion</dt>
            <dd className="mono">
              {rating.z_market.toFixed(2)} <span className="muted">({rating.market_n_sources} sources)</span>
            </dd>
            <dt>Independent rating service</dt>
            <dd className="mono">
              {rating.glicko_rating != null ? `${rating.glicko_rating.toFixed(0)} ± ${rating.glicko_phi?.toFixed(0)}` : "n/a"}
            </dd>
          </dl>
        </div>

        <div className="card">
          <h3>Overall win rate</h3>
          {winrate ? (
            <dl className={styles.detailList}>
              <dt>All matches</dt>
              <dd className="mono">
                {pct(winrate.raw_win_rate)} ({winrate.raw_win_count}/{winrate.raw_match_count})
              </dd>
              <dt>Adjusted for tournament importance</dt>
              <dd className="mono">{pct(winrate.tier_weighted_win_rate)}</dd>
              <dt>Adjusted for importance &amp; recency</dt>
              <dd className="mono">{pct(winrate.tier_and_recency_weighted_win_rate)}</dd>
              <dt>Average match length</dt>
              <dd className="mono">
                {winrate.avg_match_duration_seconds
                  ? `${Math.floor(winrate.avg_match_duration_seconds / 60)}:${Math.round(winrate.avg_match_duration_seconds % 60)
                      .toString()
                      .padStart(2, "0")}`
                  : "-"}
              </dd>
            </dl>
          ) : (
            <p className="muted">No data.</p>
          )}
        </div>

        <div className="card">
          <h3>Consistency</h3>
          {stability ? (
            <dl className={styles.detailList}>
              <dt>Predicted win chance right after draft</dt>
              <dd className="mono">{pct(stability.avg_draft_stage_win_rate)}</dd>
              <dt>How often they close it out when favored after draft</dt>
              <dd className="mono">{pct(stability.draft_favored_win_rate)}</dd>
              <dt>How often they win anyway as the draft underdog</dt>
              <dd className="mono">{pct(stability.draft_underdog_win_rate)}</dd>
              <dt>How often they lose from a winning position</dt>
              <dd className="mono">{pct(stability.choke_rate)}</dd>
              <dt>How often they win from a losing position</dt>
              <dd className="mono">{pct(stability.comeback_rate)}</dd>
              <dt>How much their games swing back and forth</dt>
              <dd className="mono">{stability.avg_volatility?.toFixed(3) ?? "-"}</dd>
            </dl>
          ) : (
            <p className="muted">No data.</p>
          )}
        </div>

        <div className="card">
          <h3>Latest patch effect</h3>
          {patch ? (
            <>
              <div className={styles.bigNumber}>{patch.patch_impact_score?.toFixed(4) ?? "n/a"}</div>
              <ul className={styles.compactList}>
                {patch.pool_heroes.slice(0, 5).map((h) => (
                  <li key={h.hero_id}>
                    <span>{h.hero_name}</span>
                    <span className="mono muted">{h.winrate_delta != null ? `${(h.winrate_delta * 100).toFixed(2)}pp` : "-"}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">No data.</p>
          )}
        </div>

        <div className="card">
          <h3>Top picks</h3>
          <ul className={styles.compactList}>
            {topPicks.map(([heroId, v]) => (
              <li key={heroId}>
                <span>{v.hero_name}</span>
                <span className="mono muted">{pct(v.win_rate, 0)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className={`${styles.wide} card`}>
          <h3>Head-to-head vs the other 15 teams</h3>
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Opponent</th>
                  <th>Record</th>
                  <th>Win rate</th>
                  <th>Recent-weighted win rate</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(TEAM_CANONICAL)
                  .map(Number)
                  .filter((oppId) => oppId !== teamId)
                  .map((oppId) => {
                    const cell = h2hRow[String(oppId)];
                    return (
                      <tr key={oppId}>
                        <td>
                          <Link href={`/teams/${oppId}`}>{TEAM_CANONICAL[oppId]}</Link>
                        </td>
                        <td className="mono">{cell && cell.matches_played > 0 ? `${cell.wins}-${cell.losses}` : "never played"}</td>
                        <td className="mono muted">{pct(cell?.win_rate)}</td>
                        <td className="mono muted">{pct(cell?.decayed_win_rate)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
