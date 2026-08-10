import Link from "next/link";
import styles from "./GroupsCard.module.css";
import TeamLogo from "./TeamLogo";
import { TEAM_CANONICAL } from "@/data/teams";
import { precomputedSimulation } from "@/data/simulation";
import { advanceChance } from "@/lib/simulate";

const TEAM_POD = precomputedSimulation.meta.team_pod;
const PODDED_ROUNDS = precomputedSimulation.meta.podded_rounds;

const GROUP_LABELS: Record<string, { name: string; slot: string }> = {
  A: { name: "Group A", slot: "morning matches" },
  B: { name: "Group B", slot: "afternoon matches" },
};

function teamsInGroup(pod: string): number[] {
  return Object.keys(TEAM_POD)
    .filter((tid) => TEAM_POD[tid] === pod)
    .map(Number);
}

/**
 * The two hidden groups the 16 teams are split into for the opening rounds.
 * `advanceByTeam` lets a parent pass live (slider-adjusted) numbers in; without
 * it the card falls back to the standard precomputed prediction.
 */
export default function GroupsCard({ advanceByTeam }: { advanceByTeam?: Map<number, number> }) {
  function chanceFor(teamId: number): number {
    const live = advanceByTeam?.get(teamId);
    if (live != null) return live;
    return advanceChance(precomputedSimulation.teams[String(teamId)]?.outcome_pct);
  }

  return (
    <section className={`card ${styles.card}`}>
      <div className={styles.header}>
        <h2>The two groups</h2>
        <span className="pill">Not officially announced</span>
      </div>
      <p className={styles.intro}>
        The 16 teams are split into two halves that play at different times of day. For the first {PODDED_ROUNDS}{" "}
        rounds a team only faces others from its own half; after that anyone can meet anyone. We
        worked the split out from the published schedule - every one of the 8 announced Day 1 matches is between two
        teams of the same half, which is exactly how last year&apos;s tournament ran. Percentages below are each
        team&apos;s chance to make it out of the group stage.
      </p>
      <div className={styles.groups}>
        {(["A", "B"] as const).map((pod) => {
          const teams = teamsInGroup(pod).sort((a, b) => chanceFor(b) - chanceFor(a));
          return (
            <div key={pod} className={styles.group}>
              <div className={styles.groupHeader}>
                <span className={styles.groupName}>{GROUP_LABELS[pod].name}</span>
                <span className={styles.groupSlot}>{GROUP_LABELS[pod].slot}</span>
              </div>
              <div className={styles.teamList}>
                {teams.map((tid) => {
                  const chance = chanceFor(tid);
                  return (
                    <div key={tid} className={styles.teamRow}>
                      <TeamLogo teamId={tid} size="md" />
                      <Link href={`/teams/${tid}`} className={styles.teamName}>
                        {TEAM_CANONICAL[tid]}
                      </Link>
                      <span className={`${styles.chance} ${chance >= 50 ? styles.chanceStrong : ""}`}>
                        {chance.toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
