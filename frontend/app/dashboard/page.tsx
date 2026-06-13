"use client";

import { useEffect, useState } from "react";
import AlertCard from "@/components/AlertCard";
import Momentum from "@/components/Momentum";
import { api, type Alert, type ScannerStatus, type WatchlistEntry } from "@/lib/api";

function ScannerCard({
  status,
  intervalMin,
  marketOpen,
}: {
  status: ScannerStatus | null;
  intervalMin: number | null;
  marketOpen: boolean | null;
}) {
  return (
    <div className="card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-gradient-to-r before:from-violet-500 before:to-cyan-400">
      <p className="text-xs uppercase tracking-wide text-slate-400">Alert scanner</p>
      {!status ? (
        <p className="mt-1 text-sm text-slate-500">—</p>
      ) : status.last_scan_at ? (
        <>
          <p className="mt-1 font-mono text-sm text-slate-200">
            {status.scanned} scanned ·{" "}
            <span className="text-emerald-300">{status.calls} CALL</span> ·{" "}
            <span className="text-rose-300">{status.puts} PUT</span> ·{" "}
            <span className="text-slate-400">{status.no_trades} no-trade</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Last scan {new Date(status.last_scan_at).toLocaleTimeString()}
            {intervalMin ? ` · every ${intervalMin} min` : ""}
          </p>
        </>
      ) : (
        <p className="mt-1 text-sm text-slate-400">
          {status.skipped_reason
            ? `Idle — ${status.skipped_reason}`
            : marketOpen === false
              ? "Idle — market closed"
              : "No scan yet this session"}
          {intervalMin ? ` · runs every ${intervalMin} min` : ""}
        </p>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null);
  const [scanner, setScanner] = useState<ScannerStatus | null>(null);
  const [intervalMin, setIntervalMin] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.alerts({ actionableOnly: true }).then(setAlerts).catch((e) => setError(e.message));
    api.watchlist().then(setWatchlist).catch(() => {});
    api
      .health()
      .then((h) => {
        setMarketOpen(h.market_open);
        setScanner(h.scanner ?? null);
        setIntervalMin(h.scan_interval_minutes ?? null);
      })
      .catch(() => {});
  };

  useEffect(load, []);

  const runScan = async () => {
    setScanning(true);
    setError(null);
    try {
      await api.scan();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const calls = alerts.filter((a) => a.decision === "CALL").length;
  const puts = alerts.filter((a) => a.decision === "PUT").length;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="grad-text text-3xl font-extrabold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Research signals — not financial advice.
          </p>
        </div>
        <div className="flex items-center gap-4">
          {marketOpen !== null && (
            <span
              className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm ${
                marketOpen
                  ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                  : "border-white/10 bg-white/[0.04] text-slate-400"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  marketOpen ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" : "bg-slate-600"
                }`}
              />
              Market {marketOpen ? "open" : "closed"}
            </span>
          )}
          <button onClick={runScan} disabled={scanning} className="btn-primary">
            {scanning ? "Scanning…" : "⚡ Scan now"}
          </button>
        </div>
      </div>

      {error && (
        <p className="card border-rose-400/40 bg-rose-500/10 text-sm text-rose-300">{error}</p>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Tickers tracked", value: watchlist.length, color: "text-cyan-300" },
          { label: "Active signals", value: alerts.length, color: "text-violet-300" },
          { label: "CALL signals", value: calls, color: "text-emerald-300" },
          { label: "PUT signals", value: puts, color: "text-rose-300" },
        ].map((s) => (
          <div key={s.label} className="card">
            <p className="text-xs uppercase tracking-wide text-slate-400">{s.label}</p>
            <p className={`mt-1 font-mono text-3xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <ScannerCard status={scanner} intervalMin={intervalMin} marketOpen={marketOpen} />

      <Momentum />

      <section>
        <h2 className="section-label">Watchlist</h2>
        <div className="flex flex-wrap gap-2">
          {watchlist.map((w) => (
            <a key={w.id} href={`/research/${w.symbol}`} className="chip">
              {w.symbol}
            </a>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="section-label">Recent signals</h2>
        {alerts.length === 0 && (
          <div className="card text-sm text-slate-400">
            No CALL/PUT signals yet. Run a scan or wait for the scheduler — alerts land here
            and on your notification channels when a setup crosses the score threshold.
          </div>
        )}
        {alerts.map((a) => (
          <AlertCard key={a.id} alert={a} />
        ))}
      </section>
    </div>
  );
}
