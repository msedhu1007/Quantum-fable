"use client";

import { useEffect, useState } from "react";
import {
  api,
  type MomentumRow,
  type MomentumSnapshot,
  type MomentumUniverse,
  type Research,
} from "@/lib/api";

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.abs(score), 100);
  const grad =
    score > 0 ? "bg-gradient-to-r from-emerald-500 to-teal-400" : "bg-gradient-to-r from-rose-500 to-pink-400";
  return (
    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
      <div className={`h-full rounded-full ${grad}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function DirectionBadge({ direction }: { direction: MomentumRow["direction"] }) {
  const styles = {
    CALL: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    PUT: "border-rose-400/40 bg-rose-400/10 text-rose-300",
    FLAT: "border-white/15 bg-white/[0.05] text-slate-400",
  } as const;
  const label = { CALL: "CALL bias", PUT: "PUT bias", FLAT: "flat" }[direction];
  return (
    <span className={`rounded-lg border px-2 py-0.5 text-[11px] font-bold ${styles[direction]}`}>
      {label}
    </span>
  );
}

function ExpandedDetail({
  symbol,
  direction,
}: {
  symbol: string;
  direction: MomentumRow["direction"];
}) {
  const [res, setRes] = useState<Research | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.research(symbol).then(setRes).catch((e) => setError(e.message));
  }, [symbol]);

  if (error) return <p className="px-4 pb-4 text-xs text-rose-400">{error}</p>;
  if (!res)
    return (
      <p className="px-4 pb-4 text-xs text-slate-400">
        Pulling options chain, news, fundamentals for {symbol}…
      </p>
    );

  const d = res.data;
  // Contract follows the momentum direction of this row, not the overall verdict
  const contract =
    direction === "PUT" ? d.best_put ?? d.best_call : d.best_call ?? d.best_put;
  return (
    <div className="space-y-3 border-t border-white/5 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-slate-300">
        <span>
          Engine score{" "}
          <span className="font-mono font-bold text-violet-300">{res.score}</span>
        </span>
        <span>
          Verdict <span className="font-bold">{res.verdict.decision}</span>
        </span>
        <span>Tech {d.technical_rating?.replace("_", " ") ?? "—"}</span>
        <span>Fund {d.fundamental_rating?.replace("_", " ") ?? "—"}</span>
        <span>Sentiment {d.news_sentiment != null ? d.news_sentiment.toFixed(2) : "—"}</span>
        <span>C/P ratio {d.call_volume_ratio ?? "—"}</span>
        {d.next_earnings_date && <span>Earnings {d.next_earnings_date}</span>}
      </div>
      {contract ? (
        <p className="font-mono text-xs text-slate-200">
          Best {contract.option_type.toUpperCase()}: {symbol} {contract.expiration}{" "}
          {contract.strike}
          {contract.option_type === "call" ? "C" : "P"} · Δ {contract.delta ?? "—"} · IV{" "}
          {contract.iv != null ? `${(contract.iv * 100).toFixed(1)}%` : "—"} · Vol{" "}
          {contract.volume ?? "—"} · OI {contract.open_interest ?? "—"} · Spread{" "}
          {contract.spread_pct}%
        </p>
      ) : (
        <p className="text-xs text-slate-500">
          No contract currently passes liquidity/delta filters.
        </p>
      )}
      <div className="flex items-center gap-3">
        <a href={`/research/${symbol}`} className="text-xs text-cyan-300 hover:underline">
          Full research →
        </a>
        <span className="text-[10px] text-slate-500">
          Research ranking — not investment advice.
        </span>
      </div>
    </div>
  );
}

function UniverseEditor({ onChange }: { onChange: () => void }) {
  const [uni, setUni] = useState<MomentumUniverse | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.momentumUniverse().then(setUni).catch(() => {});
  };
  useEffect(load, []);

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = input.trim().toUpperCase();
    if (!sym) return;
    setError(null);
    api
      .addMomentumSymbol(sym)
      .then(() => {
        setInput("");
        load();
        onChange();
      })
      .catch((err) => setError(err.message));
  };

  const remove = (sym: string) => {
    api
      .removeMomentumSymbol(sym)
      .then(() => {
        load();
        onChange();
      })
      .catch((err) => setError(err.message));
  };

  if (!uni) return <p className="px-1 py-2 text-xs text-slate-500">Loading universe…</p>;

  return (
    <div className="card mb-3 !p-3">
      <div className="mb-2 flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Momentum universe
        </span>
        {uni.fallback && (
          <span className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-2 py-0.5 text-[10px] text-amber-300">
            empty — using alert watchlist + SPY/QQQ/IWM/SMH
          </span>
        )}
        <span className="ml-auto font-mono text-[10px] text-slate-500">
          {uni.symbols.length}/50
        </span>
      </div>
      <form onSubmit={add} className="mb-2 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker for momentum tracking (e.g. PLTR)"
          className="input flex-1 font-mono text-xs uppercase"
        />
        <button className="btn-primary !px-3 !py-1.5 text-xs" disabled={!input.trim()}>
          + Add
        </button>
      </form>
      {error && <p className="mb-2 text-xs text-rose-400">{error}</p>}
      <div className="flex flex-wrap gap-1.5">
        {uni.symbols.map((s) => (
          <span
            key={s.symbol}
            className="group flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-xs text-slate-300"
          >
            {s.symbol}
            <button
              onClick={() => remove(s.symbol)}
              className="text-slate-600 transition-colors hover:text-rose-400"
              title={`Remove ${s.symbol}`}
            >
              ×
            </button>
          </span>
        ))}
        {uni.symbols.length === 0 && (
          <span className="text-xs text-slate-500">
            Add tickers to track a custom momentum universe, or keep using the watchlist.
          </span>
        )}
      </div>
    </div>
  );
}

export default function Momentum() {
  const [snap, setSnap] = useState<MomentumSnapshot | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = () => api.momentum(20).then(setSnap).catch(() => {});

  useEffect(() => {
    load();
    // poll only while backend is scanning, every 10s
    const t = setInterval(() => {
      setSnap((cur) => {
        if (cur?.scanning || (cur && cur.results.length === 0)) load();
        return cur;
      });
    }, 10_000);
    return () => clearInterval(t);
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshMomentum();
      setTimeout(load, 3000);
    } finally {
      setTimeout(() => setRefreshing(false), 3000);
    }
  };

  const rows = snap?.results ?? [];
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="section-label !mb-0">Momentum — top option setups</h2>
          <p className="text-[11px] text-slate-500">
            Your watchlist ranked by technical momentum. Expand a row for the
            options-aware view. Research only — not advice.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {snap?.using_watchlist_fallback && (
            <span className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] text-amber-300">
              watchlist universe
            </span>
          )}
          {snap?.updated_at && (
            <span className="text-[11px] text-slate-500">
              Updated {new Date(snap.updated_at).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => setEditing((v) => !v)}
            className={`rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors ${
              editing
                ? "border-cyan-400/50 bg-cyan-400/15 text-cyan-300"
                : "border-white/15 bg-white/[0.05] text-slate-300 hover:border-cyan-400/40"
            }`}
          >
            {editing ? "Done" : "✎ Edit universe"}
          </button>
          <button
            onClick={refresh}
            disabled={refreshing || snap?.scanning}
            className="rounded-xl border border-violet-400/40 bg-violet-500/10 px-3 py-1.5 text-xs font-semibold text-violet-300 transition-colors hover:bg-violet-500/25 disabled:opacity-50"
          >
            {snap?.scanning || refreshing ? "Scanning…" : "↺ Refresh"}
          </button>
        </div>
      </div>

      {editing && <UniverseEditor onChange={load} />}

      {rows.length === 0 ? (
        <div className="card text-sm text-slate-400">
          {snap?.scanning
            ? "First momentum sweep running — ranking your watchlist, ~1 minute…"
            : "No momentum data yet. Hit Refresh to scan your watchlist."}
        </div>
      ) : (
        <div className="card !p-0">
          {rows.map((r, i) => {
            const isOpen = open === r.symbol;
            return (
              <div key={r.symbol} className={i > 0 ? "border-t border-white/5" : ""}>
                <button
                  onClick={() => setOpen(isOpen ? null : r.symbol)}
                  className="flex w-full items-center gap-4 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.04]"
                >
                  <span className="w-6 font-mono text-xs text-slate-500">{i + 1}</span>
                  <span className="w-16 font-mono text-sm font-bold">{r.symbol}</span>
                  <DirectionBadge direction={r.direction} />
                  <span
                    className={`w-12 text-right font-mono text-sm font-bold ${
                      r.momentum_score > 0 ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {r.momentum_score > 0 ? "+" : ""}
                    {r.momentum_score}
                  </span>
                  <ScoreBar score={r.momentum_score} />
                  <span className="hidden w-20 text-right font-mono text-xs text-slate-300 md:inline">
                    {r.price ?? "—"}
                  </span>
                  <span
                    className={`hidden w-16 text-right font-mono text-xs md:inline ${
                      (r.change_pct ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {r.change_pct != null ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct}%` : "—"}
                  </span>
                  <span className="hidden text-xs text-slate-400 lg:inline">
                    RSI {r.rsi_14 ?? "—"}
                  </span>
                  {r.breakout && (
                    <span className="hidden rounded bg-emerald-400/10 px-1.5 text-[10px] text-emerald-300 lg:inline">
                      breakout
                    </span>
                  )}
                  {r.breakdown && (
                    <span className="hidden rounded bg-rose-400/10 px-1.5 text-[10px] text-rose-300 lg:inline">
                      breakdown
                    </span>
                  )}
                  <span className="ml-auto text-slate-500">{isOpen ? "▴" : "▾"}</span>
                </button>
                {isOpen && <ExpandedDetail symbol={r.symbol} direction={r.direction} />}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
