import type { Metadata } from "next";
import OverviewClient from "@/components/OverviewClient";

export const metadata: Metadata = { title: "Group Stage Rankings - TI2026" };

export default function GroupStageHome() {
  return (
    <div className="page">
      <OverviewClient />
    </div>
  );
}
