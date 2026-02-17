import { ConnectionDot } from "./ConnectionDot";

export function Header() {
  return (
    <header className="flex items-center justify-between px-10 py-5 border-b border-arbiter-accent/20">
      <h1 className="text-3xl font-bold tracking-[0.3em] text-arbiter-accent">
        ARBITER
      </h1>
      <ConnectionDot />
    </header>
  );
}
