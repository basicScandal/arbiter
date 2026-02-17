import { useOperatorStore } from "../store/operatorStore";

export function ConnectionDot() {
  const connected = useOperatorStore((s) => s.connected);

  return (
    <span
      className={`inline-block w-3.5 h-3.5 rounded-full ${
        connected
          ? "bg-arbiter-green animate-dot-pulse"
          : "bg-arbiter-red"
      }`}
      title={connected ? "Connected" : "Disconnected"}
    />
  );
}
