import { useEffect, useRef, useCallback } from "react";
import { useOperatorStore } from "../store/operatorStore";
import type { ServerMessage, CommandMessage } from "../types/protocol";

const MAX_BACKOFF_MS = 10_000;

export function useOperatorSocket() {
  const dispatch = useOperatorStore((s) => s.dispatch);
  const setConnectionState = useOperatorStore((s) => s.setConnectionState);
  const setSendCommand = useOperatorStore((s) => s.setSendCommand);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);

  const sendCommand = useCallback((action: string, params?: Record<string, string>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const msg: CommandMessage = { type: 'command', action, ...params };
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    setSendCommand(sendCommand);
  }, [sendCommand, setSendCommand]);

  useEffect(() => {
    let unmounted = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // In dev, Vite proxy can be unreliable for WS — connect to backend directly
      const host = import.meta.env.DEV ? "localhost:8080" : window.location.host;
      const url = `${protocol}//${host}/ws/operator`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        backoffRef.current = 1000;
      };

      ws.onmessage = (event) => {
        try {
          const msg: ServerMessage = JSON.parse(event.data);
          dispatch(msg);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnectionState('reconnecting');
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
  }, [dispatch, setConnectionState]);
}
