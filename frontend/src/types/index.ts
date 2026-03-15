// Type definitions — will be fully populated in Task #10 (schemas)
// Placeholder interfaces for development

export interface NicheListItem {
  id: number;
  name: string;
  primary_keyword: string;
  monthly_search_volume: number | null;
  avg_sale_price: number | null;
  avg_review_count: number | null;
  opportunity_score: number | null;
  confidence_tier: string | null;
  is_seasonal: boolean;
  ad_saturation_index: number | null;
  listing_gap_score: number | null;
}

export interface RecommendationSummary {
  id: number;
  niche_id: number;
  niche_name: string;
  omniscient_score: number;
  confidence_tier: string;
  recommended_sale_price: number;
  estimated_net_margin_pct: number;
  break_even_week_base: number;
  total_launch_capital: number;
  generated_at: string;
}

export interface WeeklyProjection {
  week_number: number;
  scenario: string;
  estimated_organic_rank: number;
  estimated_units_sold: number;
  revenue: number;
  cogs: number;
  fba_fees: number;
  ad_spend: number;
  storage_fees: number;
  net_profit: number;
  cumulative_profit: number;
  review_count_projected: number;
  organic_traffic_pct: number;
}

export interface RiskFlag {
  risk: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  source_module: string;
  mitigation: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
}
