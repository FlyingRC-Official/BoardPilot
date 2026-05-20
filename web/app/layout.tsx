import type { Metadata } from "next";
import "./globals.css";
import { Navigation } from "@/components/navigation/Navigation";

export const metadata: Metadata = {
  title: "BoardPilot",
  description: "Private RAG support workbench for hardware teams"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Navigation />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

