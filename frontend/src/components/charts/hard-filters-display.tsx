"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface HardFilter {
  filter: string;
  passed: boolean;
  reason: string;
  value: number | boolean;
}

interface HardFiltersDisplayProps {
  filters: HardFilter[];
  className?: string;
}

const FILTER_LABELS: Record<string, string> = {
  price_range: "Price Range ($15–$70)",
  review_moat: "Review Moat (< 2,000)",
  bsr_demand: "BSR Demand (< 50,000)",
  minimum_margin: "Minimum Margin (> 25%)",
  amazon_dominance: "Amazon Dominance (< 30%)",
  restricted_category: "Not Restricted/Hazmat",
  ip_patent_risk: "No IP/Patent Risk",
  seasonality: "Non-Seasonal Demand",
};

export function HardFiltersDisplay({ filters, className }: HardFiltersDisplayProps) {
  const passedCount = filters.filter((f) => f.passed).length;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">Hard Filters</span>
        <span
          className={cn(
            "text-sm font-semibold",
            passedCount === filters.length ? "text-tier1" : "text-rejected"
          )}
        >
          {passedCount}/{filters.length} passed
        </span>
      </div>
      <div className="grid gap-2">
        {filters.map((filter) => (
          <div
            key={filter.filter}
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
              filter.passed
                ? "border-tier1/20 bg-tier1/5"
                : "border-rejected/20 bg-rejected/5"
            )}
          >
            {filter.passed ? (
              <CheckCircle2 className="h-4 w-4 text-tier1 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 text-rejected shrink-0" />
            )}
            <span className={filter.passed ? "text-foreground" : "text-rejected"}>
              {FILTER_LABELS[filter.filter] || filter.filter}
            </span>
            {!filter.passed && (
              <span className="text-xs text-rejected/70 ml-auto">{filter.reason}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
