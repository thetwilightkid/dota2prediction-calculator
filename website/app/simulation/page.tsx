import type { Metadata } from "next";
import SimulationClient from "@/components/SimulationClient";

export const metadata: Metadata = { title: "Simulation Results - TI2026 Group Stage" };

export default function SimulationPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Simulated tournament results</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        We simulate the entire group stage over and over (each team gets a randomly drawn strength each time, based on
        how confident we are in their rating) and count how often each team ends up with each record. Teams play up
        to 5 matches; 4 wins advances, 4 losses eliminates.
      </p>
      <SimulationClient />
    </div>
  );
}
