import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "TI2026 Group Stage Predictions",
  description: "TI2026 group-stage prediction dashboard: ratings, head-to-head grid, Monte Carlo simulation, and draft data for all 16 teams.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
