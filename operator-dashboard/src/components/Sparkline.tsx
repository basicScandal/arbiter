import { useMemo } from "react";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  glowColor?: string;
}

export function Sparkline({
  data,
  width = 240,
  height = 32,
  color = "var(--accent, #5588aa)",
  glowColor = "var(--glow, rgba(85, 136, 170, 0.3))",
}: SparklineProps) {
  const path = useMemo(() => {
    if (data.length < 2) return "";
    const max = Math.max(...data, 1);
    const step = width / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * step;
      const y = height - (v / max) * (height - 4) - 2;
      return `${x},${y}`;
    });
    return `M${points.join(" L")}`;
  }, [data, width, height]);

  const areaPath = useMemo(() => {
    if (data.length < 2) return "";
    return `${path} L${width},${height} L0,${height} Z`;
  }, [path, width, height, data.length]);

  if (data.length < 2) {
    return (
      <svg width={width} height={height} className="opacity-30">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke={color} strokeWidth={1} strokeDasharray="4 4" opacity={0.3} />
      </svg>
    );
  }

  return (
    <svg width={width} height={height}>
      <defs>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.2} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
        <filter id="sparkGlow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path d={areaPath} fill="url(#sparkFill)" />
      <path d={path} fill="none" stroke={color} strokeWidth={1.5}
        filter="url(#sparkGlow)" strokeLinecap="round" strokeLinejoin="round" />
      {/* Current value dot */}
      {data.length > 0 && (
        <circle
          cx={width}
          cy={height - (data[data.length - 1] / Math.max(...data, 1)) * (height - 4) - 2}
          r={2.5}
          fill={color}
          style={{ filter: `drop-shadow(0 0 4px ${glowColor})` }}
        />
      )}
    </svg>
  );
}
