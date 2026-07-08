import { useEffect, useState } from "react";
import { api, Camera, Identity, IdentityJourney } from "../api/client";

export default function Identities() {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [journey, setJourney] = useState<IdentityJourney | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Identity[]>("/reid/identities").then(setIdentities).catch(console.error);
    api<Camera[]>("/cameras").then(setCameras).catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setJourney(null);
      return;
    }
    setError("");
    api<IdentityJourney>(`/reid/identities/${selectedId}/journey`)
      .then(setJourney)
      .catch((err) => setError((err as Error).message));
  }, [selectedId]);

  const cameraName = (id: number) => cameras.find((c) => c.id === id)?.name ?? `camera ${id}`;

  return (
    <div className="space-y-6">
      <div className="card overflow-x-auto">
        <div className="label mb-3">
          Recently re-identified visitors — matched more than once, same-camera or cross-camera
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left label border-b border-line">
              <th className="py-2">Identity</th>
              <th>First seen</th>
              <th>Last seen</th>
              <th>Sightings</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {identities.map((i) => (
              <tr
                key={i.id}
                onClick={() => setSelectedId(i.id)}
                className={`cursor-pointer hover:bg-white/5 ${selectedId === i.id ? "bg-white/5" : ""}`}
              >
                <td className="py-2 font-mono">#{i.id}</td>
                <td className="text-slate-400">{new Date(i.first_seen).toLocaleString()}</td>
                <td className="text-slate-400">{new Date(i.last_seen).toLocaleString()}</td>
                <td className="font-mono">{i.track_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {identities.length === 0 && (
          <p className="text-slate-500 text-sm py-4">
            No one has been re-identified yet — an identity shows up here once the same person is
            matched across two or more tracks.
          </p>
        )}
      </div>

      {selectedId !== null && (
        <div className="card overflow-x-auto">
          <div className="flex items-center justify-between mb-3">
            <span className="label">Journey — identity #{selectedId}</span>
            <button
              onClick={() => setSelectedId(null)}
              className="text-slate-500 text-xs hover:underline"
            >
              Close
            </button>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          {journey && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left label border-b border-line">
                  <th className="py-2">Camera</th>
                  <th>Zones visited</th>
                  <th>First seen</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {journey.tracks.map((t) => (
                  <tr key={`${t.camera_id}-${t.track_id}`}>
                    <td className="py-2 font-mono">{cameraName(t.camera_id)}</td>
                    <td className="text-slate-400">{t.zones_visited.join(", ") || "—"}</td>
                    <td className="text-slate-400">{new Date(t.first_seen).toLocaleString()}</td>
                    <td className="text-slate-400">{new Date(t.last_seen).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
