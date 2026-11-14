"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDate, formatLatency, formatNumber, formatPercent } from "@/lib/format";
import type { Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const AXIS = { stroke: "#4A5451", fontSize: 10, tickLine: false, axisLine: false } as const;

function TooltipShell({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-ink-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      {label ? <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-chalk-500">{label}</p> : null}
      {children}
    </div>
  );
}

export function GrowthChart({
  data,
  language,
  height = 190,
}: {
  data: Array<{ date: string; added: number; cumulative: number }>;
  language: Language;
  height?: number;
}) {
  const hasData = data.some((point) => point.cumulative > 0 || point.added > 0);
  if (!hasData) return <ChartEmpty height={height} />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="growthFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#9DFF00" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#9DFF00" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.045)" vertical={false} />
        <XAxis
          dataKey="date"
          {...AXIS}
          minTickGap={28}
          tickFormatter={(value: string) => formatDate(value, language)}
        />
        <YAxis {...AXIS} width={46} tickFormatter={(value: number) => formatNumber(value, language)} />
        <Tooltip
          cursor={{ stroke: "rgba(157,255,0,0.25)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipShell label={String(label)}>
                <p className="mono text-sm text-neon">{formatNumber(payload[0]?.value as number, language)}</p>
                <p className="text-[10px] text-chalk-500">cumulative</p>
              </TooltipShell>
            ) : null
          }
        />
        <Area
          type="monotone"
          dataKey="cumulative"
          stroke="#9DFF00"
          strokeWidth={2}
          fill="url(#growthFill)"
          dot={false}
          activeDot={{ r: 3, fill: "#9DFF00", stroke: "#080A0B", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function LatencyChart({
  data,
  language,
  height = 160,
}: {
  data: Array<{ date: string; avg_latency_ms: number | null; samples: number }>;
  language: Language;
  height?: number;
}) {
  const hasSamples = data.some((point) => point.avg_latency_ms !== null);
  if (!hasSamples) return <ChartEmpty height={height} label="No measured latency yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.045)" vertical={false} />
        <XAxis dataKey="date" {...AXIS} minTickGap={24} tickFormatter={(value: string) => formatDate(value, language)} />
        <YAxis {...AXIS} width={48} tickFormatter={(value: number) => `${Math.round(value)}`} />
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipShell label={String(label)}>
                <p className="mono text-sm text-violet-400">{formatLatency(payload[0]?.value as number)}</p>
                <p className="text-[10px] text-chalk-500">average connect time</p>
              </TooltipShell>
            ) : null
          }
        />
        <Line
          type="monotone"
          dataKey="avg_latency_ms"
          stroke="#8B5CF6"
          strokeWidth={2}
          dot={false}
          connectNulls
          activeDot={{ r: 3, fill: "#8B5CF6", stroke: "#080A0B", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ActivityChart({
  data,
  language,
  height = 160,
}: {
  data: Array<{ date: string; runs: number; accepted: number; new: number }>;
  language: Language;
  height?: number;
}) {
  const hasRuns = data.some((point) => point.runs > 0);
  if (!hasRuns) return <ChartEmpty height={height} label="No pipeline runs in this window" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.045)" vertical={false} />
        <XAxis dataKey="date" {...AXIS} minTickGap={24} tickFormatter={(value: string) => formatDate(value, language)} />
        <YAxis {...AXIS} width={46} allowDecimals={false} tickFormatter={(value: number) => formatNumber(value, language)} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipShell label={String(label)}>
                <p className="mono text-sm text-neon">{formatNumber(payload[0]?.value as number, language)} accepted</p>
                <p className="text-[10px] text-chalk-500">{formatNumber(payload[0]?.payload?.runs ?? 0, language)} run(s)</p>
              </TooltipShell>
            ) : null
          }
        />
        <Bar dataKey="accepted" fill="rgba(157,255,0,0.55)" radius={[4, 4, 0, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const HEALTH_COLORS: Record<string, string> = {
  reachable: "#9DFF00",
  failed: "#F87171",
  untested: "#3A4240",
  dns_resolved: "#60A5FA",
  unknown: "#8B5CF6",
};

export function HealthDonut({
  distribution,
  language,
  height = 180,
}: {
  distribution: Record<string, number>;
  language: Language;
  height?: number;
}) {
  const total = Object.values(distribution).reduce((sum, value) => sum + value, 0);
  if (!total) return <ChartEmpty height={height} label="No configurations recorded" />;
  const data = Object.entries(distribution)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => ({ key, value }));
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="key"
            innerRadius="66%"
            outerRadius="92%"
            paddingAngle={2}
            stroke="none"
          >
            {data.map((entry) => (
              <Cell key={entry.key} fill={HEALTH_COLORS[entry.key] ?? "#6E7875"} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipShell label={String(payload[0]?.name)}>
                  <p className="mono text-sm text-chalk-100">{formatNumber(payload[0]?.value as number, language)}</p>
                </TooltipShell>
              ) : null
            }
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="mono text-xl text-chalk-100">{formatNumber(total, language)}</span>
        <span className="text-[10px] uppercase tracking-widest text-chalk-500">configs</span>
      </div>
    </div>
  );
}

export function ProtocolBars({
  items,
  language,
}: {
  items: Array<{ protocol: string; count: number; share: number }>;
  language: Language;
}) {
  if (!items.length) return <ChartEmpty height={150} label="No protocol data" />;
  return (
    <ul className="space-y-3">
      {items.map((item, index) => (
        <li key={item.protocol} className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="font-mono uppercase tracking-wide text-chalk-300">{item.protocol}</span>
            <span className="mono text-chalk-500">{formatPercent(item.share)}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
            <div
              className={cn("h-full rounded-full", index === 0 ? "bg-neon" : index === 1 ? "bg-violet" : "bg-chalk-500/60")}
              style={{ width: `${Math.max(2, item.share * 100)}%` }}
            />
          </div>
          <p className="mono text-[10px] text-chalk-500">{formatNumber(item.count, language)} configurations</p>
        </li>
      ))}
    </ul>
  );
}

export function RingGauge({
  value,
  max,
  label,
  caption,
  size = 132,
}: {
  value: number;
  max: number;
  label: string;
  caption: string;
  size?: number;
}) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#080A0B" strokeOpacity={0.35} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#080A0B"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circumference * ratio} ${circumference}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="mono text-2xl font-medium text-ink-950">{label}</span>
        <span className="mt-0.5 max-w-[86px] text-[9px] font-medium uppercase leading-tight tracking-wider text-ink-950/70">
          {caption}
        </span>
      </div>
    </div>
  );
}

export function Heatmap({
  cells,
  language,
}: {
  cells: Array<{ date: string; added: number; tests: number; runs: number; intensity: number }>;
  language: Language;
}) {
  if (!cells.length) return <ChartEmpty height={140} />;
  const weeks: typeof cells[] = [];
  for (let index = 0; index < cells.length; index += 7) weeks.push(cells.slice(index, index + 7));
  const shades = ["bg-white/[0.035]", "bg-neon/15", "bg-neon/30", "bg-neon/55", "bg-neon/85"];
  return (
    <div className="space-y-3">
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {weeks.map((week, weekIndex) => (
          <div key={weekIndex} className="flex flex-col gap-1.5">
            {week.map((cell) => (
              <div
                key={cell.date}
                title={`${cell.date} · ${formatNumber(cell.added, language)} added · ${cell.tests} tests · ${cell.runs} runs`}
                className={cn("size-4 rounded-[4px] transition-transform hover:scale-110", shades[cell.intensity] ?? shades[0])}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between text-[10px] text-chalk-500">
        <span>{cells[0]?.date}</span>
        <div className="flex items-center gap-1">
          <span className="me-1">Less</span>
          {shades.map((shade) => (
            <span key={shade} className={cn("size-2.5 rounded-[3px]", shade)} />
          ))}
          <span className="ms-1">More</span>
        </div>
        <span>{cells[cells.length - 1]?.date}</span>
      </div>
    </div>
  );
}

export function Sparkline({ values, tone = "neon" }: { values: number[]; tone?: "neon" | "violet" | "danger" }) {
  if (values.length < 2) return <div className="h-10" />;
  const width = 120;
  const height = 36;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const color = tone === "neon" ? "#9DFF00" : tone === "violet" ? "#8B5CF6" : "#F87171";
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-9 w-full" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChartEmpty({ height = 160, label = "No data in this window" }: { height?: number; label?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/[0.07] text-[11px] text-chalk-500"
      style={{ height }}
    >
      <div className="h-px w-16 bg-white/10" />
      {label}
    </div>
  );
}
