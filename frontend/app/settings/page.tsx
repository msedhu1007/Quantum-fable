"use client";

import { useEffect, useState } from "react";
import { api, type WatchlistEntry } from "@/lib/api";

type Providers = Awaited<ReturnType<typeof api.providers>>;
type Settings = Awaited<ReturnType<typeof api.settings>>;

function Dot({ on }: { on: boolean }) {
  return (
    <span className={`inline-block h-2.5 w-2.5 rounded-full ${on ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-slate-700"}`} />
  );
}

function StatusTable({ title, entries }: { title: string; entries: Record<string, boolean> }) {
  return (
    <div className="card">
      <h2 className="section-label">{title}</h2>
      <ul className="space-y-2 text-sm">
        {Object.entries(entries).map(([name, on]) => (
          <li key={name} className="flex items-center gap-2 text-slate-300">
            <Dot on={on} />
            <span className="font-mono">{name}</span>
            <span className="text-xs text-slate-500">{on ? "configured" : "not configured"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StockUniverse({ maxTickers }: { maxTickers: number }) {
  const [items, setItems] = useState<WatchlistEntry[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.watchlist().then(setItems).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  function add(e: React.FormEvent) {
    e.preventDefault();
    const sym = input.trim().toUpperCase();
    if (!sym) return;
    setError(null);
    api
      .addSymbol(sym)
      .then(() => {
        setInput("");
        load();
      })
      .catch((err) => setError(err.message));
  }

  function remove(sym: string) {
    api.removeSymbol(sym).then(load).catch((err) => setError(err.message));
  }

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="section-label !mb-0">Alert scanner watchlist</h2>
        <span className={`font-mono text-xs ${items.length >= maxTickers ? "text-rose-400" : "text-slate-500"}`}>
          {items.length}/{maxTickers}
        </span>
      </div>
      <p className="mb-4 text-xs text-slate-500">
        These tickers are scanned every cycle for CALL/PUT alerts. The momentum board has
        its own list — edit it via “Edit universe” on the dashboard (it falls back to this
        watchlist + SPY/QQQ/IWM/SMH while empty).
      </p>

      <form onSubmit={add} className="mb-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker (e.g. NVDA)"
          className="input flex-1 font-mono uppercase"
          disabled={items.length >= maxTickers}
        />
        <button
          type="submit"
          className="btn-primary text-sm"
          disabled={items.length >= maxTickers || !input.trim()}
        >
          + Add
        </button>
      </form>

      {error && <p className="mb-3 text-sm text-rose-400">{error}</p>}

      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item.symbol}
            className="group flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-xs text-slate-300 transition-colors hover:border-rose-500/40 hover:bg-rose-400/5"
          >
            {item.symbol}
            <button
              onClick={() => remove(item.symbol)}
              className="ml-0.5 text-slate-600 transition-colors hover:text-rose-400 group-hover:text-rose-400"
              title={`Remove ${item.symbol}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>

      {items.length === 0 && (
        <p className="text-sm text-slate-500">No tickers added. Add some above to start scanning.</p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<Providers | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.providers(), api.settings()])
      .then(([p, s]) => {
        setProviders(p);
        setSettings(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-rose-400">{error}</p>;
  if (!providers || !settings) return <p className="text-slate-400">Loading settings…</p>;

  const filters = settings.contract_filters;

  return (
    <div className="space-y-6">
      <h1 className="grad-text text-3xl font-extrabold tracking-tight">Settings</h1>
      <p className="text-sm text-slate-400">
        Configured through backend environment variables (see{" "}
        <code className="text-cyan-300">.env.example</code>). Active market data provider:{" "}
        <span className="font-mono text-cyan-300">{providers.market_data_provider}</span>
      </p>

      <StockUniverse maxTickers={settings.max_watchlist} />

      <div className="grid gap-4 md:grid-cols-2">
        <StatusTable title="Data providers" entries={providers.providers} />
        <StatusTable title="Alert channels" entries={providers.alert_channels} />
      </div>

      <div className="card">
        <h2 className="section-label">Scanner thresholds</h2>
        <table className="w-full text-left text-sm">
          <tbody className="text-slate-300">
            {[
              ["Scan interval", `${settings.scan_interval_minutes} min`],
              ["Market hours only", String(settings.market_hours_only)],
              ["CALL / PUT score thresholds", `${settings.call_score_threshold} / ${settings.put_score_threshold}`],
              ["Alert cooldown", `${settings.alert_cooldown_minutes} min`],
              ["DTE window", `${filters.min_dte}–${filters.max_dte} days`],
              ["Min open interest", filters.min_open_interest],
              ["Min volume", filters.min_volume],
              ["Max spread", `${filters.max_spread_pct}%`],
              ["Delta band", `${filters.min_abs_delta}–${filters.max_abs_delta} (abs)`],
              ["Market benchmark", settings.market_benchmark],
            ].map(([k, v]) => (
              <tr key={String(k)} className="border-t border-white/5">
                <td className="py-2 text-slate-400">{k}</td>
                <td className="py-2 font-mono">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
