// ── Pagination ───────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// ── Niche ────────────────────────────────────────────────────────────────

export interface NicheListItem {
  id: number;
  name: string;
  primary_keyword: string;
  monthly_search_volume: number | null;
  avg_sale_price: string | number | null;
  avg_review_count: number | null;
  opportunity_score: string | number | null;
  confidence_tier: string | null;
  is_seasonal: boolean | null;
  hard_filter_passed: boolean | null;
  created_at: string;
}

export interface NicheDetail {
  id: number;
  name: string;
  primary_keyword: string;
  category_id: string | null;
  monthly_search_volume: number | null;
  avg_sale_price: string | null;
  avg_review_count: number | null;
  avg_bsr: number | null;
  status: string | null;

  // Scores
  opportunity_score: string | null;
  confidence_tier: string | null;
  demand_score: string | null;
  competition_score: string | null;
  margin_score: string | null;
  ad_profitability_score: string | null;
  review_achievability_score: string | null;
  supplier_reliability_score: string | null;
  sales_velocity_score: string | null;
  marketing_score: string | null;
  brand_building_score: string | null;

  // Flags
  is_seasonal: boolean | null;
  seasonality_variance: string | null;
  ad_saturation_index: string | null;
  listing_gap_score: string | null;
  hard_filter_passed: boolean | null;
  hard_filter_fail_reasons: string[] | null;
  last_scored_at: string | null;

  created_at: string;
  updated_at: string | null;
}

// ── Product ──────────────────────────────────────────────────────────────

export interface ProductSummary {
  id: number;
  asin: string;
  niche_id: number | null;
  title: string | null;
  brand: string | null;
  current_price: string | null;
  current_bsr: number | null;
  review_count: number | null;
  rating: string | null;
  estimated_monthly_revenue: string | null;
  listing_quality_score: string | null;
}

export interface ProductDetail extends ProductSummary {
  category_id: string | null;
  current_subcategory_bsr: number | null;
  bsr_category: string | null;
  subcategory_name: string | null;

  // Listing flags
  is_fba: boolean | null;
  is_amazon_choice: boolean | null;
  is_best_seller: boolean | null;
  is_sponsored: boolean | null;
  has_a_plus: boolean | null;
  has_video: boolean | null;
  has_brand_story: boolean | null;
  image_count: number | null;
  bullet_count: number | null;

  // Seller info
  seller_id: string | null;
  brand_registered: boolean | null;
  storefront_asin_count: number | null;

  // Estimates
  estimated_monthly_units: number | null;

  // Cost structure
  fba_fee: string | null;
  referral_fee_pct: string | null;
  product_weight_lbs: string | null;
  product_dimensions: string | null;

  last_scraped_at: string | null;
  created_at: string;
  updated_at: string | null;
}

// ── Recommendation ───────────────────────────────────────────────────────

export interface RecommendationSummary {
  id: number;
  niche_id: number;
  niche_name?: string;
  omniscient_score: string | number;
  confidence_tier: string;
  recommended_sale_price: string | number | null;
  estimated_net_margin_pct: string | number | null;
  total_launch_capital: string | number | null;
  break_even_week_base: number | null;
  generated_at: string | null;
}

export interface RecommendationDetail extends RecommendationSummary {
  product_description: string | null;
  differentiation_features: string[] | null;
  top_supplier_ids: number[] | null;

  // Unit economics
  best_landed_cost: string | null;

  // Break-even timelines
  break_even_week_bull: number | null;
  break_even_week_bear: number | null;

  // Reviews
  review_threshold: number | null;
  weeks_to_review_threshold: number | null;
  vine_recommended: boolean | null;
  vine_cost: string | null;

  // PPC
  ppc_budget_30d: string | null;
  ppc_budget_90d: string | null;
  break_even_acos: string | null;
  estimated_acos: string | null;

  // Scoring breakdown
  subscore_breakdown: Record<string, number> | null;
  competitor_landscape: Record<string, unknown> | null;

  // JSONB payloads
  marketing_channels: Record<string, unknown> | null;
  risk_flags: Record<string, unknown> | null;
  launch_playbook: Record<string, unknown> | null;
  ppc_strategy: Record<string, unknown> | null;
  product_blueprint: Record<string, unknown> | null;
  financial_report: Record<string, unknown> | null;

  // Intelligence JSONB payloads
  niche_overview: Record<string, unknown> | null;
  product_overviews: Record<string, unknown>[] | null;
  product_ideas: Record<string, unknown>[] | null;
  review_intelligence: Record<string, unknown> | null;
  product_supplier_matches: Record<string, unknown>[] | null;
}

// ── Financial Projections ────────────────────────────────────────────────

export interface WeeklyProjection {
  id: number;
  niche_id: number;
  scenario: string | null;
  week_number: number | null;
  estimated_organic_rank: number | null;
  estimated_units_sold: number | null;
  revenue: string | null;
  cogs: string | null;
  fba_fees: string | null;
  ad_spend: string | null;
  storage_fees: string | null;
  net_profit: string | null;
  cumulative_profit: string | null;
  review_count_projected: number | null;
  organic_traffic_pct: string | null;
  calculated_at: string | null;
}

// ── Competitor ───────────────────────────────────────────────────────────

export interface CompetitorEntry {
  id: number;
  niche_id: number;
  product_id: number;
  organic_rank: number | null;
  sponsored_rank: number | null;
  listing_quality_score: string | null;
  title_score: string | null;
  image_score: string | null;
  bullet_score: string | null;
  a_plus_score: string | null;
  video_score: string | null;
  backend_kw_score: string | null;
  price_90d_min: string | null;
  price_90d_max: string | null;
  price_90d_avg: string | null;
  has_subscribe_save: boolean | null;
  coupon_frequency: number | null;
  lightning_deal_frequency: number | null;
  review_velocity: string | null;
  sentiment_score: string | null;
  vulnerability: string | null;
  vulnerability_type: string | null;
  last_analyzed_at: string | null;
}

// ── Supplier ─────────────────────────────────────────────────────────────

export interface SupplierEntry {
  id: number;
  niche_id: number;
  supplier_name: string | null;
  alibaba_url: string | null;
  country: string | null;
  city: string | null;
  years_in_business: number | null;
  is_gold_supplier: boolean | null;
  is_verified: boolean | null;
  is_audited: boolean | null;
  trade_assurance: boolean | null;
  transaction_volume: number | null;
  moq: number | null;
  fob_price_min: string | null;
  fob_price_max: string | null;
  lead_time_days: number | null;
  supplier_score: string | null;
  risk_flags: string[] | null;
}

// ── Risk ─────────────────────────────────────────────────────────────────

export interface RiskFlag {
  filter: string;
  passed: boolean;
  value: unknown;
  reason: string;
}

// ── Job ──────────────────────────────────────────────────────────────────

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string | null;
}

// ── Settings ─────────────────────────────────────────────────────────────

export interface UserSettings {
  id: number;
  user_id: string;
  has_sp_api_credentials: boolean;
  has_ads_api_credentials: boolean;
  has_alibaba_credentials: boolean;
  default_marketplace: string | null;
  min_margin_threshold: string | null;
  max_review_moat: number | null;
  allow_seasonal: boolean | null;
}
