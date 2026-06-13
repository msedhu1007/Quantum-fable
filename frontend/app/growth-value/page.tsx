"use client";

import { Fragment, useEffect, useState } from "react";
import {
  api,
  type GVSnapshot,
  type GVRow,
  type GVUniverse,
  type GVScorecard,
  type GVFactor,
  type GVEntryGuidance,
  type GVNote,
} from "@/lib/api";

type SortBy = "growth" | "value";

function scoreColor(score: number): string {
  if (score >= 75) return "from-emerald-500 to-emerald-300";
  if (score >= 50) return "from-violet-500 to-blue-400";
  if (score >= 25) return "from-amber-500 to-amber-300";
  return "from-rose-500 to-rose-400";
}

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${scoreColor(score)}`}
          style={{ width: `${Math.max(2, score)}%` }}
        />
      </div>
      <span className="w-7 text-right font-mono text-sm tabular-nums">{score}</span>
    </div>
  );
}

function num(v: number | null | undefined, digits = 1, suffix = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}${suffix}`;
}

function FactorBars({ factors }: { factors: GVFactor[] }) {
  return (
    <div className="space-y-2">
      {factors.map((f) => {
        const pct = f.points === null ? 0 : (f.points / f.max) * 100;
        return (
          <div key={f.key} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
            <div className="min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-slate-300">{f.label}</span>
                <span className="shrink-0 font-mono text-xs text-slate-500">
                  {f.value === null || f.value === undefined ? "n/a" : f.value}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                {f.points === null ? (
                  <div className="h-full w-full bg-[repeating-linear-gradient(45deg,rgba(255,255,255,0.08),rgba(255,255,255,0.08)_4px,transparent_4px,transparent_8px)]" />
                ) : (
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${scoreColor(pct)}`}
                    style={{ width: `${Math.max(2, pct)}%` }}
                  />
                )}
              </div>
            </div>
            <span className="w-14 text-right font-mono text-xs tabular-nums text-slate-400">
              {f.points === null ? "N/A" : `${f.points}/${f.max}`}
              <span className="ml-1 text-slate-600">·{f.weight}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Drilldown({ ticker }: { ticker: string }) {
  const [card, setCard] = useState<GVScorecard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setCard(null);
    setErr(null);
    api
      .gvScorecard(ticker)
      .then((c) => live && setCard(c))
      .catch((e) => live && setErr(e instanceof Error ? e.message : "Failed to load"));
    return () => {
      live = false;
    };
  }, [ticker]);

  if (err) return <p className="text-sm text-rose-300">{err}</p>;
  if (!card) return <p className="text-sm text-slate-400">Loading scorecard…</p>;
  if (!card.available)
    return (
      <div className="space-y-4">
        <p className="text-sm text-amber-300">
          {card.unavailable_reason ?? "No fundamentals available."}
        </p>
        <ThesisEditor ticker={ticker} note={card.note ?? null} />
      </div>
    );

  const m = card.metrics;
  const mt = card.margin_trend;
  const trendColor =
    mt?.direction === "rising"
      ? "text-emerald-300"
      : mt?.direction === "eroding"
        ? "text-rose-300"
        : "text-slate-300";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-xs text-slate-400">
        {m.sector && <span className="chip">{m.sector}</span>}
        {m.industry && <span className="chip">{m.industry}</span>}
        <span className="chip">Price {num(m.price, 2)}</span>
        <span className="chip">P/E {num(m.pe)}</span>
        <span className="chip">Fwd P/E {num(m.forward_pe)}</span>
        <span className="chip">EV/Sales {num(m.ev_sales)}</span>
        <span className="chip">Gross mgn {num(m.gross_margin, 1, "%")}</span>
        <span className="chip">FCF mgn {num(m.fcf_margin, 1, "%")}</span>
        <span className="chip">Rev gth {num(m.revenue_growth_yoy, 1, "%")}</span>
        <span className="chip">ROE {num(m.roe, 1, "%")}</span>
        <span className="chip">D/E {num(m.debt_to_equity, 2)}</span>
      </div>
      {mt && (
        <p className="text-xs text-slate-400">
          Gross-margin trend:{" "}
          <span className={`font-semibold ${trendColor}`}>
            {mt.direction} ({mt.delta_pts > 0 ? "+" : ""}
            {mt.delta_pts} pts
          </span>{" "}
          <span className="font-mono text-slate-500">
            {mt.history.map(([yr, gm]) => `${yr}:${gm}%`).join("  ")}
          </span>{" "}
          — rising/stable margins signal pricing power (moat); eroding signals
          commoditization.
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <div className="mb-3 flex items-center justify-between">
            <span className="section-label mb-0">Growth · {card.growth.coverage_pct}% data</span>
            <span className="grad-text font-mono text-xl font-bold">{card.growth.score}</span>
          </div>
          <FactorBars factors={card.growth.factors} />
        </div>
        <div className="card">
          <div className="mb-3 flex items-center justify-between">
            <span className="section-label mb-0">Value · {card.value.coverage_pct}% data</span>
            <span className="grad-text font-mono text-xl font-bold">{card.value.score}</span>
          </div>
          <FactorBars factors={card.value.factors} />
        </div>
      </div>
      {card.entry_guidance && <EntryGuidance g={card.entry_guidance} />}
      <ThesisEditor ticker={ticker} note={card.note ?? null} />
    </div>
  );
}

const FLAG_STYLE: Record<string, string> = {
  flag: "border-rose-400/40 text-rose-200",
  caution: "border-amber-400/40 text-amber-200",
  note: "border-slate-500/40 text-slate-300",
};

function EntryGuidance({ g }: { g: GVEntryGuidance }) {
  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <span className="section-label mb-0">When to act · what to watch</span>
        <span className="chip">{g.valuation_state}</span>
      </div>

      {/* Data-derived flags */}
      {g.flags.length > 0 && (
        <ul className="space-y-2">
          {g.flags.map((f, i) => (
            <li
              key={i}
              className={`rounded-xl border bg-black/20 px-3 py-2 text-sm ${FLAG_STYLE[f.level] ?? FLAG_STYLE.note}`}
            >
              <span className="mr-1.5 font-semibold uppercase tracking-wide text-xs opacity-70">
                {f.level}
              </span>
              {f.text}
            </li>
          ))}
        </ul>
      )}

      {/* Regime playbooks — general discipline, not a recommendation */}
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          <p className="mb-1 font-semibold text-slate-100">If you judge it a moat compounder</p>
          <p className="text-slate-400">
            Rarely gets cheap. Disciplined entry = reasonable vs its own growth (reverse-DCF / PEG),
            scaled in, added on <em>thesis-intact</em> drawdowns (price falls, moat metrics don&apos;t).
            Expect large interim volatility.
          </p>
          <p className="mt-2 text-rose-200/80">
            Invalidation: gross margin erodes several quarters · growth decelerates with no
            re-acceleration · FCF margin falls · a rival breaks the lock-in.
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          <p className="mb-1 font-semibold text-slate-100">If you judge it a cyclical</p>
          <p className="text-slate-400">
            Buy pessimism, not strength: near the 52-week low, EV/Sales below its own history,
            industry capex being cut, a balance sheet that survives the trough, demand structurally
            intact. <span className="text-amber-200">Avoid</span> when forward P/E looks cheap near
            the highs — that&apos;s peak earnings, the classic trap.
          </p>
          <p className="mt-2 text-rose-200/80">
            Invalidation: demand declining structurally (not cyclically) · leverage forcing
            dilution · no industry supply discipline.
          </p>
        </div>
      </div>

      {/* What to monitor */}
      <div>
        <p className="section-label">Monitor each quarter</p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-400">
          {g.watch.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </div>

      <p className="text-xs italic text-slate-500">{g.disclaimer}</p>
    </div>
  );
}

function ThesisEditor({ ticker, note }: { ticker: string; note: GVNote | null }) {
  const [thesis, setThesis] = useState(note?.thesis ?? "");
  const [risks, setRisks] = useState(note?.risks ?? "");
  const [watch, setWatch] = useState(note?.watch ?? "");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(note?.updated_at ?? null);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const res = await api.saveGvNote(ticker, { thesis, risks, watch });
      setSavedAt(res.updated_at);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const fields: [string, string, string, (v: string) => void, string][] = [
    ["Moat thesis — why a durable advantage exists", thesis, "CUDA ecosystem lock-in; switching costs; scale cost advantage…", setThesis, "thesis"],
    ["What would break it (disconfirming evidence)", risks, "Custom ASICs displace GPUs; commoditization; customer concentration…", setRisks, "risks"],
    ["What to watch", watch, "Gross-margin trend; hyperscaler capex; competitive roadmap…", setWatch, "watch"],
  ];

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <span className="section-label mb-0">Your moat thesis · {ticker}</span>
        <span className="text-xs text-slate-500">
          {savedAt ? `Saved ${new Date(savedAt).toLocaleString()}` : "Not saved yet"}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        The score reads backward-looking margins — it flags a moat&apos;s footprint, it cannot
        certify a future moat. Write the qualitative judgment the number can&apos;t.
      </p>
      {fields.map(([label, value, ph, set, key]) => (
        <label key={key} className="block space-y-1">
          <span className="text-xs text-slate-400">{label}</span>
          <textarea
            className="input min-h-[60px] w-full resize-y"
            placeholder={ph}
            value={value}
            onChange={(e) => set(e.target.value)}
          />
        </label>
      ))}
      {err && <p className="text-sm text-rose-300">{err}</p>}
      <button className="btn-primary" onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save thesis"}
      </button>
    </div>
  );
}

export default function GrowthValuePage() {
  const [snap, setSnap] = useState<GVSnapshot | null>(null);
  const [universe, setUniverse] = useState<GVUniverse | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>("growth");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = async (sb: SortBy = sortBy) => {
    try {
      const [s, u] = await Promise.all([api.growthValue(50, sb), api.gvUniverse()]);
      setSnap(s);
      setUniverse(u);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll while a sweep is running so scores fill in.
  useEffect(() => {
    if (!snap?.scanning) return;
    const t = setInterval(() => load(), 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snap?.scanning, sortBy]);

  const changeSort = (sb: SortBy) => {
    setSortBy(sb);
    load(sb);
  };

  const add = async () => {
    const symbol = input.trim().toUpperCase();
    if (!symbol) return;
    setBusy(true);
    setError(null);
    try {
      await api.addGvSymbol(symbol);
      setInput("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (symbol: string) => {
    try {
      await api.removeGvSymbol(symbol);
      if (open === symbol) setOpen(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    }
  };

  const rows: GVRow[] = snap?.results ?? [];

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="grad-text text-3xl font-extrabold tracking-tight">Growth &amp; Value</h1>
        <p className="max-w-3xl text-sm text-slate-400">
          Long-horizon research scorecards (0–100) built from fundamentals — separate from the
          short-term options signals. <span className="text-slate-300">Growth/Moat</span> rewards
          the durable-compounder fingerprint (high gross margin = pricing power, FCF conversion);{" "}
          <span className="text-slate-300">Value</span> uses EV/Sales so cyclicals stay scoreable
          at a trough when P/E breaks. Research only — not investment advice.
        </p>
      </header>

      {error && (
        <p className="card border-rose-400/40 text-sm text-rose-300">{error}</p>
      )}

      {/* Universe manager */}
      <section className="card space-y-3">
        <span className="section-label">Board universe</span>
        <div className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="Add ticker (e.g. NVDA)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <button className="btn-primary" onClick={add} disabled={busy}>
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {(universe?.symbols ?? []).length === 0 && (
            <span className="text-sm text-slate-500">
              No tickers yet — add a few to build your board.
            </span>
          )}
          {(universe?.symbols ?? []).map((s) => (
            <span key={s.id} className="chip flex items-center gap-2">
              {s.symbol}
              <button
                className="text-slate-500 transition-colors hover:text-rose-300"
                onClick={() => remove(s.symbol)}
                aria-label={`Remove ${s.symbol}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </section>

      {/* Board */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="section-label mb-0">Sort by</span>
            {(["growth", "value"] as SortBy[]).map((sb) => (
              <button
                key={sb}
                onClick={() => changeSort(sb)}
                className={`rounded-xl px-3 py-1 text-sm capitalize transition-colors ${
                  sortBy === sb
                    ? "bg-gradient-to-r from-violet-600/30 to-blue-500/25 text-white shadow-[inset_0_0_0_1px_rgba(139,92,246,0.45)]"
                    : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100"
                }`}
              >
                {sb}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500">
            {snap?.scanning
              ? "Scanning…"
              : snap?.updated_at
                ? `Updated ${new Date(snap.updated_at).toLocaleTimeString()}`
                : ""}
          </span>
        </div>

        {rows.length === 0 ? (
          <p className="card text-sm text-slate-400">
            {snap?.scanning
              ? "Scoring tickers…"
              : "Nothing scored yet. Add tickers above, then scores appear within a few seconds."}
          </p>
        ) : (
          <div className="card overflow-x-auto p-0">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3">Growth / Moat</th>
                  <th className="px-4 py-3">Value</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-right">Rev YoY</th>
                  <th className="px-4 py-3 text-right">Gross mgn</th>
                  <th className="px-4 py-3 text-right">FCF mgn</th>
                  <th className="px-4 py-3 text-right">P/E</th>
                  <th className="px-4 py-3 text-right">EV/S</th>
                  <th className="px-4 py-3 text-right">ROE</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isOpen = open === r.symbol;
                  return (
                    <Fragment key={r.symbol}>
                      <tr
                        onClick={() => setOpen(isOpen ? null : r.symbol)}
                        className="cursor-pointer border-b border-white/5 transition-colors hover:bg-white/[0.04]"
                      >
                        <td className="px-4 py-3 font-mono font-semibold">
                          <span className="mr-1.5 text-slate-500">{isOpen ? "▾" : "▸"}</span>
                          {r.symbol}
                        </td>
                        <td className="px-4 py-3">
                          <ScoreBar score={r.growth_score} />
                        </td>
                        <td className="px-4 py-3">
                          <ScoreBar score={r.value_score} />
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.price, 2)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.revenue_growth_yoy, 1, "%")}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.gross_margin, 1, "%")}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.fcf_margin, 1, "%")}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">{num(r.pe)}</td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.ev_sales)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {num(r.roe, 1, "%")}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className="border-b border-white/10 bg-black/20">
                          <td colSpan={10} className="px-4 py-4">
                            <Drilldown ticker={r.symbol} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
