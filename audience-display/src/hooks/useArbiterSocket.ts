import { useEffect, useRef } from "react";
import { useDisplayStore } from "../store/displayStore";
import type { ArbiterMessage } from "../types/messages";

const MAX_BACKOFF_MS = 10_000;

export function useArbiterSocket() {
  const dispatch = useDisplayStore((s) => s.dispatch);
  const setConnected = useDisplayStore((s) => s.setConnected);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);

  useEffect(() => {
    let unmounted = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/ws/display`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        // Request state resync on (re)connect
        ws.send(JSON.stringify({ type: 'request_state' }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "ping") {
            ws.send(JSON.stringify({ type: "pong" }));
            return;
          }
          dispatch(msg as ArbiterMessage);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!unmounted) {
          reconnectTimer = setTimeout(() => {
            backoffRef.current = Math.min(
              backoffRef.current * 2,
              MAX_BACKOFF_MS,
            );
            connect();
          }, backoffRef.current);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [dispatch, setConnected]);
}
