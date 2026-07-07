import { useEffect, useRef, useState } from "react";
import { getToken } from "../api/client";

/** Subscribe to a backend WS channel; auto-reconnects with backoff. */
export function useWebSocket<T>(path: string, onMessage?: (msg: T) => void) {
  const [last, setLast] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let backoff = 1000;
    let alive = true;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}${path}?token=${getToken()}`);
      ws.onopen = () => { setConnected(true); backoff = 1000; };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data) as T;
        setLast(msg);
        handler.current?.(msg);
      };
      ws.onclose = () => {
        setConnected(false);
        if (alive) {
          timer = window.setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, 15000);
        }
      };
    };
    connect();
    const ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
    return () => { alive = false; ws?.close(); clearTimeout(timer); clearInterval(ping); };
  }, [path]);

  return { last, connected };
}
