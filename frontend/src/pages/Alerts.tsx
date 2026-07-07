import { useEffect, useState } from "react";
import { api, Alert } from "../api/client";

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [onlyOpen, setOnlyOpen] = useState(false);

  const load = () =>
    api<Alert[]>(`/alerts?hours=168&unacknowledged_only=${onlyOpen}`)
      .then(setAlerts).catch(console.error);
  useEffect(() => { load(); }, [onlyOpen]);

  async function ack(id: number) {
    await api(`/alerts/${id}/ack`, { method: "POST" });
    load();
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <span className="label">Alerts - last 7 days</span>
        <label className="text-xs text-slate-400 flex items-center gap-2">
          <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
          Unacknowledged only
        </label>
      </div>
      <ul className="divide-y divide-line">
        {alerts.map((a) => (
          <li key={a.id} className="py-2 flex items-center gap-4 text-sm">
            <span className={`w-20 shrink-0 ${a.severity === "critical" ? "text-red-400" : "text-amber"}`}>
              {a.severity.toUpperCase()}
            </span>
            <span className="w-32 shrink-0 font-mono text-slate-400">{a.type}</span>
            <span className="grow text-slate-300">{a.message}</span>
            <span className="text-xs text-slate-500">{new Date(a.ts).toLocaleString()}</span>
            {!a.acknowledged && (
              <button onClick={() => ack(a.id)} className="text-signal text-xs hover:underline">
                Acknowledge
              </button>
            )}
          </li>
        ))}
        {alerts.length === 0 && <p className="text-slate-500 text-sm py-4">No alerts in this window.</p>}
      </ul>
    </div>
  );
}
