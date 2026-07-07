import { useEffect, useRef } from "react";
import { useWebSocket } from "../hooks/useWebSocket";

interface Det { class_name: string; confidence: number; bbox: number[]; track_id: number | null; }
interface Frame { camera_id: number; fps: number; detections: Det[]; }

const COLORS: Record<string, string> = {
  person: "#39d0d8", cart: "#f5a623", basket: "#f5a623",
  product: "#a78bfa", staff: "#4ade80",
};

/** Signature element: live wireframe of detections + track IDs on a dark grid.
 *  Renders normalized bboxes streamed over /ws/detections/{id}. */
export default function LiveDetectionCanvas({ cameraId }: { cameraId: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { last, connected } = useWebSocket<Frame>(`/ws/detections/${cameraId}`);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const { width: W, height: H } = canvas;
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#1f2a37";
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    if (!last) return;
    for (const d of last.detections) {
      const [x1, y1, x2, y2] = d.bbox;
      const c = COLORS[d.class_name] ?? "#94a3b8";
      ctx.strokeStyle = c;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x1 * W, y1 * H, (x2 - x1) * W, (y2 - y1) * H);
      ctx.fillStyle = c;
      ctx.font = "11px ui-monospace, monospace";
      const label = d.track_id != null ? `${d.class_name} #${d.track_id}` : d.class_name;
      ctx.fillText(label, x1 * W + 3, Math.max(y1 * H - 4, 10));
    }
    ctx.fillStyle = "#64748b";
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillText(`${last.fps.toFixed(1)} fps`, W - 60, H - 8);
  }, [last]);

  return (
    <div className="relative">
      <canvas ref={canvasRef} width={640} height={360} className="w-full rounded border border-line bg-ink" />
      <span className={`absolute top-2 right-2 text-[10px] font-mono px-2 py-0.5 rounded
        ${connected ? "text-emerald-400 border border-emerald-900" : "text-red-400 border border-red-900"}`}>
        {connected ? "LIVE" : "RECONNECTING"}
      </span>
    </div>
  );
}
