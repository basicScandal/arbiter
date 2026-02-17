import { useOperatorStore } from "../store/operatorStore";

export function ConnectionDot() {
  const connectionState = useOperatorStore((s) => s.connectionState);

  const dotClass = {
    connected: "bg-accent-capturing animate-dot-pulse",
    connecting: "bg-text-dim animate-pulse",
    reconnecting: "bg-event-injection animate-pulse",
  }[connectionState];

  const label = {
    connected: "Connected",
    connecting: "Connecting...",
    reconnecting: "Reconnecting...",
  }[connectionState];

  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${dotClass}`}
      title={label}
    />
  );
}
