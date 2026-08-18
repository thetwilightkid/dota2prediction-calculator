import type { Metadata } from "next";
import DraftsClient from "@/components/DraftsClient";

export const metadata: Metadata = { title: "Heroes & Patch - TI2026 Group Stage" };

export default function DraftsPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Hero picks, bans, and the latest patch</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        See what each team actually drafts in tournaments, what each player likes to play individually, and how the
        newest balance patch might affect them.
      </p>
      <DraftsClient />
    </div>
  );
}
