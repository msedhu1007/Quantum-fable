import Link from "next/link";
import type { Alert } from "@/lib/api";

const decisionStyles: Record<string, string> = {
  CALL: "bg-gradient-to-r from-emerald-500/25 to-teal-400/15 text-emerald-300 border-emerald-400/40 shadow-[0_0_14px_rgba(16,185,129,0.25)]",
  PUT: "bg-gradient-to-r from-rose-500/25 to-pink-400/15 text-rose-300 border-rose-400/40 shadow-[0_0_14px_rgba(244,63,94,0.25)]",
  "NO TRADE": "bg-white/[0.06] text-slate-400 border-white/15",
};

const edgeStyles: Record<string, string> = {
  CALL: "before:bg-gradient-to-b before:from-emerald-400 before:to-teal-500",
  PUT: "before:bg-gradient-to-b before:from-rose-400 before:to-pink-500",
  "NO TRADE": "before:bg-white/15",
};

export default function AlertCard({ alert }: { alert: Alert }) {
  const c = alert.contract;
  return (
    <div
      className={`card card-hover relative overflow-hidden pl-5 before:absolute before:inset-y-0 before:left-0 before:w-1 ${edgeStyles[alert.decision]}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`rounded-lg border px-2.5 py-0.5 text-xs font-bold tracking-wide ${decisionStyles[alert.decision]}`}
          >
            {alert.decision}
          </span>
          <Link
            href={`/research/${alert.symbol}`}
            className="font-mono text-lg font-bold transition-colors hover:text-cyan-300"
          >
            {alert.symbol}
          </Link>
          <span className="rounded-lg bg-white/[0.06] px-2 py-0.5 font-mono text-xs text-violet-300">
            {alert.score}/100
          </span>
          {alert.confidence && (
            <span className="text-xs text-slate-400">Confidence: {alert.confidence}</span>
          )}
        </div>
        <span className="text-xs text-slate-500">
          {new Date(alert.created_at).toLocaleString()}
        </span>
      </div>

      {c && (
        <p className="mt-2 font-mono text-sm text-slate-300">
          {alert.symbol} {c.expiration} {c.strike}
          {c.option_type === "call" ? "C" : "P"} · Δ {c.delta ?? "—"} · IV{" "}
          {c.iv != null ? `${(c.iv * 100).toFixed(1)}%` : "—"} · Vol {c.volume ?? "—"} · OI{" "}
          {c.open_interest ?? "—"} · Spread {c.spread_pct}%
        </p>
      )}

      {alert.reasons && alert.reasons.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-sm text-slate-400">
          {alert.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {alert.risks && alert.risks.length > 0 && (
        <p className="mt-2 text-xs text-amber-300/90">⚠ {alert.risks.join(" · ")}</p>
      )}
      {alert.invalidation_level && (
        <p className="mt-1 text-xs text-slate-500">Invalidation: {alert.invalidation_level}</p>
      )}
    </div>
  );
}
