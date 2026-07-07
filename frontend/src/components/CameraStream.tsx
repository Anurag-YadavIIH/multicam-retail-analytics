import { useEffect, useRef, useState } from "react";
import { api, getToken } from "../api/client";

const POLL_INTERVAL_MS = 5000;

interface StreamToken {
  token: string;
  expires_in: number;
}

/** Live MJPEG preview for a camera, backed by the Redis frame cache the vision
 * worker fills (~2-3 FPS). Polls /snapshot (full access token, header auth) to
 * detect online/offline before opening the long-lived /stream connection, so
 * an offline camera never holds a dangling connection open on the backend.
 * The <img src> can't set an Authorization header, so it uses a ~60s
 * camera-scoped stream token instead of the full access token - a fresh one
 * is fetched right before every (re)connect, never reused across connects. */
export default function CameraStream({ cameraId }: { cameraId: number }) {
  const [online, setOnline] = useState<boolean | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const wasOnline = useRef(false);

  const openStream = async () => {
    const { token } = await api<StreamToken>(`/cameras/${cameraId}/stream-token`, {
      method: "POST",
    });
    setStreamUrl(`/api/v1/cameras/${cameraId}/stream?token=${token}`);
  };

  const handleStreamError = () => {
    openStream().catch(() => {
      setOnline(false);
      setStreamUrl(null);
    });
  };

  useEffect(() => {
    let cancelled = false;
    let timer: number;

    const poll = async () => {
      let ok = false;
      try {
        const res = await fetch(`/api/v1/cameras/${cameraId}/snapshot`, {
          headers: { Authorization: `Bearer ${getToken() ?? ""}` },
        });
        ok = res.ok;
      } catch {
        ok = false;
      }
      if (cancelled) return;
      setOnline(ok);
      if (ok && !wasOnline.current) {
        try {
          await openStream();
        } catch {
          setStreamUrl(null);
        }
      }
      wasOnline.current = ok;
      if (!cancelled) timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [cameraId]);

  return (
    <div className="relative aspect-video rounded border border-line bg-ink overflow-hidden flex items-center justify-center">
      {online && streamUrl ? (
        <img
          key={streamUrl}
          src={streamUrl}
          alt="Live camera preview"
          className="w-full h-full object-contain"
          onError={handleStreamError}
        />
      ) : (
        <div className="text-center text-slate-500 text-sm">
          <div className="text-2xl mb-1">&#9678;</div>
          {online === null ? "Connecting…" : "Camera offline"}
        </div>
      )}
      <span
        className={`absolute top-2 right-2 text-[10px] font-mono px-2 py-0.5 rounded border ${
          online
            ? "text-emerald-400 border-emerald-900"
            : "text-red-400 border-red-900"
        }`}
      >
        {online ? "LIVE" : "OFFLINE"}
      </span>
    </div>
  );
}
