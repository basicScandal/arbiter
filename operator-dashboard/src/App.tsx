import { useOperatorSocket } from "./hooks/useOperatorSocket";
import { Header } from "./components/Header";
import { CommandBar } from "./components/CommandBar";
import { StatusPanel } from "./panels/StatusPanel";
import { EventStream } from "./panels/EventStream";
import { CountersPanel } from "./panels/CountersPanel";
import { DefensePanel } from "./panels/DefensePanel";
import { ScorePanel } from "./panels/ScorePanel";

export default function App() {
  useOperatorSocket();

  return (
    <div className="flex flex-col h-screen bg-arbiter-bg font-mono">
      <Header />
      <main className="flex-1 grid grid-cols-3 gap-4 p-4 overflow-hidden">
        <div className="col-span-2 flex flex-col gap-4">
          <StatusPanel />
          <EventStream />
        </div>
        <div className="flex flex-col gap-4">
          <CountersPanel />
          <DefensePanel />
          <ScorePanel />
        </div>
      </main>
      <CommandBar />
    </div>
  );
}
