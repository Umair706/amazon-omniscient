// Amazon marketplaces this tool analyses. Keep in sync with backend/app/core/marketplace.py.
export const MARKETPLACE_LABELS: Record<string, string> = {
  AU: "Amazon.com.au (Australia)",
  US: "Amazon.com (United States)",
};

// Full human label for a marketplace code, e.g. "AU" -> "Amazon.com.au (Australia)".
export function marketplaceLabel(code?: string | null): string {
  if (!code) return "Unknown marketplace";
  return MARKETPLACE_LABELS[code] ?? code;
}
