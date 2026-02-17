interface StateIndicatorProps {
  state: 'idle' | 'capturing' | 'paused' | 'stopped';
}

export function StateIndicator({ state }: StateIndicatorProps) {
  const colorMap = {
    idle: 'bg-arbiter-green',
    capturing: 'bg-arbiter-cyan',
    paused: 'bg-arbiter-yellow',
    stopped: 'bg-arbiter-red',
  };

  return (
    <span
      className={`inline-block w-4 h-4 rounded-full ${colorMap[state]}`}
      title={`State: ${state}`}
    />
  );
}
