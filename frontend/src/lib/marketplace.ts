// Amazon marketplaces this tool analyses. Keep in sync with backend/app/core/marketplace.py.
export const MARKETPLACE_LABELS: Record<string, string> = {
  AU: "Amazon.com.au (Australia)",
  US: "Amazon.com (United States)",
};

// Codes for a selector, AU first (the default marketplace).
export const MARKETPLACE_CODES = ["AU", "US"];

// Full human label for a marketplace code, e.g. "AU" -> "Amazon.com.au (Australia)".
export function marketplaceLabel(code?: string | null): string {
  if (!code) return "Unknown marketplace";
  return MARKETPLACE_LABELS[code] ?? code;
}

// The storefront domain per marketplace. Keep in sync with backend/app/core/marketplace.py.
export const MARKETPLACE_DOMAINS: Record<string, string> = {
  AU: "amazon.com.au",
  US: "amazon.com",
};

// Link to a product on the correct Amazon store. A US-hardcoded link 404s / geo-redirects
// for an AU-only ASIN, so the domain must follow the marketplace.
export function amazonProductUrl(asin: string, marketplace?: string | null): string {
  const domain = (marketplace && MARKETPLACE_DOMAINS[marketplace]) || MARKETPLACE_DOMAINS.US;
  return `https://www.${domain}/dp/${asin}`;
}
