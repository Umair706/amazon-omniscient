"use client";

import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { WeeklyProjection } from "@/types";

interface OrganicRankChartProps {
  projections: WeeklyProjection[];
  className?: string;
}

export function OrganicRankChart({ projections, className }: OrganicRankChartProps) {
  const data = projections.map((week) => ({
    week: week.week_number,
    rank: week.estimated_organic_rank,
    organic_pct: week.organic_traffic_pct,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="week"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            yAxisId="left"
            reversed
            domain={[1, 50]}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            label={{ value: "Rank (lower = better)", angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            label={{ value: "Organic %", angle: 90, position: "insideRight", style: { fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            labelFormatter={(label) => `Week ${label}`}
            formatter={(value: number, name: string) => {
              if (name === "Organic Rank") return [value, name];
              return [`${value}%`, name];
            }}
          />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="rank"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            name="Organic Rank"
          />
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="organic_pct"
            stroke="#22c55e"
            fill="#22c55e"
            fillOpacity={0.15}
            name="Organic Traffic %"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
