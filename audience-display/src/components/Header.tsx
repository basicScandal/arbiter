import { ConnectionDot } from "./ConnectionDot";

export function Header() {
  return (
    <header className="flex items-center justify-between px-8 py-4 border-b border-arbiter-accent/20">
      <h1 className="text-2xl font-bold tracking-[0.3em] text-arbiter-accent">
        ARBITER
      </h1>
      <ConnectionDot />
    </header>
  );
}
