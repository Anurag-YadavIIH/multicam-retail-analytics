import { FormEvent, useEffect, useState } from "react";
import { api, Camera } from "../api/client";
import CameraStream from "../components/CameraStream";
import ZoneEditor from "../components/ZoneEditor";

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [type, setType] = useState("rtsp");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Camera | null>(null);
  const [panelMode, setPanelMode] = useState<"preview" | "zones">("preview");

  const load = () => api<Camera[]>("/cameras").then((data) => { setCameras(data); return data; }).catch(console.error);
  useEffect(() => { load(); }, []);

  async function refreshSelected(id: number) {
    const data = await load();
    setSelected(data?.find((c) => c.id === id) ?? null);
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/cameras", { method: "POST", body: JSON.stringify({ name, source, type }) });
      setName(""); setSource("");
      load();
    } catch (err) { setError((err as Error).message); }
  }

  async function remove(id: number) {
    await api(`/cameras/${id}`, { method: "DELETE" });
    if (selected?.id === id) setSelected(null);
    load();
  }

  return (
    <div className="space-y-6">
      <form onSubmit={create} className="card flex flex-wrap gap-3 items-end">
        <label>
          <span className="label">Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required
            className="mt-1 block bg-ink border border-line rounded px-3 py-2 text-sm w-44" />
        </label>
        <label className="grow min-w-64">
          <span className="label">Source (RTSP URL / device index / file path)</span>
          <input value={source} onChange={(e) => setSource(e.target.value)} required
            className="mt-1 block w-full bg-ink border border-line rounded px-3 py-2 text-sm" />
        </label>
        <label>
          <span className="label">Type</span>
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="mt-1 block bg-ink border border-line rounded px-3 py-2 text-sm">
            <option value="rtsp">rtsp</option>
            <option value="usb">usb</option>
            <option value="file">file</option>
          </select>
        </label>
        <button className="bg-amber text-ink rounded px-4 py-2 text-sm font-medium">Add camera</button>
        {error && <p className="text-red-400 text-xs w-full">{error}</p>}
      </form>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left label border-b border-line">
              <th className="py-2">Name</th><th>Type</th><th>Status</th>
              <th>FPS</th><th>Zones</th><th>Location</th><th />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {cameras.map((c) => (
              <tr
                key={c.id}
                onClick={() => setSelected(c)}
                className={`cursor-pointer hover:bg-white/5 ${selected?.id === c.id ? "bg-white/5" : ""}`}
              >
                <td className="py-2 font-mono">{c.name}</td>
                <td>{c.type}</td>
                <td>
                  <span className={c.status === "online" ? "text-emerald-400" : "text-slate-500"}>
                    ● {c.status}
                  </span>
                </td>
                <td className="font-mono">{c.measured_fps.toFixed(1)}</td>
                <td>{c.zones.length}</td>
                <td className="text-slate-400">{c.location}</td>
                <td className="text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); remove(c.id); }}
                    className="text-red-400 text-xs hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex gap-4">
              <button
                onClick={() => setPanelMode("preview")}
                className={`label ${panelMode === "preview" ? "text-amber" : ""}`}
              >
                Live preview — {selected.name}
              </button>
              <button
                onClick={() => setPanelMode("zones")}
                className={`label ${panelMode === "zones" ? "text-amber" : ""}`}
              >
                Edit zones
              </button>
            </div>
            <button onClick={() => setSelected(null)} className="text-slate-500 text-xs hover:underline">
              Close
            </button>
          </div>
          {panelMode === "preview" ? (
            <div className="max-w-2xl">
              <CameraStream cameraId={selected.id} />
            </div>
          ) : (
            <ZoneEditor
              cameraId={selected.id}
              zones={selected.zones}
              onZonesChanged={() => refreshSelected(selected.id)}
            />
          )}
        </div>
      )}
    </div>
  );
}
