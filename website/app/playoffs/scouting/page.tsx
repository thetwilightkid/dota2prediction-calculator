import type { Metadata } from "next";
import ScoutingClient from "@/components/ScoutingClient";

export const metadata: Metadata = { title: "Scouting Report - TI2026 Playoffs" };

export default function ScoutingPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Playoff scouting report</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Pick any two of the 8 playoff teams to see how they&apos;re likely to match up: predicted win probability,
        each side&apos;s go-to picks and bans, which heroes they specifically ban when facing this exact opponent, and
        their comeback/choke tendencies.
      </p>
      <ScoutingClient />
    </div>
  );
}
