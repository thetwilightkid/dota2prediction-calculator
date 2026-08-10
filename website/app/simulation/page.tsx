import type { Metadata } from "next";
import SimulationClient from "@/components/SimulationClient";

export const metadata: Metadata = { title: "Simulation Results - TI2026 Group Stage" };

export default function SimulationPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Simulated tournament results</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        We simulate the entire group stage over and over (each team gets a randomly drawn strength each time, based on
        how confident we are in their rating) and count how often each team ends up with each record. The group stage
        runs 6 rounds: the first 3 only pit teams against others in their own group, then it opens up. Reaching 4 wins
        gets a team through and 4 losses knocks them out; anyone still undecided going into the last round plays one
        do-or-die match. That final match is why 3-3 shows up twice below - <strong>(in)</strong> for teams who won it
        and advanced, <strong>(out)</strong> for teams who lost it and went home. Exactly 8 teams advance in every
        single simulated tournament.
      </p>
      <SimulationClient />
    </div>
  );
}
