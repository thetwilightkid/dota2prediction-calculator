import type { Metadata } from "next";
import MatchPredictionsClient from "@/components/MatchPredictionsClient";

export const metadata: Metadata = { title: "Match Predictions - TI2026 Group Stage" };

export default function MatchesPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Match predictions</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Who&apos;s favored in individual matches, starting with the announced Day 1 schedule.
      </p>
      <MatchPredictionsClient />
    </div>
  );
}
