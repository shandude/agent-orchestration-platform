import { useEffect, useRef, useState } from "react";

export interface MonitorEvent {
  type: string;
  run_id?: string | null;
  level?: string;
  message?: string;
  data?: Record<string, any>;
  ts?: string;
}

/**
 * Subscribe to the backend monitoring WebSocket. Auto-reconnects on drop so the
 * live feed survives backend restarts during a demo.
 */
export function useMonitor(max = 500) {
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/monitor`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!stop) retry = setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const data = JSON.parse(ev.data) as MonitorEvent;
        if (data.type === "ping" || data.type === "connected") return;
        setEvents((prev) => [...prev.slice(-(max - 1)), data]);
      };
    };
    connect();

    return () => {
      stop = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [max]);

  return { events, connected, clear: () => setEvents([]) };
}
