"use client";

import { useEffect, useState } from "react";
import { api, type WatchlistEntry } from "@/lib/api";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistEntry[]>([]);
  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.watchlist().then(setItems).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim()) return;
    setError(null);
    try {
      await api.addSymbol(symbol.trim().toUpperCase());
      setSymbol("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add");
    }
  };

  const remove = async (s: string) => {
    await api.removeSymbol(s).catch(() => {});
    load();
  };

  return (
    <div className="space-y-6">
      <h1 className="grad-text text-3xl font-extrabold tracking-tight">Watchlist</h1>

      <form onSubmit={add} className="flex gap-2">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="Add ticker (e.g. NVDA)"
          className="input font-mono uppercase"
        />
        <button className="btn-primary">+ Add</button>
      </form>
      {error && <p className="text-sm text-rose-400">{error}</p>}

      <div className="card !p-0">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr className="border-b border-white/10">
              <th className="px-4 py-3 font-medium uppercase tracking-wide">Symbol</th>
              <th className="font-medium uppercase tracking-wide">Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((w) => (
              <tr
                key={w.id}
                className="border-t border-white/5 transition-colors hover:bg-white/[0.04]"
              >
                <td className="px-4 py-3">
                  <a
                    href={`/research/${w.symbol}`}
                    className="font-mono font-bold transition-colors hover:text-cyan-300"
                  >
                    {w.symbol}
                  </a>
                </td>
                <td className="text-slate-500">{new Date(w.added_at).toLocaleDateString()}</td>
                <td className="pr-4 text-right">
                  <button
                    onClick={() => remove(w.symbol)}
                    className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300 transition-colors hover:bg-rose-500/25"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
