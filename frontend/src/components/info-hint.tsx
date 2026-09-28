"use client";

import { Info } from "lucide-react";

// A small info icon that explains a number on hover, so users aren't left guessing how a
// metric is derived. Uses the native title tooltip — no dependency, works everywhere.
export function InfoHint({ text, className }: { text: string; className?: string }) {
  return (
    <span
      title={text}
      aria-label={text}
      className={`inline-flex cursor-help text-muted-foreground/60 hover:text-foreground align-middle ${className ?? ""}`}
    >
      <Info className="h-3.5 w-3.5" />
    </span>
  );
}
