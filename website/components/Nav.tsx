"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const SECTIONS = {
  playoffs: {
    tabHref: "/",
    tabLabel: "Playoffs",
    links: [
      { href: "/", label: "Bracket & odds" },
      { href: "/playoffs/scouting", label: "Scouting report" },
      { href: "/playoffs/predict", label: "Predict a matchup" },
    ],
  },
  groupStage: {
    tabHref: "/group-stage",
    tabLabel: "Group Stage",
    links: [
      { href: "/group-stage", label: "Rankings" },
      { href: "/group-stage/matches", label: "Match predictions" },
      { href: "/group-stage/matchups", label: "Head-to-head" },
      { href: "/group-stage/simulation", label: "Simulated results" },
      { href: "/group-stage/drafts", label: "Heroes & patch" },
      { href: "/group-stage/stats", label: "Isolated stats" },
    ],
  },
} as const;

export default function Nav() {
  const pathname = usePathname();
  const activeSection = pathname.startsWith("/group-stage") ? "groupStage" : "playoffs";
  const section = SECTIONS[activeSection];

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand}>
          TI2026 <span className={styles.brandAccent}>Predictions</span>
        </Link>
        <nav className={styles.tabs}>
          {(Object.keys(SECTIONS) as (keyof typeof SECTIONS)[]).map((key) => (
            <Link
              key={key}
              href={SECTIONS[key].tabHref}
              className={activeSection === key ? styles.tabActive : styles.tab}
            >
              {SECTIONS[key].tabLabel}
            </Link>
          ))}
        </nav>
      </div>
      <div className={styles.inner}>
        <nav className={styles.links}>
          {section.links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={pathname === link.href ? styles.activeLink : styles.link}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
