import type { Metadata } from "next";
import DraftsClient from "@/components/DraftsClient";

export const metadata: Metadata = { title: "Drafts & Patch Impact - TI2026 Group Stage" };

export default function DraftsPage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Pick/ban database & patch 7.41e impact</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        League data mode reflects actual tournament drafts (decayed/tier-weighted); player history mode reflects each
        player&apos;s recent hero comfort independent of team drafts.
      </p>
      <DraftsClient />
    </div>
  );
}
