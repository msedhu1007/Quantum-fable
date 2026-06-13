"use client";

import { useState } from "react";
import { api, type Research, type Contract } from "@/lib/api";

/* ── Shared small components ───────────────────────────────── */

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="card card-hover !p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 font-mono text-lg text-slate-100">{value ?? "—"}</p>
    </div>
  );
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span className={`inline-block rounded-lg border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${color}`}>
      {text}
    </span>
  );
}

function bullishBearishColor(val: string | undefined) {
  if (!val) return "border-slate-600 text-slate-400";
  if (val.includes("bullish") || val === "oversold" || val === "approaching_oversold")
    return "border-emerald-500/40 bg-emerald-400/10 text-emerald-300";
  if (val.includes("bearish") || val === "overbought" || val === "approaching_overbought")
    return "border-rose-500/40 bg-rose-400/10 text-rose-300";
  return "border-slate-600 bg-white/5 text-slate-400";
}

function Sparkline({ closes, price }: { closes: number[]; price?: number }) {
  const points = price != null ? [...closes, price] : closes;
  if (points.length < 2) return null;
  const w = 800, h = 160, pad = 8;
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
    <svg viewBox={`0 0 ${w} ${h}`} className="h-40 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.3" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L${x(points.length - 1)},${h - pad} L${x(0)},${h - pad} Z`} fill={`url(#${gradId})`} />
      <path d={path} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx={x(points.length - 1)} cy={y(points[points.length - 1])} r="4" fill={stroke} />
    </svg>
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
    <div className="w-full">
      <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full bg-gradient-to-r ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>{score >= 0 ? "bullish" : "bearish"} strength</span>
        <span>alert threshold: ±70</span>
      </div>
    </div>
  );
}

/* ── Interpretation helpers ────────────────────────────────── */

const MA_TEXT: Record<string, string> = {
  bullish_stack: "All MAs aligned bullish (EMA9 > SMA20 > SMA50 > SMA200). Strongest trend configuration — price is above every moving average in perfect order.",
  bearish_stack: "All MAs aligned bearish. Price below every moving average in descending order — strong downtrend.",
  bullish: "Price above all moving averages, though not perfectly stacked. Overall bullish posture.",
  bearish: "Price below all moving averages. Bearish posture — rallies likely to meet resistance at MA levels.",
  mixed: "Mixed MA alignment. Some averages above price, some below — market at an inflection point.",
};

const RSI_TEXT: Record<string, string> = {
  overbought: "RSI above 70 — overbought. Momentum is strong but pullback risk is elevated. Watch for bearish divergence.",
  approaching_overbought: "RSI 60-70 — approaching overbought. Healthy upside momentum, room to run but watch for exhaustion.",
  neutral: "RSI in neutral zone (40-60). No extreme momentum in either direction.",
  approaching_oversold: "RSI 30-40 — approaching oversold. Selling pressure building but may find support soon.",
  oversold: "RSI below 30 — oversold. Selling may be overdone. Watch for bullish divergence and reversal signals.",
};

const BOLL_TEXT: Record<string, string> = {
  above_upper: "Price above upper Bollinger Band — extended. May indicate breakout strength or reversion risk.",
  upper_zone: "Price in upper zone of Bollinger Bands — bullish momentum, trading near the upper range.",
  middle: "Price near the middle band (20-SMA). Neutral positioning within the volatility envelope.",
  lower_zone: "Price in lower zone of Bollinger Bands — bearish pressure, approaching potential support.",
  below_lower: "Price below lower Bollinger Band — oversold by volatility measure. Watch for mean reversion.",
};

const MACD_TEXT: Record<string, string> = {
  bullish: "MACD histogram positive — bullish momentum. Signal line below MACD line confirms upward pressure.",
  bearish: "MACD histogram negative — bearish momentum. Signal line above MACD line suggests continued downward pressure.",
  neutral: "MACD at zero line — momentum equilibrium. Watch for decisive cross in either direction.",
};

function peLabel(pe: number | null | undefined): { text: string; color: string } {
  if (pe == null) return { text: "N/A", color: "text-slate-500" };
  if (pe < 0) return { text: "Negative", color: "text-rose-400" };
  if (pe < 15) return { text: "Cheap", color: "text-emerald-300" };
  if (pe <= 25) return { text: "Fair", color: "text-blue-300" };
  if (pe <= 40) return { text: "Growth premium", color: "text-amber-300" };
  return { text: "Expensive", color: "text-rose-300" };
}

function growthLabel(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "N/A", color: "text-slate-500" };
  if (val > 20) return { text: `${val.toFixed(1)}%`, color: "text-emerald-300" };
  if (val > 10) return { text: `${val.toFixed(1)}%`, color: "text-emerald-400/80" };
  if (val > 0) return { text: `${val.toFixed(1)}%`, color: "text-blue-300" };
  return { text: `${val.toFixed(1)}%`, color: "text-rose-300" };
}

/* ── Section components ────────────────────────────────────── */

function HeroSection({ data, score }: { data: Research["data"]; score: number }) {
  const scoreColor = score >= 70 ? "text-emerald-300" : score <= -70 ? "text-rose-300" : "grad-text";
  const changeColor = (data.change_pct ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300";
  return (
    <div className="card !p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="grad-text font-mono text-5xl font-extrabold">{data.ticker}</h2>
          <div className="mt-2 flex items-baseline gap-4 font-mono">
            <span className="text-3xl font-bold text-slate-100">${data.price?.toFixed(2) ?? "—"}</span>
            {data.change_pct != null && (
              <span className={`text-lg ${changeColor}`}>
                {data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
              </span>
            )}
          </div>
          {data.price_stale && <span className="text-xs text-amber-400">15-min delayed</span>}
        </div>
        <div className="text-right">
          <p className={`font-mono text-4xl font-bold ${scoreColor}`}>{score}</p>
          <p className="text-xs uppercase tracking-wide text-slate-400">signal score</p>
          <div className="mt-2 w-44">
            <ScoreGauge score={score} />
          </div>
        </div>
      </div>
      {data.history_closes && data.history_closes.length > 1 && (
        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
            <span>Last {data.history_closes.length} sessions</span>
          </div>
          <Sparkline closes={data.history_closes} price={data.price} />
        </div>
      )}
    </div>
  );
}

function TechnicalSection({ data }: { data: Research["data"] }) {
  const d = data;
  return (
    <section>
      <h2 className="section-label mb-4 text-base">Technical Analysis</h2>

      {/* Trend */}
      <div className="mb-4 grid gap-4 md:grid-cols-2">
        <div className="card">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200">Trend & Moving Averages</h3>
            {d.ma_alignment && <Badge text={d.ma_alignment.replace("_", " ")} color={bullishBearishColor(d.ma_alignment)} />}
          </div>
          <p className="text-sm leading-relaxed text-slate-400">{MA_TEXT[d.ma_alignment ?? ""] ?? "Insufficient data for MA alignment analysis."}</p>
          {(d.golden_cross || d.death_cross) && (
            <p className={`mt-2 text-sm font-semibold ${d.golden_cross ? "text-emerald-300" : "text-rose-300"}`}>
              {d.golden_cross ? "Golden Cross detected (SMA50 > SMA200)" : "Death Cross detected (SMA50 < SMA200)"}
            </p>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">EMA 9</span>
              <span className="font-mono text-slate-200">{d.ema_9 ?? "—"}</span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">SMA 20</span>
              <span className="font-mono text-slate-200">{d.sma_20 ?? "—"}</span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">SMA 50</span>
              <span className="font-mono text-slate-200">{d.sma_50 ?? "—"}</span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">SMA 200</span>
              <span className="font-mono text-slate-200">{d.sma_200 ?? "—"}</span>
            </div>
          </div>
        </div>

        {/* Momentum */}
        <div className="card">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200">Momentum</h3>
            {d.rsi_signal && <Badge text={d.rsi_signal.replace("_", " ")} color={bullishBearishColor(d.rsi_signal)} />}
          </div>
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-slate-400">RSI (14)</span>
              <span className="font-mono text-slate-200">{d.rsi_14 ?? "—"}</span>
            </div>
            {d.rsi_14 != null && (
              <div className="relative h-2.5 overflow-hidden rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full ${
                    d.rsi_14 >= 70 ? "bg-rose-400" : d.rsi_14 <= 30 ? "bg-emerald-400" : "bg-blue-400"
                  }`}
                  style={{ width: `${d.rsi_14}%` }}
                />
                <div className="absolute top-0 h-full w-px bg-slate-500" style={{ left: "30%" }} />
                <div className="absolute top-0 h-full w-px bg-slate-500" style={{ left: "70%" }} />
              </div>
            )}
            <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{RSI_TEXT[d.rsi_signal ?? ""] ?? ""}</p>
          </div>
          <div className="border-t border-white/5 pt-3">
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-slate-400">MACD</span>
              {d.macd_signal && <Badge text={d.macd_signal} color={bullishBearishColor(d.macd_signal)} />}
            </div>
            {d.macd && (
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-white/5 px-2 py-1 text-center">
                  <span className="text-slate-500">Line</span>
                  <p className="font-mono text-slate-300">{d.macd.macd.toFixed(3)}</p>
                </div>
                <div className="rounded-lg bg-white/5 px-2 py-1 text-center">
                  <span className="text-slate-500">Signal</span>
                  <p className="font-mono text-slate-300">{d.macd.signal.toFixed(3)}</p>
                </div>
                <div className="rounded-lg bg-white/5 px-2 py-1 text-center">
                  <span className="text-slate-500">Histogram</span>
                  <p className={`font-mono ${d.macd.histogram >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                    {d.macd.histogram.toFixed(3)}
                  </p>
                </div>
              </div>
            )}
            <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{MACD_TEXT[d.macd_signal ?? ""] ?? ""}</p>
          </div>
        </div>
      </div>

      {/* Volatility + Support/Resistance */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200">Volatility</h3>
            {d.bollinger_position && (
              <Badge text={d.bollinger_position.replace("_", " ")} color={bullishBearishColor(
                d.bollinger_position === "above_upper" || d.bollinger_position === "upper_zone" ? "bullish" :
                d.bollinger_position === "below_lower" || d.bollinger_position === "lower_zone" ? "bearish" : "neutral"
              )} />
            )}
          </div>
          {d.bollinger && (
            <div className="mb-3 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">BB Upper</span>
                <span className="font-mono text-slate-200">{d.bollinger.upper.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">BB Middle</span>
                <span className="font-mono text-slate-200">{d.bollinger.middle.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">BB Lower</span>
                <span className="font-mono text-slate-200">{d.bollinger.lower.toFixed(2)}</span>
              </div>
            </div>
          )}
          <p className="text-xs leading-relaxed text-slate-500">{BOLL_TEXT[d.bollinger_position ?? ""] ?? ""}</p>
          {d.atr_14 != null && d.price != null && (
            <div className="mt-3 border-t border-white/5 pt-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">ATR (14)</span>
                <span className="font-mono text-slate-200">
                  {d.atr_14.toFixed(2)}{" "}
                  <span className="text-xs text-slate-500">({((d.atr_14 / d.price) * 100).toFixed(1)}% of price)</span>
                </span>
              </div>
            </div>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">20D High</span>
              <span className="font-mono text-slate-200">{d.high_20d ?? "—"}</span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">20D Low</span>
              <span className="font-mono text-slate-200">{d.low_20d ?? "—"}</span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">Breakout</span>
              <span className={`font-mono ${d.breakout ? "text-emerald-300" : "text-slate-400"}`}>
                {d.breakout ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex justify-between rounded-lg bg-white/5 px-3 py-1.5">
              <span className="text-slate-400">Gap %</span>
              <span className="font-mono text-slate-200">{d.gap_pct ?? "—"}</span>
            </div>
          </div>
        </div>

        {/* Support & Resistance */}
        <div className="card">
          <h3 className="mb-3 text-sm font-bold text-slate-200">Key Levels</h3>
          {d.resistance_levels && d.resistance_levels.length > 0 && (
            <div className="mb-4">
              <p className="mb-1.5 text-[11px] uppercase tracking-wider text-rose-400/70">Resistance</p>
              {d.resistance_levels.map((r, i) => (
                <div key={i} className="flex items-center justify-between border-b border-white/5 py-1.5 text-sm last:border-0">
                  <span className="text-slate-400">{r.label}</span>
                  <div className="text-right">
                    <span className="font-mono text-rose-300">{r.level.toFixed(2)}</span>
                    {d.price != null && (
                      <span className="ml-2 text-xs text-slate-500">
                        +{(((r.level - d.price) / d.price) * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="my-2 flex items-center gap-2">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-violet-500/50 to-transparent" />
            <span className="font-mono text-sm font-bold text-violet-300">${d.price?.toFixed(2) ?? "—"}</span>
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-violet-500/50 to-transparent" />
          </div>
          {d.support_levels && d.support_levels.length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] uppercase tracking-wider text-emerald-400/70">Support</p>
              {d.support_levels.map((s, i) => (
                <div key={i} className="flex items-center justify-between border-b border-white/5 py-1.5 text-sm last:border-0">
                  <span className="text-slate-400">{s.label}</span>
                  <div className="text-right">
                    <span className="font-mono text-emerald-300">{s.level.toFixed(2)}</span>
                    {d.price != null && (
                      <span className="ml-2 text-xs text-slate-500">
                        {(((s.level - d.price) / d.price) * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!d.support_levels?.length && !d.resistance_levels?.length && (
            <p className="text-sm text-slate-500">Insufficient data for level analysis.</p>
          )}
        </div>
      </div>

      {/* Technical Verdict */}
      <div className="mt-4 card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-gradient-to-r before:from-violet-500 before:to-cyan-400">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-bold text-slate-200">Technical Verdict</h3>
          {d.technical_rating && (
            <Badge
              text={d.technical_rating.replace("_", " ")}
              color={bullishBearishColor(d.technical_rating)}
            />
          )}
        </div>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          {d.technical_rating === "strong_bullish" && "All technical signals align bullish. Price above all MAs, positive momentum, favorable breakout conditions."}
          {d.technical_rating === "mild_bullish" && "Technical setup leans bullish. Most indicators favor upside but not all conditions are met for a strong signal."}
          {d.technical_rating === "neutral" && "Technical picture is neutral. Mixed signals across momentum, trend, and volatility indicators."}
          {d.technical_rating === "mild_bearish" && "Technical setup leans bearish. Majority of indicators suggest downside risk, though some support levels may hold."}
          {d.technical_rating === "strong_bearish" && "All technical signals align bearish. Price below key MAs, negative momentum, breakdown conditions present."}
          {!d.technical_rating && "Insufficient data for technical rating."}
        </p>
      </div>
    </section>
  );
}

function FundamentalSection({ data }: { data: Research["data"] }) {
  const f = data.fundamentals;
  if (!f) return null;
  const pe = peLabel(f.pe);
  const revGrowth = growthLabel(f.revenue_growth_yoy);
  const epsGrowth = growthLabel(f.eps_growth_yoy);
  const ratingColor = bullishBearishColor(data.fundamental_rating);

  return (
    <section>
      <h2 className="section-label mb-4 text-base">Fundamental Analysis</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {/* Valuation */}
        <div className="card">
          <h3 className="mb-3 text-sm font-bold text-slate-200">Valuation</h3>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">P/E (TTM)</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-200">{f.pe?.toFixed(1) ?? "—"}</span>
                  <span className={`text-xs font-semibold ${pe.color}`}>{pe.text}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">P/S (TTM)</span>
              <span className="font-mono text-slate-200">{f.ps?.toFixed(1) ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Forward P/E</span>
              <span className="font-mono text-slate-200">{(f as Record<string, unknown>).forward_pe != null ? Number((f as Record<string, unknown>).forward_pe).toFixed(1) : "—"}</span>
            </div>
            {f.market_cap != null && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Market Cap</span>
                <span className="font-mono text-slate-200">
                  ${f.market_cap >= 1e6 ? `${(f.market_cap / 1e6).toFixed(1)}T` : f.market_cap >= 1000 ? `${(f.market_cap / 1000).toFixed(1)}B` : `${f.market_cap.toFixed(0)}M`}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Growth */}
        <div className="card">
          <h3 className="mb-3 text-sm font-bold text-slate-200">Growth</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Revenue YoY</span>
              <span className={`font-mono font-semibold ${revGrowth.color}`}>{revGrowth.text}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">EPS YoY</span>
              <span className={`font-mono font-semibold ${epsGrowth.color}`}>{epsGrowth.text}</span>
            </div>
            {data.next_earnings_date && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Next Earnings</span>
                <span className="font-mono text-amber-300">{data.next_earnings_date}</span>
              </div>
            )}
          </div>
        </div>

        {/* Profitability */}
        <div className="card">
          <h3 className="mb-3 text-sm font-bold text-slate-200">Profitability</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Net Margin</span>
              <span className={`font-mono ${(f.net_margin ?? 0) > 15 ? "text-emerald-300" : (f.net_margin ?? 0) > 0 ? "text-blue-300" : "text-rose-300"}`}>
                {f.net_margin != null ? `${f.net_margin.toFixed(1)}%` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">ROE</span>
              <span className={`font-mono ${(f.roe ?? 0) > 15 ? "text-emerald-300" : (f.roe ?? 0) > 0 ? "text-blue-300" : "text-rose-300"}`}>
                {f.roe != null ? `${f.roe.toFixed(1)}%` : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Financial Health */}
        <div className="card">
          <h3 className="mb-3 text-sm font-bold text-slate-200">Financial Health</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Debt / Equity</span>
              <span className={`font-mono ${(f.debt_to_equity ?? 0) > 2 ? "text-rose-300" : "text-slate-200"}`}>
                {f.debt_to_equity != null ? f.debt_to_equity.toFixed(2) : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Beta</span>
              <span className="font-mono text-slate-200">{f.beta?.toFixed(2) ?? "—"}</span>
            </div>
            {f["52w_high"] != null && f["52w_low"] != null && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">52W Range</span>
                <span className="font-mono text-slate-200">
                  {f["52w_low"]!.toFixed(2)} – {f["52w_high"]!.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Fundamental Verdict */}
      <div className="mt-4 card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-gradient-to-r before:from-amber-400 before:to-orange-500">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-bold text-slate-200">Fundamental Verdict</h3>
          {data.fundamental_rating && (
            <Badge text={data.fundamental_rating.replace("_", " ")} color={ratingColor} />
          )}
        </div>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          {data.fundamental_rating === "strong_bullish" && "Strong fundamentals — solid growth, high profitability, and healthy balance sheet. Company is executing well across key metrics."}
          {data.fundamental_rating === "mild_bullish" && "Fundamentals lean positive. Growth or profitability shows strength, though not all metrics are at premium levels."}
          {data.fundamental_rating === "neutral" && "Fundamentals are mixed. Some metrics are positive while others need improvement."}
          {data.fundamental_rating === "mild_bearish" && "Fundamentals lean negative. Growth may be slowing or profitability under pressure."}
          {data.fundamental_rating === "strong_bearish" && "Weak fundamentals — declining growth, margins under pressure, or concerning debt levels."}
          {!data.fundamental_rating && "Fundamental data unavailable for rating."}
        </p>
      </div>
    </section>
  );
}

function OptionsSection({ data }: { data: Research["data"] }) {
  const d = data;
  if (!d.call_volume && !d.put_volume) return null;
  return (
    <section>
      <h2 className="section-label mb-4 text-base">Options Flow</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Call Volume" value={d.call_volume} />
        <Stat label="Put Volume" value={d.put_volume} />
        <Stat label="C/P Ratio" value={d.call_volume_ratio?.toFixed(2)} />
        <Stat label="Chain IV" value={d.chain_mean_iv != null ? `${(d.chain_mean_iv * 100).toFixed(1)}%` : undefined} />
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <ContractCard title="Best CALL Candidate" c={d.best_call} />
        <ContractCard title="Best PUT Candidate" c={d.best_put} />
      </div>
    </section>
  );
}

function ContractCard({ title, c }: { title: string; c: Contract | null | undefined }) {
  const isCall = title.toLowerCase().includes("call");
  return (
    <div className={`card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 ${
      isCall
        ? "before:bg-gradient-to-r before:from-emerald-400 before:to-teal-500"
        : "before:bg-gradient-to-r before:from-rose-400 before:to-pink-500"
    }`}>
      <h3 className={`mb-2 text-sm font-bold ${isCall ? "text-emerald-300" : "text-rose-300"}`}>{title}</h3>
      {!c ? (
        <p className="text-sm text-slate-500">No contract passes liquidity/delta filters.</p>
      ) : (
        <div className="space-y-1 font-mono text-sm text-slate-200">
          <p className="text-base font-bold">
            {c.expiration} {c.strike}{c.option_type === "call" ? "C" : "P"}{" "}
            <span className="text-xs font-normal text-slate-400">({c.dte} DTE)</span>
          </p>
          <p>{"Δ"} {c.delta ?? "—"} · IV {c.iv != null ? `${(c.iv * 100).toFixed(1)}%` : "—"}</p>
          <p>Vol {c.volume ?? "—"} · OI {c.open_interest ?? "—"}</p>
          <p>
            Bid {c.bid} / Ask {c.ask} · Spread{" "}
            <span className={c.spread_pct < 5 ? "text-emerald-300" : "text-amber-300"}>{c.spread_pct}%</span>
          </p>
        </div>
      )}
    </div>
  );
}

function MarketContext({ data, verdict }: { data: Research["data"]; verdict: Research["verdict"] }) {
  return (
    <section>
      <h2 className="section-label mb-4 text-base">Market Context & Signal</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Market Trend" value={data.market_trend} />
        <Stat label="News Sentiment" value={data.news_sentiment != null ? data.news_sentiment.toFixed(2) : undefined} />
        <Stat label="Rel. Volume" value={data.relative_volume?.toFixed(2)} />
        <Stat label="Next Earnings" value={data.next_earnings_date} />
      </div>
      {verdict.decision !== "NO TRADE" && (
        <div className={`mt-3 card border ${
          verdict.decision === "CALL" ? "border-emerald-500/30 bg-emerald-400/5" : "border-rose-500/30 bg-rose-400/5"
        }`}>
          <p className="text-sm text-slate-300">{verdict.message}</p>
        </div>
      )}
    </section>
  );
}

/* ── Main page ─────────────────────────────────────────────── */

export default function AnalysisPage() {
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const [res, setRes] = useState<Research | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function analyze(e: React.FormEvent) {
    e.preventDefault();
    const t = query.trim().toUpperCase();
    if (!t) return;
    setTicker(t);
    setLoading(true);
    setError(null);
    setRes(null);
    api
      .research(t)
      .then(setRes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  return (
    <div className="space-y-8">
      {/* Header + Search */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="grad-text text-3xl font-extrabold tracking-tight">Stock Analysis</h1>
        <form onSubmit={analyze} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter ticker (e.g. NVDA)"
            className="input w-56 font-mono uppercase"
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </form>
      </div>

      {/* Empty state */}
      {!ticker && !loading && (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <span className="text-5xl opacity-30">◎</span>
          <p className="mt-4 text-lg text-slate-300">Enter a ticker to begin analysis</p>
          <p className="mt-1 text-sm text-slate-500">
            Get comprehensive technical and fundamental analysis with interpreted signals
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="card py-16 text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="mt-4 text-sm text-slate-400">Analyzing {ticker}…</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border border-rose-500/30 bg-rose-400/5 text-rose-300">
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Results */}
      {res && (
        <>
          <HeroSection data={res.data} score={res.score} />
          <TechnicalSection data={res.data} />
          <FundamentalSection data={res.data} />
          <OptionsSection data={res.data} />
          <MarketContext data={res.data} verdict={res.verdict} />
        </>
      )}
    </div>
  );
}
