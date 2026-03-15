"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
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
  listing_quality_score: { label: "Listing Quality", domain: [0, 100], format: (v: number) => `${v}` },
  review_count: { label: "Review Count", domain: undefined, format: (v: number) => v.toLocaleString() },
  rating: { label: "Rating", domain: [0, 5], format: (v: number) => v.toFixed(1) },
};

const COLORS = [
  "hsl(var(--primary))",
  "#22c55e",
  "#eab308",
  "#f97316",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
  "#f43f5e",
];

export function CompetitorBarChart({ competitors, metric, className }: CompetitorBarChartProps) {
  const config = METRIC_CONFIG[metric];
  const data = competitors.slice(0, 10).map((c) => ({
    name: c.name.length > 20 ? c.name.substring(0, 20) + "..." : c.name,
    value: c[metric],
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 80, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            domain={config.domain as [number, number] | undefined}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={75}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number) => [config.format(value), config.label]}
          />
          <Bar dataKey="value" name={config.label} radius={[0, 4, 4, 0]}>
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
