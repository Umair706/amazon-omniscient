"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { WeeklyProjection } from "@/types";

interface RevenueChartProps {
  projections: WeeklyProjection[];
  className?: string;
}

export function RevenueChart({ projections, className }: RevenueChartProps) {
  const data = projections.map((week) => ({
    week: week.week_number,
    revenue: week.revenue,
    cogs: week.cogs,
    fba_fees: week.fba_fees,
    ad_spend: week.ad_spend,
    net_profit: week.net_profit,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="week"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis
            tickFormatter={(v) => `$${v}`}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number, name: string) => [formatCurrency(value), name]}
            labelFormatter={(label) => `Week ${label}`}
          />
          <Legend />
          <Area
            type="monotone"
            dataKey="revenue"
            stackId="1"
            stroke="#22c55e"
            fill="#22c55e"
            fillOpacity={0.3}
            name="Revenue"
          />
          <Area
            type="monotone"
            dataKey="cogs"
            stackId="2"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.2}
            name="COGS"
          />
          <Area
            type="monotone"
            dataKey="ad_spend"
            stackId="2"
            stroke="#eab308"
            fill="#eab308"
            fillOpacity={0.2}
            name="Ad Spend"
          />
          <Area
            type="monotone"
            dataKey="fba_fees"
            stackId="2"
            stroke="#f97316"
            fill="#f97316"
            fillOpacity={0.2}
            name="FBA Fees"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
