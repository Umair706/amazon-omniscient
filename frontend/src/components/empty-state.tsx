"use client";

import { Inbox, LucideIcon } from "lucide-react";

// A blank section should never be silent. This states what is missing and why, and what
// the user can do about it (add an LLM key, wait for tracking, configure a proxy, ...).
export function EmptyState({
  title,
  reason,
  icon: Icon = Inbox,
  className,
}: {
  title: string;
  reason: string;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-10 px-4 ${className ?? ""}`}>
      <div className="p-3 rounded-full bg-muted mb-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-md text-xs text-muted-foreground">{reason}</p>
    </div>
  );
}

// Reusable reasons so the copy is consistent wherever a section can be empty.
export const EMPTY_REASONS = {
  llm: "This section is AI-generated. Add an LLM key (Settings, or run a local model) and re-analyze to populate it.",
  suppliers: "No supplier data. 1688 was unreachable (it blocks datacenter IPs). Add a proxy or Alibaba API key, then re-analyze.",
  tracking: "This appears once the 6-hourly tracker has built history for these products — it is empty on a fresh analysis.",
  noProducts: "No products were captured for this niche. Re-run the analysis, or check the marketplace and network.",
  competitors: "No competitor analysis yet. This is a separate step that scores listing quality and vulnerabilities; it needs an LLM key and a completed analysis.",
};
