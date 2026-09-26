// Human labels for the backend's data-gap names (backend/app/workers/pipeline_steps/assumptions.py).
export const DATA_GAP_LABELS: Record<string, string> = {
  supplier_data_unavailable: "No 1688 supplier data — supplier score is neutral, not measured",
  fob_estimated_from_price: "Factory cost estimated from listing price (no supplier quotes)",
  break_even_assumed: "Break-even week assumed (no PPC plan data)",
  search_volume_assumed: "Search volume assumed (keyword research returned nothing)",
  revenue_per_seller_assumed: "Revenue per seller assumed",
  review_velocity_unavailable: "Review velocity not yet measurable — needs 14 days of tracking",
  moq_assumed: "Minimum order quantity assumed (suppliers listed no MOQ)",
};

export function labelForDataGap(gap: string): string {
  return DATA_GAP_LABELS[gap] ?? gap.replace(/_/g, " ");
}
