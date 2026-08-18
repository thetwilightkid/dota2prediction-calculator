import type { Metadata } from "next";
import Link from "next/link";
import PlayoffBracketClient from "@/components/PlayoffBracketClient";

export const metadata: Metadata = { title: "Playoff Bracket - TI2026" };

export default function PlayoffsPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>TI2026 playoff bracket simulation</h1>
      <p className="muted" style={{ marginBottom: 8 }}>
        The 8 teams that qualified out of the Group Stage now play a double-elimination bracket (Aug 20-23): 14
        matches, best-of-3 throughout except a best-of-5 Grand Final, no bracket reset. We simulate the entire
        bracket a million times, sampling each team&apos;s strength from their rating distribution every time, using
        the real announced Upper Bracket Round 1 seeding as the fixed starting point.
      </p>
      <p className="muted" style={{ marginBottom: 16 }}>
        Want to know how any two of these 8 teams are likely to match up in a single game -{" "}
        <Link href="/playoffs/scouting" className="pill">
          see the scouting report &rarr;
        </Link>
      </p>
      <PlayoffBracketClient />
    </div>
  );
}
