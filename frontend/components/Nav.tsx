"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: "▦" },
  { href: "/analysis", label: "Analysis", icon: "◎" },
  { href: "/growth-value", label: "Growth & Value", icon: "📈" },
  { href: "/watchlist", label: "Watchlist", icon: "☆" },
  { href: "/alerts", label: "Alerts", icon: "⚡" },
  { href: "/congress", label: "Congress", icon: "🏛" },
  { href: "/settings", label: "Settings", icon: "⚙" },
  { href: "/backtest", label: "Backtest", icon: "↺" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-20 border-b border-white/10 bg-[#070b1a]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
        <Link href="/dashboard" className="mr-4 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-400 text-sm shadow-[0_0_18px_rgba(124,58,237,0.6)]">
            ⚡
          </span>
          <span className="grad-text text-lg font-extrabold tracking-tight">
            Options Signal
          </span>
        </Link>
        {links.map((l) => {
          const active = pathname?.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-xl px-3 py-1.5 text-sm transition-colors duration-150 ${
                active
                  ? "bg-gradient-to-r from-violet-600/30 to-blue-500/25 text-white shadow-[inset_0_0_0_1px_rgba(139,92,246,0.45)]"
                  : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100"
              }`}
            >
              <span className="mr-1.5 opacity-80">{l.icon}</span>
              {l.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
