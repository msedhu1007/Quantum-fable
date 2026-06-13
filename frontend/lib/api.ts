const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Contract {
  symbol?: string;
  description?: string;
  option_type: "call" | "put";
  strike: number;
  expiration: string;
  dte: number;
  delta: number | null;
  iv: number | null;
  volume: number | null;
  open_interest: number | null;
  bid: number | null;
  ask: number | null;
  spread_pct: number;
}

export interface Alert {
  id: number;
  symbol: string;
  created_at: string;
  decision: "CALL" | "PUT" | "NO TRADE";
  score: number;
  confidence: string | null;
  contract: Contract | null;
  reasons: string[] | null;
  risks: string[] | null;
  invalidation_level: string | null;
  message: string | null;
  dispatched: boolean;
}

export interface WatchlistEntry {
  id: number;
  symbol: string;
  enabled: boolean;
  added_at: string;
}

export interface MomentumRow {
  symbol: string;
  momentum_score: number;
  direction: "CALL" | "PUT" | "FLAT";
  price: number | null;
  change_pct: number | null;
  rsi_14: number | null;
  relative_volume: number | null;
  technical_rating: string | null;
  breakout: boolean;
  breakdown: boolean;
  sma_20: number | null;
  sma_50: number | null;
}

export interface MomentumSnapshot {
  updated_at: string | null;
  scanning: boolean;
  using_watchlist_fallback?: boolean;
  results: MomentumRow[];
}

export interface MomentumUniverse {
  symbols: { id: number; symbol: string; added_at: string }[];
  fallback: boolean;
}

export interface GVRow {
  symbol: string;
  growth_score: number;
  value_score: number;
  price: number | null;
  market_cap: number | null;
  pe: number | null;
  ps: number | null;
  revenue_growth_yoy: number | null;
  eps_growth_yoy: number | null;
  net_margin: number | null;
  roe: number | null;
  debt_to_equity: number | null;
}

export interface GVSnapshot {
  updated_at: string | null;
  scanning: boolean;
  sort_by: "growth" | "value";
  results: GVRow[];
}

export interface GVUniverse {
  symbols: { id: number; symbol: string; added_at: string }[];
}

export interface GVFactor {
  key: string;
  label: string;
  value: number | null;
  points: number | null;
  weight: number;
  max: number;
}

export interface GVScore {
  score: number;
  factors: GVFactor[];
  coverage_pct: number;
}

export interface GVScorecard {
  symbol: string;
  available: boolean;
  note?: string;
  growth: GVScore;
  value: GVScore;
  metrics: {
    price?: number | null;
    market_cap?: number | null;
    pe?: number | null;
    ps?: number | null;
    revenue_growth_yoy?: number | null;
    eps_growth_yoy?: number | null;
    net_margin?: number | null;
    operating_margin?: number | null;
    roe?: number | null;
    debt_to_equity?: number | null;
    current_ratio?: number | null;
    beta?: number | null;
    "52w_high"?: number | null;
    "52w_low"?: number | null;
    sector?: string | null;
    industry?: string | null;
  };
}

export interface ScannerStatus {
  last_scan_at: string | null;
  scanned: number;
  calls: number;
  puts: number;
  no_trades: number;
  skipped_reason: string | null;
}

export interface Research {
  data: {
    ticker: string;
    price?: number;
    price_stale?: boolean;
    change_pct?: number;
    volume?: number;
    relative_volume?: number;
    dma_20?: number;
    price_above_20dma?: boolean;
    call_volume?: number;
    put_volume?: number;
    call_volume_ratio?: number;
    chain_mean_iv?: number;
    market_trend?: string;
    news_sentiment?: number | null;
    next_earnings_date?: string;
    ema_9?: number;
    sma_20?: number;
    sma_50?: number;
    sma_200?: number;
    rsi_14?: number;
    atr_14?: number;
    macd?: { macd: number; signal: number; histogram: number };
    bollinger?: { upper: number; middle: number; lower: number };
    high_20d?: number;
    low_20d?: number;
    breakout?: boolean;
    breakdown?: boolean;
    gap_pct?: number;
    history_closes?: number[];
    technical_rating?: string;
    fundamental_rating?: string;
    ma_alignment?: "bullish_stack" | "bearish_stack" | "bullish" | "bearish" | "mixed";
    golden_cross?: boolean;
    death_cross?: boolean;
    rsi_signal?: "overbought" | "approaching_overbought" | "neutral" | "approaching_oversold" | "oversold";
    macd_signal?: "bullish" | "bearish" | "neutral";
    bollinger_position?: "above_upper" | "upper_zone" | "middle" | "lower_zone" | "below_lower";
    support_levels?: { level: number; label: string }[];
    resistance_levels?: { level: number; label: string }[];
    insider_activity?: {
      buys: number;
      sells: number;
      buy_value: number;
      sell_value: number;
      window_days: number;
      source: string;
      recent: {
        name: string | null;
        role: string | null;
        type: "BUY" | "SELL";
        date: string | null;
        shares: number | null;
        price: number | null;
        value: number | null;
      }[];
    } | null;
    congress_activity?: {
      buys: number;
      sells: number;
      total: number;
      source: string;
      lag_note: string;
      recent: {
        name: string | null;
        chamber: string | null;
        party: string | null;
        type: "BUY" | "SELL";
        transaction: string | null;
        range: string | null;
        traded: string | null;
        filed: string | null;
        excess_return_pct: number | null;
      }[];
    } | null;
    fundamentals?: {
      market_cap?: number | null;
      pe?: number | null;
      ps?: number | null;
      revenue_growth_yoy?: number | null;
      eps_growth_yoy?: number | null;
      net_margin?: number | null;
      roe?: number | null;
      debt_to_equity?: number | null;
      beta?: number | null;
      "52w_high"?: number | null;
      "52w_low"?: number | null;
    } | null;
    best_call?: Contract | null;
    best_put?: Contract | null;
    news?: { headline: string; source?: string; url?: string }[];
  };
  score: number;
  verdict: { decision: string; score: number; message: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  health: () =>
    request<{
      status: string;
      market_open: boolean;
      scan_interval_minutes: number;
      scanner: ScannerStatus;
    }>("/health"),
  watchlist: () => request<WatchlistEntry[]>("/watchlist"),
  addSymbol: (symbol: string) =>
    request("/watchlist", { method: "POST", body: JSON.stringify({ symbol }) }),
  removeSymbol: (symbol: string) => request(`/watchlist/${symbol}`, { method: "DELETE" }),
  alerts: (opts?: { actionableOnly?: boolean; symbol?: string }) => {
    const params = new URLSearchParams();
    if (opts?.actionableOnly) params.set("actionable_only", "true");
    if (opts?.symbol) params.set("symbol", opts.symbol);
    return request<Alert[]>(`/alerts?${params}`);
  },
  research: (ticker: string) => request<Research>(`/research/${ticker}`),
  scan: (ticker?: string) =>
    request(ticker ? `/scan/${ticker}` : "/scan", { method: "POST" }),
  momentum: (limit = 20) => request<MomentumSnapshot>(`/momentum?limit=${limit}`),
  refreshMomentum: () => request("/momentum/refresh", { method: "POST" }),
  momentumUniverse: () => request<MomentumUniverse>("/momentum/universe"),
  addMomentumSymbol: (symbol: string) =>
    request("/momentum/universe", { method: "POST", body: JSON.stringify({ symbol }) }),
  removeMomentumSymbol: (symbol: string) =>
    request(`/momentum/universe/${symbol}`, { method: "DELETE" }),
  growthValue: (limit = 50, sortBy: "growth" | "value" = "growth") =>
    request<GVSnapshot>(`/growth-value?limit=${limit}&sort_by=${sortBy}`),
  refreshGrowthValue: () => request("/growth-value/refresh", { method: "POST" }),
  gvUniverse: () => request<GVUniverse>("/growth-value/universe"),
  addGvSymbol: (symbol: string) =>
    request("/growth-value/universe", { method: "POST", body: JSON.stringify({ symbol }) }),
  removeGvSymbol: (symbol: string) =>
    request(`/growth-value/universe/${symbol}`, { method: "DELETE" }),
  gvScorecard: (ticker: string) => request<GVScorecard>(`/growth-value/${ticker}`),
  providers: () =>
    request<{
      market_data_provider: string;
      providers: Record<string, boolean>;
      alert_channels: Record<string, boolean>;
    }>("/providers"),
  settings: () =>
    request<{
      scan_interval_minutes: number;
      market_hours_only: boolean;
      call_score_threshold: number;
      put_score_threshold: number;
      alert_cooldown_minutes: number;
      contract_filters: Record<string, number>;
      default_watchlist: string;
      max_watchlist: number;
      market_benchmark: string;
    }>("/settings"),
};
