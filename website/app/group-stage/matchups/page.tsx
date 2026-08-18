import type { Metadata } from "next";
import MatchupGrid from "@/components/MatchupGrid";

export const metadata: Metadata = { title: "Head-to-Head - TI2026 Group Stage" };

export default function MatchupsPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>How every team has done against every other team</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        98 of the 120 possible pairs have actually played each other. Numbers show the row team&apos;s win percentage.
      </p>
      <MatchupGrid />
    </div>
  );
}
