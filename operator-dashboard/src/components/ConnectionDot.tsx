import { useOperatorStore } from "../store/operatorStore";

export function ConnectionDot() {
  const connected = useOperatorStore((s) => s.connected);

  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        connected
          ? "bg-accent-capturing animate-dot-pulse"
          : "bg-event-injection"
      }`}
      title={connected ? "Connected" : "Disconnected"}
    />
  );
}
