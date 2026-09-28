import { cn } from "@/lib/utils";

// The Omniscient mark: an "all-seeing" lens — an orbit ring around a pupil with
// a single orbiting node. Uses currentColor so it inherits the brand color.
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn("text-primary", className)}
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="15" className="fill-primary/10" />
      <ellipse cx="16" cy="16" rx="13" ry="7.5" stroke="currentColor" strokeWidth="1.6" opacity="0.5" />
      <ellipse cx="16" cy="16" rx="7.5" ry="13" stroke="currentColor" strokeWidth="1.6" opacity="0.5" transform="rotate(90 16 16)" />
      <circle cx="16" cy="16" r="4.2" fill="currentColor" />
      <circle cx="27" cy="16" r="2.2" fill="currentColor" />
    </svg>
  );
}

// The full lockup: mark + wordmark, with an optional tagline underneath.
export function Logo({ withTagline = true, className }: { withTagline?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark className="h-8 w-8 shrink-0" />
      <div className="leading-tight">
        <span className="block text-lg font-bold tracking-tight">Omniscient</span>
        {withTagline && (
          <span className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Product Research
          </span>
        )}
      </div>
    </div>
  );
}
