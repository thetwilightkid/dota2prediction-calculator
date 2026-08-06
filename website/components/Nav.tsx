"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/matchups", label: "Matchups" },
  { href: "/simulation", label: "Simulation" },
  { href: "/drafts", label: "Drafts & Patch" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand}>
          TI2026 <span className={styles.brandAccent}>Group Stage</span>
        </Link>
        <nav className={styles.links}>
          {LINKS.map((link) => (
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
