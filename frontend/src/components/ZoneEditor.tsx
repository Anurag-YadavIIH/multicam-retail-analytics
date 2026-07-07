import { useEffect, useRef, useState } from "react";
import { api, Zone } from "../api/client";

type Point = [number, number]; // normalized [0, 1] - the system-wide zone coordinate convention

interface Draft {
  zoneId: number | null; // null = creating a new zone
  name: string;
  type: string;
  points: Point[];
  closed: boolean;
}

const ZONE_COLORS: Record<string, string> = {
  entrance: "#4ade80",
  exit: "#38bdf8",
  aisle: "#a78bfa",
  shelf: "#f5a623",
  queue: "#f472b6",
  checkout: "#fb923c",
  restricted: "#f87171",
};
const ZONE_TYPES = Object.keys(ZONE_COLORS);
const CLOSE_HIT_RADIUS_PX = 12;

function colorFor(type: string): string {
  return ZONE_COLORS[type] ?? "#94a3b8";
}

function pointsAttr(points: Point[], w: number, h: number): string {
  return points.map(([x, y]) => `${x * w},${y * h}`).join(" ");
}

/** Draw/edit zone polygons over a camera snapshot. Plain SVG, no canvas lib -
 * the viewBox tracks the image's rendered pixel box (via ResizeObserver) so
 * 1 SVG unit = 1 CSS pixel regardless of the camera's aspect ratio; only the
 * pointer-to-normalized conversion on click/drag needs any math. */
export default function ZoneEditor({
  cameraId,
  zones,
  onZonesChanged,
}: {
  cameraId: number;
  zones: Zone[];
  onZonesChanged: () => void;
}) {
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState(false);
  const [imgEl, setImgEl] = useState<HTMLImageElement | null>(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [mousePt, setMousePt] = useState<Point | null>(null);
  const [saveError, setSaveError] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);

  const loadSnapshot = () => {
    setSnapshotError(false);
    api<{ token: string }>(`/cameras/${cameraId}/stream-token`, { method: "POST" })
      .then(({ token }) => setSnapshotUrl(`/api/v1/cameras/${cameraId}/snapshot?token=${token}`))
      .catch(() => setSnapshotError(true));
  };

  useEffect(loadSnapshot, [cameraId]);

  useEffect(() => {
    if (!imgEl) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setImgSize({ w: width, h: height });
    });
    ro.observe(imgEl);
    return () => ro.disconnect();
  }, [imgEl]);

  function normalize(clientX: number, clientY: number): Point {
    const rect = svgRef.current!.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return [x, y];
  }

  function closePolygon() {
    setDraft((d) => d && { ...d, closed: true });
  }

  function startNew() {
    setSaveError("");
    setDraft({ zoneId: null, name: "", type: "aisle", points: [], closed: false });
  }

  function startEdit(zone: Zone) {
    setSaveError("");
    setDraft({
      zoneId: zone.id,
      name: zone.name,
      type: zone.type,
      points: zone.polygon.map(([x, y]) => [x, y]),
      closed: true,
    });
  }

  function handleSvgMouseDown(e: React.MouseEvent) {
    if (!draft || draft.closed) return;
    const pt = normalize(e.clientX, e.clientY);
    if (draft.points.length >= 3) {
      const [fx, fy] = draft.points[0];
      const dx = (pt[0] - fx) * imgSize.w;
      const dy = (pt[1] - fy) * imgSize.h;
      if (Math.hypot(dx, dy) < CLOSE_HIT_RADIUS_PX) {
        closePolygon();
        return;
      }
    }
    setDraft((d) => d && { ...d, points: [...d.points, pt] });
  }

  function handleSvgMouseMove(e: React.MouseEvent) {
    if (!draft || draft.closed) return;
    setMousePt(normalize(e.clientX, e.clientY));
  }

  function handleVertexMouseDown(i: number, e: React.MouseEvent) {
    e.stopPropagation();
    if (!draft) return;
    if (i === 0 && !draft.closed && draft.points.length >= 3) {
      closePolygon();
      return;
    }
    setDragIndex(i);
  }

  // drag tracking on window so the pointer can leave the small vertex handle
  useEffect(() => {
    if (dragIndex === null) return;
    const onMove = (e: MouseEvent) => {
      const pt = normalize(e.clientX, e.clientY);
      setDraft((d) => {
        if (!d) return d;
        const points = [...d.points];
        points[dragIndex] = pt;
        return { ...d, points };
      });
    };
    const onUp = () => setDragIndex(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragIndex]);

  // Enter closes, Escape cancels the draft
  useEffect(() => {
    if (!draft) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !draft.closed && draft.points.length >= 3) {
        closePolygon();
      } else if (e.key === "Escape") {
        setDraft(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [draft]);

  async function handleSave() {
    if (!draft || !draft.closed || draft.points.length < 3 || !draft.name.trim()) return;
    setSaveError("");
    const payload = { name: draft.name.trim(), type: draft.type, polygon: draft.points };
    try {
      if (draft.zoneId === null) {
        await api(`/cameras/${cameraId}/zones`, { method: "POST", body: JSON.stringify(payload) });
      } else {
        await api(`/cameras/${cameraId}/zones/${draft.zoneId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      setDraft(null);
      onZonesChanged();
    } catch (err) {
      setSaveError((err as Error).message);
    }
  }

  async function handleDelete(zoneId: number) {
    await api(`/cameras/${cameraId}/zones/${zoneId}`, { method: "DELETE" });
    if (draft?.zoneId === zoneId) setDraft(null);
    onZonesChanged();
  }

  const canSave = !!draft?.closed && draft.points.length >= 3 && !!draft.name.trim();
  const otherZones = zones.filter((z) => z.id !== draft?.zoneId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {!draft ? (
          <button
            onClick={startNew}
            className="bg-amber text-ink rounded px-3 py-1.5 text-xs font-medium"
          >
            + Add zone
          </button>
        ) : (
          <>
            <input
              value={draft.name}
              onChange={(e) => setDraft((d) => d && { ...d, name: e.target.value })}
              placeholder="Zone name"
              className="bg-ink border border-line rounded px-2 py-1.5 text-sm w-40"
            />
            <select
              value={draft.type}
              onChange={(e) => setDraft((d) => d && { ...d, type: e.target.value })}
              className="bg-ink border border-line rounded px-2 py-1.5 text-sm"
            >
              {ZONE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <button
              onClick={handleSave}
              disabled={!canSave}
              className="bg-amber text-ink rounded px-3 py-1.5 text-xs font-medium disabled:opacity-40"
            >
              Save
            </button>
            <button
              onClick={() => setDraft(null)}
              className="text-slate-400 text-xs hover:underline"
            >
              Cancel (Esc)
            </button>
            {!draft.closed && (
              <span className="label">
                click to add points · click near start / Enter to close
              </span>
            )}
            {saveError && <p className="text-red-400 text-xs w-full">{saveError}</p>}
          </>
        )}
      </div>

      {snapshotError ? (
        <div className="aspect-video rounded border border-line bg-ink flex items-center justify-center text-slate-500 text-sm">
          No snapshot available yet
          <button onClick={loadSnapshot} className="ml-2 text-amber hover:underline">
            retry
          </button>
        </div>
      ) : !snapshotUrl ? (
        <div className="aspect-video rounded border border-line bg-ink flex items-center justify-center text-slate-500 text-sm">
          Loading snapshot…
        </div>
      ) : (
        <div className="relative inline-block max-w-full">
          <img
            ref={setImgEl}
            src={snapshotUrl}
            alt="Camera snapshot"
            className="block max-w-full rounded border border-line"
            onError={() => setSnapshotError(true)}
          />
          {imgSize.w > 0 && (
            <svg
              ref={svgRef}
              viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
              className="absolute inset-0 w-full h-full"
              style={{ cursor: draft && !draft.closed ? "crosshair" : "default" }}
              onMouseDown={handleSvgMouseDown}
              onMouseMove={handleSvgMouseMove}
            >
              {otherZones.map((z) => (
                <polygon
                  key={z.id}
                  points={pointsAttr(z.polygon as Point[], imgSize.w, imgSize.h)}
                  fill={`${colorFor(z.type)}22`}
                  stroke={colorFor(z.type)}
                  strokeWidth={2}
                />
              ))}

              {draft && draft.points.length > 0 && (
                <>
                  {draft.closed ? (
                    <polygon
                      points={pointsAttr(draft.points, imgSize.w, imgSize.h)}
                      fill={`${colorFor(draft.type)}33`}
                      stroke={colorFor(draft.type)}
                      strokeWidth={2}
                    />
                  ) : (
                    <polyline
                      points={pointsAttr(
                        mousePt ? [...draft.points, mousePt] : draft.points,
                        imgSize.w,
                        imgSize.h,
                      )}
                      fill="none"
                      stroke={colorFor(draft.type)}
                      strokeWidth={2}
                      strokeDasharray={mousePt ? "4 4" : undefined}
                    />
                  )}
                  {draft.points.map(([x, y], i) => (
                    <circle
                      key={i}
                      cx={x * imgSize.w}
                      cy={y * imgSize.h}
                      r={6}
                      fill={i === 0 ? "#ffffff" : colorFor(draft.type)}
                      stroke="#000000"
                      strokeWidth={1}
                      style={{ cursor: "grab" }}
                      onMouseDown={(e) => handleVertexMouseDown(i, e)}
                    />
                  ))}
                </>
              )}
            </svg>
          )}
        </div>
      )}

      <ul className="divide-y divide-line text-sm">
        {zones.map((z) => (
          <li key={z.id} className="flex items-center justify-between py-2">
            <span className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ background: colorFor(z.type) }}
              />
              {z.name} <span className="text-slate-500">({z.type})</span>
            </span>
            <span className="flex gap-3">
              <button onClick={() => startEdit(z)} className="text-amber text-xs hover:underline">
                Edit
              </button>
              <button
                onClick={() => handleDelete(z.id)}
                className="text-red-400 text-xs hover:underline"
              >
                Delete
              </button>
            </span>
          </li>
        ))}
        {zones.length === 0 && <li className="text-slate-500 py-2">No zones yet.</li>}
      </ul>
    </div>
  );
}
