import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { WeightsProvider } from "@/lib/WeightsContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "TI2026 Predictions",
  description: "TI2026 prediction dashboard: ratings, head-to-head grid, Monte Carlo simulation, draft data, and a playoff bracket simulator with scouting reports for the 8 qualified teams.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <WeightsProvider>
          <Nav />
          {children}
        </WeightsProvider>
      </body>
    </html>
  );
}
