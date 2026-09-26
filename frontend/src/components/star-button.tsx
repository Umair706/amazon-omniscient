"use client";

import { Star } from "lucide-react";

// A star toggle for niches. stopPropagation so clicking it inside a clickable row does
// not also navigate.
export function StarButton({
  starred,
  onToggle,
  className,
}: {
  starred: boolean;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={starred ? "Remove from starred" : "Add to starred"}
      title={starred ? "Starred" : "Star this niche"}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        onToggle();
      }}
      className={`inline-flex ${className ?? ""}`}
    >
      <Star className={`h-4 w-4 ${starred ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground hover:text-foreground"}`} />
    </button>
  );
}
