import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function tierColor(tier: string): string {
  switch (tier) {
    case "TIER_1":
      return "text-tier1";
    case "TIER_2":
      return "text-tier2";
    case "TIER_3":
      return "text-tier3";
    default:
      return "text-rejected";
  }
}

export function tierBgColor(tier: string): string {
  switch (tier) {
    case "TIER_1":
      return "bg-tier1/10 text-tier1 border-tier1/20";
    case "TIER_2":
      return "bg-tier2/10 text-tier2 border-tier2/20";
    case "TIER_3":
      return "bg-tier3/10 text-tier3 border-tier3/20";
    default:
      return "bg-rejected/10 text-rejected border-rejected/20";
  }
}

export function severityColor(severity: string): string {
  switch (severity) {
    case "CRITICAL":
      return "bg-red-500/10 text-red-500 border-red-500/20";
    case "HIGH":
      return "bg-orange-500/10 text-orange-500 border-orange-500/20";
    case "MEDIUM":
      return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
    case "LOW":
      return "bg-blue-500/10 text-blue-500 border-blue-500/20";
    default:
      return "bg-gray-500/10 text-gray-500 border-gray-500/20";
  }
}
