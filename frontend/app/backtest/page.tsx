export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <h1 className="grad-text text-3xl font-extrabold tracking-tight">Backtest</h1>
      <div className="card relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-gradient-to-r before:from-violet-500 before:to-cyan-400">
        <p className="text-sm font-semibold text-violet-300">Phase 3 — coming soon</p>
        <p className="mt-2 text-sm text-slate-400">
          Planned: replay historical snapshots through the scoring engine, track signal
          hit-rate, false-positive rate, and model confidence calibration. Every scan
          already persists ticker + options snapshots, so the data is accumulating now.
        </p>
      </div>
    </div>
  );
}
