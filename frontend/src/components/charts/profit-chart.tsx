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
import { formatCurrency, currencySymbol } from "@/lib/utils";
import type { WeeklyProjection } from "@/types";

interface ProfitChartProps {
  bull: WeeklyProjection[];
  base: WeeklyProjection[];
  bear: WeeklyProjection[];
  className?: string;
  marketplace?: string;
  breakEvenWeek?: number | null;
}

export function ProfitChart({ bull, base, bear, className, marketplace, breakEvenWeek }: ProfitChartProps) {
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
            minTickGap={24}
            label={{ value: "Week", position: "insideBottom", offset: -5 }}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            tickFormatter={(v) => `${currencySymbol(marketplace)}${(v / 1000).toFixed(0)}k`}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            width={64}
            label={{ value: "Cumulative profit", angle: -90, position: "insideLeft", style: { fill: "hsl(var(--muted-foreground))", fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number, name: string) => [
              formatCurrency(value, marketplace),
              name.charAt(0).toUpperCase() + name.slice(1),
            ]}
            labelFormatter={(label) => `Week ${label}`}
          />
          <Legend />
          {/* y=0 is break-even: above it the venture is in profit. */}
          <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3"
            label={{ value: "Break-even", position: "insideBottomLeft", style: { fill: "hsl(var(--muted-foreground))", fontSize: 10 } }} />
          {breakEvenWeek ? (
            <ReferenceLine x={breakEvenWeek} stroke="hsl(var(--primary))" strokeDasharray="4 2"
              label={{ value: `Base break-even wk ${breakEvenWeek}`, position: "top", style: { fill: "hsl(var(--primary))", fontSize: 10 } }} />
          ) : null}
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
