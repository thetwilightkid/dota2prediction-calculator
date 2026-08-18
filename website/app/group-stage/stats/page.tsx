import type { Metadata } from "next";
import GroupStageClient from "@/components/GroupStageClient";

export const metadata: Metadata = { title: "Group Stage Stats (Isolated) - TI2026" };

export default function GroupStagePage() {
  return (
    <div className="page">
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Group Stage stats, isolated</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Everything on this page comes ONLY from the 109 real TI2026 Group Stage games - not blended with any
        pre-tournament history, so it shows exactly how each team and player actually performed at this event.
        Comeback/choke rates are derived from each match&apos;s own biggest-gold-swing value rather than draft
        predictions, since third-party win-probability curves weren&apos;t available for these matches.
      </p>
      <GroupStageClient />
    </div>
  );
}
