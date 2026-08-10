import styles from "./TeamLogo.module.css";
import { TEAM_CANONICAL } from "@/data/teams";
import { teamLogo } from "@/lib/teamLogos";

// Rendered as a background-image on a span rather than an <img>, matching the
// approach in the sibling calculator project - keeps the crests crisp at any
// size without pulling in next/image or tripping the no-img-element lint rule.
export default function TeamLogo({
  teamId,
  size = "sm",
  className,
}: {
  teamId: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const name = TEAM_CANONICAL[teamId] ?? String(teamId);
  const src = teamLogo(teamId);
  const classes = [styles.logo, styles[size], className].filter(Boolean).join(" ");

  if (!src) {
    return (
      <span className={`${classes} ${styles.fallback}`} title={name} aria-hidden="true">
        {name.slice(0, 2).toUpperCase()}
      </span>
    );
  }

  return <span className={classes} style={{ backgroundImage: `url("${src}")` }} title={name} aria-hidden="true" />;
}
