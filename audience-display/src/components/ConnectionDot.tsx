import { useDisplayStore } from "../store/displayStore";

export function ConnectionDot() {
  const connected = useDisplayStore((s) => s.connected);

  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${
        connected
          ? "bg-arbiter-green animate-dot-pulse"
          : "bg-arbiter-red"
      }`}
      title={connected ? "Connected" : "Disconnected"}
    />
  );
}
