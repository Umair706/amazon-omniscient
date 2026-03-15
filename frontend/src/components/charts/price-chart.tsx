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
import { formatCurrency } from "@/lib/utils";

interface PriceDataPoint {
  time: string;
  price: number;
  has_coupon?: boolean;
}

interface PriceChartProps {
  data: PriceDataPoint[];
  className?: string;
}

export function PriceChart({ data, className }: PriceChartProps) {
  const formatted = data.map((d) => ({
    time: new Date(d.time).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    price: d.price,
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
            tickFormatter={(v) => `$${v}`}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
            }}
            formatter={(value: number) => [formatCurrency(value), "Price"]}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
