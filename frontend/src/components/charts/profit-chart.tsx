"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { WeeklyProjection } from "@/types";

interface ProfitChartProps {
  bull: WeeklyProjection[];
  base: WeeklyProjection[];
  bear: WeeklyProjection[];
  className?: string;
}

export function ProfitChart({ bull, base, bear, className }: ProfitChartProps) {
  const data = base.map((week, i) => ({
    week: week.week_number,
    bull: bull[i]?.cumulative_profit ?? 0,
    base: week.cumulative_profit,
    bear: bear[i]?.cumulative_profit ?? 0,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="week"
            label={{ value: "Week", position: "insideBottom", offset: -5 }}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number, name: string) => [
              formatCurrency(value),
              name.charAt(0).toUpperCase() + name.slice(1),
            ]}
            labelFormatter={(label) => `Week ${label}`}
          />
          <Legend />
          <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
          <Line
            type="monotone"
            dataKey="bull"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
            name="Bull"
          />
          <Line
            type="monotone"
            dataKey="base"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            name="Base"
          />
          <Line
            type="monotone"
            dataKey="bear"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            name="Bear"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
