import { useEffect, useRef } from "react";
import { useOperatorStore } from "../store/operatorStore";

export function EventStream() {
  const events = useOperatorStore((s) => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events]);

  const getEventColor = (eventType: string) => {
    if (eventType.includes('error') || eventType.includes('fail')) {
      return 'text-arbiter-red';
    }
    if (eventType.includes('warning') || eventType.includes('warn')) {
      return 'text-arbiter-yellow';
    }
    if (eventType.includes('injection') || eventType.includes('defense') || eventType.includes('attack')) {
      return 'text-arbiter-purple';
    }
    return 'text-arbiter-green';
  };

  const formatTimestamp = (ts: number) => {
    // ts is Unix seconds from Python
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="bg-arbiter-surface border border-arbiter-accent-dim rounded-lg p-4 flex-1 overflow-hidden flex flex-col">
      <h2 className="text-lg font-bold text-arbiter-accent mb-3">EVENT STREAM</h2>
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-1 font-mono text-sm">
        {events.length === 0 ? (
          <div className="text-arbiter-muted text-center py-8">No events yet</div>
        ) : (
          events.map((evt) => (
            <div key={evt.id} className="flex gap-3 py-1">
              <span className="text-arbiter-muted shrink-0">
                {formatTimestamp(evt.timestamp)}
              </span>
              <span className={`${getEventColor(evt.event_type)} font-semibold shrink-0`}>
                {evt.event_type}
              </span>
              {evt.data && (
                <span className="text-arbiter-text truncate">
                  {JSON.stringify(evt.data)}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
