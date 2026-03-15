"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { WeeklyProjection } from "@/types";

interface SalesChartProps {
  projections: WeeklyProjection[];
  className?: string;
}

export function SalesChart({ projections, className }: SalesChartProps) {
  const data = projections.map((week) => ({
    week: week.week_number,
    units: week.estimated_units_sold,
    reviews: week.review_count_projected,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="week"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            yAxisId="left"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            label={{ value: "Units Sold", angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            label={{ value: "Reviews", angle: 90, position: "insideRight", style: { fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            labelFormatter={(label) => `Week ${label}`}
          />
          <Legend />
          <Bar yAxisId="left" dataKey="units" fill="hsl(var(--primary))" name="Units Sold" radius={[2, 2, 0, 0]} />
          <Bar yAxisId="right" dataKey="reviews" fill="#22c55e" name="Cumulative Reviews" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
