import type { Metadata } from "next";
import Link from "next/link";
import PlayoffBracketClient from "@/components/PlayoffBracketClient";

export const metadata: Metadata = { title: "Playoff Bracket - TI2026" };

export default function PlayoffsHome() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>TI2026 playoff bracket simulation</h1>
      <p className="muted" style={{ marginBottom: 8 }}>
        The 8 teams that qualified out of the Group Stage now play a double-elimination bracket (Aug 20-23): 14
        matches, best-of-3 throughout except a best-of-5 Grand Final, no bracket reset. We simulate the entire
        bracket a million times, sampling each team&apos;s strength from their rating distribution every time, using
        the real announced Upper Bracket Round 1 seeding as the fixed starting point. Drag the sliders on the right
        to see how weighting different factors (recent form, expert predictions, etc.) changes these odds.
      </p>
      <p className="muted" style={{ marginBottom: 16 }}>
        <Link href="/playoffs/scouting" className="pill">
          Scouting report: picks, bans &amp; tendencies &rarr;
        </Link>{" "}
        <Link href="/playoffs/predict" className="pill" style={{ marginLeft: 8 }}>
          Predict a custom matchup &rarr;
        </Link>
      </p>
      <PlayoffBracketClient />
    </div>
  );
}
