import type { Metadata } from "next";
import MatchupGrid from "@/components/MatchupGrid";

export const metadata: Metadata = { title: "Matchups - TI2026 Group Stage" };

export default function MatchupsPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Head-to-head grid</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        98 of 120 possible pairs have roster-verified match data. Percentages are the row team&apos;s raw win rate.
      </p>
      <MatchupGrid />
    </div>
  );
}
