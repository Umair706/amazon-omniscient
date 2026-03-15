"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface BSRDataPoint {
  time: string;
  bsr: number;
}

interface BSRChartProps {
  data: BSRDataPoint[];
  className?: string;
}

export function BSRChart({ data, className }: BSRChartProps) {
  const formatted = data.map((d) => ({
    time: new Date(d.time).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    bsr: d.bsr,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={formatted} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="time"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
          />
          <YAxis
            reversed
            tickFormatter={(v) => v.toLocaleString()}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            label={{ value: "BSR (lower = better)", angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number) => [value.toLocaleString(), "BSR"]}
          />
          <Line
            type="monotone"
            dataKey="bsr"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
