"use client";

import { useEffect, useState } from "react";
import AlertCard from "@/components/AlertCard";
import { api, type Alert } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [actionableOnly, setActionableOnly] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .alerts({ actionableOnly })
      .then(setAlerts)
      .catch((e) => setError(e.message));
  }, [actionableOnly]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="grad-text text-3xl font-extrabold tracking-tight">Alert History</h1>
        <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-violet-400/40">
          <input
            type="checkbox"
            checked={actionableOnly}
            onChange={(e) => setActionableOnly(e.target.checked)}
            className="accent-violet-500"
          />
          CALL/PUT only
        </label>
      </div>
      {error && <p className="text-sm text-rose-400">{error}</p>}
      <div className="space-y-3">
        {alerts.length === 0 && (
          <div className="card text-sm text-slate-400">No alerts recorded yet.</div>
        )}
        {alerts.map((a) => (
          <AlertCard key={a.id} alert={a} />
        ))}
      </div>
    </div>
  );
}
