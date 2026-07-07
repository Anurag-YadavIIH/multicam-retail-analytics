import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { api, Camera, Overview, TrafficPoint, Alert } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import LiveDetectionCanvas from "../components/LiveDetectionCanvas";

function Stat({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="kpi mt-1">{value}<span className="text-sm text-slate-500 ml-1">{unit}</span></div>
    </div>
  );
}

export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [traffic, setTraffic] = useState<TrafficPoint[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [liveAlerts, setLiveAlerts] = useState<Alert[]>([]);

  useWebSocket<Alert>("/ws/alerts", (a) => setLiveAlerts((prev) => [a, ...prev].slice(0, 8)));

  useEffect(() => {
    const load = () => {
      api<Overview>("/analytics/overview").then(setOverview).catch(console.error);
      api<TrafficPoint[]>("/analytics/traffic?hours=24").then(setTraffic).catch(console.error);
    };
    load();
    api<Camera[]>("/cameras").then((cams) => {
      setCameras(cams);
      if (cams.length && selected === null) setSelected(cams[0].id);
    }).catch(console.error);
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const chart = traffic.map((p) => ({
    time: new Date(p.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    count: p.count,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Stat label="Visitors today" value={overview?.total_visitors_today ?? "–"} />
        <Stat label="In store now" value={overview?.current_occupancy ?? "–"} />
        <Stat label="Avg dwell" value={overview ? (overview.avg_dwell_s / 60).toFixed(1) : "–"} unit="min" />
        <Stat label="Max queue" value={overview?.max_queue_length ?? "–"} />
        <Stat label="Cameras online" value={overview?.active_cameras ?? "–"} />
        <Stat label="Open alerts" value={overview?.open_alerts ?? "–"} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="label">Live detections</span>
            <select
              className="bg-ink border border-line rounded px-2 py-1 text-xs"
              value={selected ?? ""}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          {selected !== null && <LiveDetectionCanvas cameraId={selected} />}
        </div>

        <div className="card">
          <span className="label">Traffic - last 24h</span>
          <div className="h-72 mt-3">
            <ResponsiveContainer>
              <LineChart data={chart}>
                <CartesianGrid stroke="#1f2a37" />
                <XAxis dataKey="time" stroke="#64748b" fontSize={11} minTickGap={40} />
                <YAxis stroke="#64748b" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #1f2a37" }} />
                <Line type="monotone" dataKey="count" stroke="#39d0d8" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card">
        <span className="label">Live alert feed</span>
        {liveAlerts.length === 0 ? (
          <p className="text-slate-500 text-sm mt-2">No alerts in this session. Thresholds are configured in configs/app.yaml.</p>
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {liveAlerts.map((a, i) => (
              <li key={i} className="py-2 text-sm flex gap-3">
                <span className={a.severity === "critical" ? "text-red-400" : "text-amber"}>
                  {a.severity.toUpperCase()}
                </span>
                <span className="text-slate-300">{a.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
