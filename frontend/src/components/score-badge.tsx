"use client";
import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number | string;
  tier: string;
  size?: "sm" | "md" | "lg";
}

function getScoreColor(score: number): string {
  if (score >= 80) return "text-tier1 border-tier1";
  if (score >= 60) return "text-tier2 border-tier2";
  if (score >= 40) return "text-tier3 border-tier3";
  return "text-rejected border-rejected";
}

function getScoreBg(score: number): string {
  if (score >= 80) return "bg-tier1/10";
  if (score >= 60) return "bg-tier2/10";
  if (score >= 40) return "bg-tier3/10";
  return "bg-rejected/10";
}

function getTierLabel(tier: string): string {
  switch (tier) {
    case "HIGH": return "Strong Buy";
    case "MEDIUM": return "Buy";
    case "LOW": return "Hold";
    case "VERY_LOW": return "Avoid";
    case "FAIL": return "Disqualified";
    default: return tier;
  }
}

export function ScoreBadge({ score: rawScore, tier, size = "md" }: ScoreBadgeProps) {
  const score = typeof rawScore === "string" ? parseFloat(rawScore) || 0 : rawScore;
  const sizes = {
    sm: "w-12 h-12 text-lg",
    md: "w-16 h-16 text-xl",
    lg: "w-24 h-24 text-3xl",
  };
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={cn(
          "rounded-full border-2 flex items-center justify-center font-bold",
          getScoreColor(score),
          getScoreBg(score),
          sizes[size]
        )}
      >
        {score}
      </div>
      <span className={cn("text-xs font-medium", getScoreColor(score))}>
        {getTierLabel(tier)}
      </span>
    </div>
  );
}
