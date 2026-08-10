import type { Metadata } from "next";
import SimulationClient from "@/components/SimulationClient";

export const metadata: Metadata = { title: "Simulation Results - TI2026 Group Stage" };

export default function SimulationPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Simulated tournament results</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        We simulate the entire group stage over and over (each team gets a randomly drawn strength each time, based on
        how confident we are in their rating) and count how often each team ends up with each record. Teams keep
        playing until they reach 4 wins (advance) or 4 losses (eliminated) - anywhere from 4 to 7 matches. The first
        3 rounds only pit teams against others in their own group (the real tournament splits into two hidden groups
        for scheduling); after that it&apos;s an open field.
      </p>
      <SimulationClient />
    </div>
  );
}
