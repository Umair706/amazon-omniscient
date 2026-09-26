"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LabelList,
  Cell,
} from "recharts";

interface CompetitorData {
  name: string;
  listing_quality_score: number;
  review_count: number;
  rating: number;
}

interface CompetitorBarChartProps {
  competitors: CompetitorData[];
  metric: "listing_quality_score" | "review_count" | "rating";
  className?: string;
}

const METRIC_CONFIG = {
  listing_quality_score: { label: "Listing Quality", domain: [0, 100] as [number, number], format: (v: number) => `${Math.round(v)}` },
  review_count: { label: "Review Count", domain: undefined, format: (v: number) => v.toLocaleString() },
  rating: { label: "Rating", domain: [0, 5] as [number, number], format: (v: number) => v.toFixed(1) },
};

const COLORS = [
  "hsl(var(--primary))", "#22c55e", "#eab308", "#f97316", "#ef4444",
  "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6", "#f43f5e",
];

const MAX_BARS = 10;
const ROW_HEIGHT = 40; // px per bar, so ten competitors are not crushed into 300px
const LABEL_MAX_CHARS = 22;

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1).trimEnd() + "…" : text;
}

interface Row {
  rank: number;
  fullName: string;
  label: string;
  value: number;
}

// Tooltip shows the FULL competitor name (the axis label is rank-prefixed and truncated).
function CompetitorTooltip({ active, payload, metricLabel, format }: any) {
  if (!active || !payload?.length) return null;
  const row: Row = payload[0].payload;
  return (
    <div className="rounded-md border bg-card p-2 text-xs shadow-sm max-w-[240px]">
      <p className="font-medium">{row.rank}. {row.fullName}</p>
      <p className="text-muted-foreground mt-0.5">{metricLabel}: {format(row.value)}</p>
    </div>
  );
}

export function CompetitorBarChart({ competitors, metric, className }: CompetitorBarChartProps) {
  const config = METRIC_CONFIG[metric];
  const data: Row[] = competitors.slice(0, MAX_BARS).map((c, i) => ({
    rank: i + 1,
    fullName: c.name,
    label: `${i + 1}. ${truncate(c.name, LABEL_MAX_CHARS)}`,
    value: c[metric] ?? 0,
  }));
  const height = Math.max(200, data.length * ROW_HEIGHT + 24);

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 52, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
          <XAxis
            type="number"
            domain={config.domain}
            tickFormatter={config.format}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={150}
            interval={0}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))", opacity: 0.3 }}
            content={<CompetitorTooltip metricLabel={config.label} format={config.format} />}
          />
          <Bar dataKey="value" name={config.label} radius={[0, 4, 4, 0]}>
            <LabelList
              dataKey="value"
              position="right"
              formatter={config.format}
              style={{ fill: "hsl(var(--foreground))", fontSize: 11 }}
            />
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
