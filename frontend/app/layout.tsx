import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Options Signal Alert Engine",
  description: "Research and alerting tool — not financial advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl border-t border-white/10 px-4 py-6 text-xs text-slate-500">
          Research alerts only. Options involve substantial risk. Nothing here is
          financial advice or a recommendation to trade.
        </footer>
      </body>
    </html>
  );
}
