import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "./api";

// Connection state: "live" (WS), "poll" (fallback), "down".
// Subscribes to /ws for new readings; falls back to 5s polling if the socket
// cannot be established or drops. Either way, `tick` increments to signal
// consumers that fresh data is available.
export function useLiveData() {
  const [conn, setConn] = useState("connecting");
  const [tick, setTick] = useState(0);
  const [lastReading, setLastReading] = useState(null);
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const retryRef = useRef(null);

  const bump = useCallback(() => setTick((t) => t + 1), []);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    setConn((c) => (c === "live" ? c : "poll"));
    pollRef.current = setInterval(bump, 5000);
  }, [bump]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  useEffect(() => {
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (closed) return;
        setConn("live");
        stopPolling();
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "reading") {
            setLastReading(msg.data);
            bump();
          }
        } catch { /* ignore malformed frames */ }
      };
      ws.onclose = () => {
        if (closed) return;
        wsRef.current = null;
        startPolling();          // immediate fallback
        retryRef.current = setTimeout(connect, 8000); // try to upgrade back
      };
      ws.onerror = () => { try { ws.close(); } catch {} };
    };

    connect();
    // Safety net: if WS never opens, polling still drives updates.
    const initial = setTimeout(() => { if (conn !== "live") startPolling(); }, 2000);

    return () => {
      closed = true;
      clearTimeout(initial);
      clearTimeout(retryRef.current);
      stopPolling();
      if (wsRef.current) wsRef.current.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { conn, tick, lastReading };
}

// Convenience hook: re-fetch a function whenever `tick` changes.
export function usePolledData(fn, deps, tick) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let alive = true;
    fn().then((d) => alive && setData(d)).catch((e) => alive && setError(e));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error };
}

export { api };
