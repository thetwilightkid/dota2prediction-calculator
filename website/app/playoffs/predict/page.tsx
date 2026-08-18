import type { Metadata } from "next";
import PlayoffPredictClient from "@/components/PlayoffPredictClient";

export const metadata: Metadata = { title: "Predict a Matchup - TI2026 Playoffs" };

export default function PlayoffPredictPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Predict a playoff matchup</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Single-game win chances for the announced UB Round 1 matchups, plus a tool to add any hypothetical pairing
        among the 8 playoff teams.
      </p>
      <PlayoffPredictClient />
    </div>
  );
}
