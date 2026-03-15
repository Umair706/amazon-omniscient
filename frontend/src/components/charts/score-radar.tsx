"use client";

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface SubScore {
  name: string;
  value: number;
}

interface ScoreRadarProps {
  subScores: Record<string, number>;
  className?: string;
}

const LABEL_MAP: Record<string, string> = {
  demand: "Demand",
  competition: "Competition",
  revenue: "Revenue",
  margin: "Margin",
  trend: "Trend",
  review_feasibility: "Reviews",
  supplier: "Supplier",
  ppc_viability: "PPC",
  launch_feasibility: "Launch",
};

export function ScoreRadar({ subScores, className }: ScoreRadarProps) {
  const data: SubScore[] = Object.entries(subScores).map(([key, value]) => ({
    name: LABEL_MAP[key] || key,
    value: Math.round(value),
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
          <PolarGrid stroke="hsl(var(--border))" />
          <PolarAngleAxis
            dataKey="name"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
          />
          <Radar
            name="Score"
            dataKey="value"
            stroke="hsl(var(--primary))"
            fill="hsl(var(--primary))"
            fillOpacity={0.25}
            strokeWidth={2}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
              fontSize: "0.875rem",
            }}
            formatter={(value: number) => [`${value}/100`, "Score"]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
