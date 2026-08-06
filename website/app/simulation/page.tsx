import type { Metadata } from "next";
import SimulationClient from "@/components/SimulationClient";

export const metadata: Metadata = { title: "Simulation - TI2026 Group Stage" };

export default function SimulationPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Monte Carlo group-stage simulation</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Swiss-format simulation (5 rounds max, 4 wins to advance, 4 losses to eliminate), sampling a fresh rating per
        team per trial from its rating distribution.
      </p>
      <SimulationClient />
    </div>
  );
}
