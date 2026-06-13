"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Research, type Contract } from "@/lib/api";

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="card card-hover !p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 font-mono text-lg text-slate-100">{value ?? "—"}</p>
    </div>
  );
}

function Rating({ value }: { value?: string }) {
  if (!value) return <>—</>;
  const color = value.includes("bullish")
    ? "text-emerald-400"
    : value.includes("bearish")
      ? "text-rose-400"
      : "text-slate-400";
  return <span className={`${color} text-sm`}>{value.replace("_", " ")}</span>;
}

function Sparkline({ closes, price }: { closes: number[]; price?: number }) {
  const points = price != null ? [...closes, price] : closes;
  if (points.length < 2) return null;
  const w = 800;
  const h = 180;
  const pad = 8;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const x = (i: number) => pad + (i / (points.length - 1)) * (w - pad * 2);
  const y = (v: number) => h - pad - ((v - min) / range) * (h - pad * 2);
  const path = points.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const up = points[points.length - 1] >= points[0];
  const stroke = up ? "#34d399" : "#fb7185";
  const gradId = up ? "spark-up" : "spark-down";
  return (
    <div className="card !p-3">
      <div className="mb-1 flex items-center justify-between px-1">
        <span className="text-xs uppercase tracking-wide text-slate-400">
          Last {closes.length} sessions
        </span>
        <span className={`font-mono text-xs ${up ? "text-emerald-300" : "text-rose-300"}`}>
          {min.toFixed(2)} – {max.toFixed(2)}
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-44 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L${x(points.length - 1)},${h - pad} L${x(0)},${h - pad} Z`} fill={`url(#${gradId})`} />
        <path d={path} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinejoin="round" />
        <circle cx={x(points.length - 1)} cy={y(points[points.length - 1])} r="4" fill={stroke} />
      </svg>
    </div>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const pct = Math.min(Math.abs(score), 100);
  const color =
    score >= 70 ? "from-emerald-400 to-teal-400"
    : score <= -70 ? "from-rose-400 to-pink-400"
    : score >= 0 ? "from-violet-500 to-blue-400"
    : "from-amber-400 to-rose-400";
  return (
    <div className="mt-2 w-44">
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>{score >= 0 ? "bullish" : "bearish"} strength</span>
        <span>±70 alert</span>
      </div>
    </div>
  );
}

function ContractCard({ title, c }: { title: string; c: Contract | null | undefined }) {
  const isCall = title.toLowerCase().includes("call");
  return (
    <div
      className={`card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 ${
        isCall
          ? "before:bg-gradient-to-r before:from-emerald-400 before:to-teal-500"
          : "before:bg-gradient-to-r before:from-rose-400 before:to-pink-500"
      }`}
    >
      <h3 className={`mb-2 text-sm font-bold ${isCall ? "text-emerald-300" : "text-rose-300"}`}>
        {title}
      </h3>
      {!c ? (
        <p className="text-sm text-slate-500">No contract passes liquidity/delta filters.</p>
      ) : (
        <div className="space-y-1 font-mono text-sm text-slate-200">
          <p className="text-base font-bold">
            {c.expiration} {c.strike}
            {c.option_type === "call" ? "C" : "P"}{" "}
            <span className="text-xs font-normal text-slate-400">({c.dte} DTE)</span>
          </p>
          <p>Δ {c.delta ?? "—"} · IV {c.iv != null ? `${(c.iv * 100).toFixed(1)}%` : "—"}</p>
          <p>Vol {c.volume ?? "—"} · OI {c.open_interest ?? "—"}</p>
          <p>
            Bid {c.bid} / Ask {c.ask} · Spread{" "}
            <span className={c.spread_pct < 5 ? "text-emerald-300" : "text-amber-300"}>
              {c.spread_pct}%
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

export default function ResearchPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = (params?.ticker ?? "").toUpperCase();
  const [res, setRes] = useState<Research | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    api
      .research(ticker)
      .then(setRes)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <p className="text-slate-400">Loading {ticker}…</p>;
  if (error) return <p className="text-rose-400">{error}</p>;
  if (!res) return null;

  const d = res.data;
  const scoreColor =
    res.score >= 70 ? "text-emerald-300" : res.score <= -70 ? "text-rose-300" : "grad-text";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="grad-text font-mono text-4xl font-extrabold">{ticker}</h1>
        <div className="card !px-5 !py-3 text-right">
          <p className={`font-mono text-3xl font-bold ${scoreColor}`}>{res.score}</p>
          <p className="text-xs uppercase tracking-wide text-slate-400">signal score</p>
          <ScoreGauge score={res.score} />
        </div>
      </div>

      {d.history_closes && d.history_closes.length > 1 && (
        <Sparkline closes={d.history_closes} price={d.price} />
      )}

      <p className="card text-sm text-slate-300">
        {res.verdict.decision !== "NO TRADE" ? `⚡ ${res.verdict.decision} candidate — ` : ""}
        {res.verdict.message}
      </p>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label={d.price_stale ? "Price (15-min delayed)" : "Price"}
          value={d.price}
        />
        <Stat label="Change %" value={d.change_pct} />
        <Stat label="Rel. volume" value={d.relative_volume} />
        <Stat label="Technical rating" value={<Rating value={d.technical_rating} />} />
        <Stat label="Call vol" value={d.call_volume} />
        <Stat label="Put vol" value={d.put_volume} />
        <Stat label="C/P ratio" value={d.call_volume_ratio} />
        <Stat
          label="Chain IV"
          value={d.chain_mean_iv != null ? `${(d.chain_mean_iv * 100).toFixed(1)}%` : undefined}
        />
        <Stat label="Market trend" value={d.market_trend} />
        <Stat
          label="News sentiment"
          value={d.news_sentiment != null ? d.news_sentiment.toFixed(2) : undefined}
        />
        <Stat label="Next earnings" value={d.next_earnings_date} />
        <Stat label="Fundamental rating" value={<Rating value={d.fundamental_rating} />} />
      </div>

      <section>
        <h2 className="section-label">Technicals</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="EMA 9" value={d.ema_9} />
          <Stat label="SMA 20" value={d.sma_20} />
          <Stat label="SMA 50" value={d.sma_50} />
          <Stat label="SMA 200" value={d.sma_200} />
          <Stat label="RSI 14" value={d.rsi_14} />
          <Stat label="ATR 14" value={d.atr_14} />
          <Stat
            label="MACD hist"
            value={d.macd ? d.macd.histogram.toFixed(3) : undefined}
          />
          <Stat
            label="Bollinger"
            value={d.bollinger ? `${d.bollinger.lower} – ${d.bollinger.upper}` : undefined}
          />
          <Stat label="20d high" value={d.high_20d} />
          <Stat label="20d low" value={d.low_20d} />
          <Stat
            label="Breakout / down"
            value={d.breakout ? "breakout ↑" : d.breakdown ? "breakdown ↓" : "no"}
          />
          <Stat label="Gap %" value={d.gap_pct} />
        </div>
      </section>

      {d.fundamentals && (
        <section>
          <h2 className="section-label">Fundamentals</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Market cap"
              value={d.fundamentals.market_cap != null ? `$${(d.fundamentals.market_cap / 1000).toFixed(1)}B` : undefined}
            />
            <Stat label="P/E (TTM)" value={d.fundamentals.pe?.toFixed(1)} />
            <Stat label="P/S (TTM)" value={d.fundamentals.ps?.toFixed(1)} />
            <Stat
              label="Rev growth YoY"
              value={d.fundamentals.revenue_growth_yoy != null ? `${d.fundamentals.revenue_growth_yoy.toFixed(1)}%` : undefined}
            />
            <Stat
              label="EPS growth YoY"
              value={d.fundamentals.eps_growth_yoy != null ? `${d.fundamentals.eps_growth_yoy.toFixed(1)}%` : undefined}
            />
            <Stat
              label="Net margin"
              value={d.fundamentals.net_margin != null ? `${d.fundamentals.net_margin.toFixed(1)}%` : undefined}
            />
            <Stat
              label="ROE"
              value={d.fundamentals.roe != null ? `${d.fundamentals.roe.toFixed(1)}%` : undefined}
            />
            <Stat label="Beta" value={d.fundamentals.beta?.toFixed(2)} />
          </div>
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <ContractCard title="Best CALL candidate" c={d.best_call} />
        <ContractCard title="Best PUT candidate" c={d.best_put} />
      </div>

      {d.insider_activity && (
        <section>
          <h2 className="section-label">
            Insider activity — {d.insider_activity.source} (last {d.insider_activity.window_days}d)
          </h2>
          <div className="card !p-0">
            <div className="flex gap-6 border-b border-white/5 px-4 py-3 text-sm">
              <span className="text-emerald-300">
                {d.insider_activity.buys} buys · ${d.insider_activity.buy_value.toLocaleString()}
              </span>
              <span className="text-rose-300">
                {d.insider_activity.sells} sells · ${d.insider_activity.sell_value.toLocaleString()}
              </span>
            </div>
            {d.insider_activity.recent.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">
                No open-market insider transactions found in the window.
              </p>
            ) : (
              d.insider_activity.recent.map((t, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/5 px-4 py-2 text-sm first:border-t-0"
                >
                  <span
                    className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
                      t.type === "BUY"
                        ? "bg-emerald-400/15 text-emerald-300"
                        : "bg-rose-400/15 text-rose-300"
                    }`}
                  >
                    {t.type}
                  </span>
                  <span className="font-mono text-xs text-slate-400">{t.date}</span>
                  <span className="font-medium text-slate-200">{t.name ?? "—"}</span>
                  {t.role && <span className="text-xs text-slate-500">{t.role}</span>}
                  <span className="ml-auto font-mono text-xs text-slate-300">
                    {t.shares != null ? `${t.shares.toLocaleString()} sh` : "—"}
                    {t.price != null ? ` @ ${t.price}` : ""}
                    {t.value != null ? ` · $${t.value.toLocaleString()}` : ""}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {d.congress_activity && d.congress_activity.total > 0 && (
        <section>
          <h2 className="section-label">Congress trading — {d.congress_activity.source}</h2>
          <div className="card !p-0">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-white/5 px-4 py-3 text-sm">
              <span className="text-emerald-300">{d.congress_activity.buys} buys</span>
              <span className="text-rose-300">{d.congress_activity.sells} sells</span>
              <span className="text-xs text-slate-500">⚠ {d.congress_activity.lag_note}</span>
            </div>
            {d.congress_activity.recent.map((t, i) => (
              <div
                key={i}
                className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/5 px-4 py-2 text-sm first:border-t-0"
              >
                <span
                  className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
                    t.type === "BUY"
                      ? "bg-emerald-400/15 text-emerald-300"
                      : "bg-rose-400/15 text-rose-300"
                  }`}
                >
                  {t.type}
                </span>
                <span className="font-medium text-slate-200">{t.name ?? "—"}</span>
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

      {d.news && d.news.length > 0 && (
        <section>
          <h2 className="section-label">Recent news</h2>
          <ul className="space-y-2">
            {d.news.map((n, i) => (
              <li key={i} className="card card-hover !p-3 text-sm">
                <a href={n.url} target="_blank" rel="noreferrer" className="transition-colors hover:text-cyan-300">
                  {n.headline}
                </a>
                {n.source && <span className="ml-2 text-xs text-slate-500">{n.source}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
