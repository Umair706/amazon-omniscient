// Human labels for the backend's data-gap names (backend/app/workers/pipeline_steps/assumptions.py).
export const DATA_GAP_LABELS: Record<string, string> = {
  supplier_data_unavailable: "No 1688 supplier data — supplier score is neutral, not measured",
  fob_estimated_from_price: "Factory cost estimated from listing price (no supplier quotes)",
  break_even_assumed: "Break-even week assumed (sales forecast unavailable)",
  search_volume_assumed: "Search volume assumed (keyword research returned nothing)",
  revenue_per_seller_assumed: "Revenue per seller assumed",
  review_velocity_unavailable: "Review velocity not yet measurable — needs 14 days of tracking",
  moq_assumed: "Minimum order quantity assumed (suppliers listed no MOQ)",
  bsr_unavailable: "BSR could not be read — demand is scored as unknown, not favorable",
  sales_estimate_assumed: "Monthly sales assumed (no BSR to estimate from)",
  sales_estimate_uncalibrated: "Sales estimate is uncalibrated for this marketplace (US-derived model)",
  fx_rate_assumed: "Supplier costs converted to your currency at an approximate fixed rate — check today's rate",
  ppc_ad_share_assumed: "Net margin assumes about half of sales come from ads (the rest organic) — a blended estimate",
};

export function labelForDataGap(gap: string): string {
  return DATA_GAP_LABELS[gap] ?? gap.replace(/_/g, " ");
}
