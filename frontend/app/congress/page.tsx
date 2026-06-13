"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Row {
  ticker: string;
  buys: number;
  sells: number;
  buyers: number;
  sellers: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  dem_buys: number;
  rep_buys: number;
  last_traded: string;
}

interface Notable {
  ticker: string;
  name: string;
  party: string | null;
  chamber: string | null;
  type: "BUY" | "SELL";
  range: string | null;
  amount: number;
  traded: string;
  filed: string | null;
}

interface Board {
  window_days: number;
  tickers: number;
  rows: Row[];
  notable: Notable[];
  source: string;
  lag_note: string;
  error?: string;
}

const WINDOWS = [30, 90, 180, 365];

function usd(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n}`;
}

function HighlightCard({
  title,
  row,
  metric,
  color,
}: {
  title: string;
  row: Row | undefined;
  metric: string;
  color: string;
}) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      {row ? (
        <>
          <a
            href={`/research/${row.ticker}`}
            className={`mt-1 block font-mono text-2xl font-bold ${color} hover:underline`}
          >
            {row.ticker}
          </a>
          <p className="text-xs text-slate-400">{metric}</p>
        </>
      ) : (
        <p className="mt-1 text-sm text-slate-500">—</p>
      )}
    </div>
  );
}

export default function CongressPage() {
  const [board, setBoard] = useState<Board | null>(null);
  const [windowDays, setWindowDays] = useState(180);
  const [sortBy, setSortBy] = useState<"buyers" | "buy_value" | "net_value">("buyers");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBoard(null);
    fetch(`${API_BASE}/congress?window=${windowDays}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setBoard(d)))
      .catch((e) => setError(e.message));
  }, [windowDays]);

  if (error) return <p className="text-rose-400">{error}</p>;

  const rows = [...(board?.rows ?? [])].sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));
  const mostBuyers = rows.length ? [...rows].sort((a, b) => b.buyers - a.buyers)[0] : undefined;
  const biggestInflow = rows.length ? [...rows].sort((a, b) => b.buy_value - a.buy_value)[0] : undefined;
  const mostSold = rows.length ? [...rows].sort((a, b) => b.sell_value - a.sell_value)[0] : undefined;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="grad-text text-3xl font-extrabold tracking-tight">Congress Trading</h1>
          <p className="mt-1 text-sm text-slate-400">
            STOCK Act disclosures aggregated per ticker. {board?.lag_note ?? "Disclosures lag up to 45 days."}{" "}
            Research only — not advice.
          </p>
        </div>
        <div className="flex gap-1 rounded-xl border border-white/10 bg-white/[0.04] p-1">
          {WINDOWS.map((w) => (
            <button
              key={w}
              onClick={() => setWindowDays(w)}
              className={`rounded-lg px-3 py-1 text-xs font-semibold transition-colors ${
                windowDays === w
                  ? "bg-gradient-to-r from-violet-600/40 to-blue-500/30 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>

      {!board ? (
        <div className="card text-sm text-slate-400">Loading congressional trades…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <HighlightCard
              title="Most members buying"
              row={mostBuyers}
              metric={`${mostBuyers?.buyers ?? 0} distinct buyers · ${mostBuyers?.buys ?? 0} buys`}
              color="text-emerald-300"
            />
            <HighlightCard
              title="Largest estimated inflow"
              row={biggestInflow}
              metric={`${usd(biggestInflow?.buy_value ?? 0)} min. reported buys`}
              color="text-cyan-300"
            />
            <HighlightCard
              title="Most sold"
              row={mostSold}
              metric={`${usd(mostSold?.sell_value ?? 0)} min. reported sells`}
              color="text-rose-300"
            />
          </div>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="section-label !mb-0">
                Leaderboard — {board.tickers} tickers, last {board.window_days}d
              </h2>
              <div className="flex gap-1 text-xs">
                {(
                  [
                    ["buyers", "by members"],
                    ["buy_value", "by inflow"],
                    ["net_value", "by net flow"],
                  ] as const
                ).map(([k, label]) => (
                  <button
                    key={k}
                    onClick={() => setSortBy(k)}
                    className={`rounded-lg px-2.5 py-1 transition-colors ${
                      sortBy === k
                        ? "bg-violet-500/20 text-violet-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="card !p-0 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr className="border-b border-white/10">
                    <th className="px-4 py-2.5">#</th>
                    <th>Ticker</th>
                    <th className="text-right">Members buying</th>
                    <th className="text-right">Buys</th>
                    <th className="text-right">Sells</th>
                    <th className="text-right">Est. inflow</th>
                    <th className="text-right">Net flow</th>
                    <th className="text-right">D / R buys</th>
                    <th className="pr-4 text-right">Last trade</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.ticker} className="border-t border-white/5 transition-colors hover:bg-white/[0.04]">
                      <td className="px-4 py-2 font-mono text-xs text-slate-500">{i + 1}</td>
                      <td>
                        <a href={`/research/${r.ticker}`} className="font-mono font-bold hover:text-cyan-300">
                          {r.ticker}
                        </a>
                      </td>
                      <td className="text-right font-mono text-emerald-300">{r.buyers}</td>
                      <td className="text-right font-mono">{r.buys}</td>
                      <td className="text-right font-mono text-slate-400">{r.sells}</td>
                      <td className="text-right font-mono text-cyan-300">{usd(r.buy_value)}</td>
                      <td className={`text-right font-mono ${r.net_value >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {usd(r.net_value)}
                      </td>
                      <td className="text-right font-mono text-xs">
                        <span className="text-blue-300">{r.dem_buys}</span>
                        <span className="text-slate-600"> / </span>
                        <span className="text-rose-300">{r.rep_buys}</span>
                      </td>
                      <td className="pr-4 text-right font-mono text-xs text-slate-500">{r.last_traded}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {board.notable.length > 0 && (
            <section>
              <h2 className="section-label">Notable trades (≥ $50k reported)</h2>
              <div className="card !p-0">
                {board.notable.map((t, i) => (
                  <div
                    key={i}
                    className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/5 px-4 py-2 text-sm first:border-t-0"
                  >
                    <span
                      className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
                        t.type === "BUY" ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"
                      }`}
                    >
                      {t.type}
                    </span>
                    <a href={`/research/${t.ticker}`} className="font-mono font-bold hover:text-cyan-300">
                      {t.ticker}
                    </a>
                    <span className="text-slate-200">{t.name}</span>
                    <span className="text-xs text-slate-500">
                      {t.chamber}
                      {t.party ? ` · ${t.party}` : ""}
                    </span>
                    <span className="font-mono text-xs text-slate-400">{t.range}</span>
                    <span className="ml-auto font-mono text-[11px] text-slate-500">
                      traded {t.traded} · filed {t.filed}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
