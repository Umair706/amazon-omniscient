"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBadge } from "@/components/score-badge";
import { StatCard } from "@/components/stat-card";
import { formatCurrency, formatPercent } from "@/lib/utils";
import api from "@/lib/api";
import {
  ArrowLeft,
  DollarSign,
  TrendingUp,
  Clock,
  ShieldCheck,
  Target,
  Megaphone,
  Star,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  RefreshCw,
} from "lucide-react";

interface RecommendationDetail {
  id: number;
  niche_id: number;
  niche_name: string | null;
  omniscient_score: number;
  confidence_tier: string;
  product_description: string | null;
  differentiation_features: string[] | null;
  best_landed_cost: number | null;
  recommended_sale_price: number | null;
  estimated_net_margin_pct: number | null;
  break_even_week_bull: number | null;
  break_even_week_base: number | null;
  break_even_week_bear: number | null;
  total_launch_capital: number | null;
  review_threshold: number | null;
  weeks_to_review_threshold: number | null;
  vine_recommended: boolean | null;
  vine_cost: number | null;
  ppc_budget_30d: number | null;
  ppc_budget_90d: number | null;
  break_even_acos: number | null;
  estimated_acos: number | null;
  subscore_breakdown: Record<string, number> | null;
  competitor_landscape: any;
  risk_flags: any;
  ppc_strategy: any;
  marketing_channels: any;
  launch_playbook: any;
  product_blueprint: any;
  financial_report: any;
  niche_overview: any;
  product_overviews: any;
  product_ideas: any;
  review_intelligence: any;
  product_supplier_matches: any;
  generated_at: string;
}

type TabId = "overview" | "market-intel" | "competitors" | "product-ideas" | "suppliers" | "reviews" | "product" | "blueprint" | "financials" | "marketing" | "playbook";

export default function OpportunityBriefPage() {
  const params = useParams();
  const id = params.id as string;

  const [rec, setRec] = useState<RecommendationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");

  const fetchRec = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/recommendations/${id}`);
      setRec(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load recommendation");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRec();
  }, [fetchRec]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4 text-center py-12">
        <AlertTriangle className="h-10 w-10 text-destructive mx-auto" />
        <p className="text-destructive font-medium">{error}</p>
        <Button variant="outline" onClick={fetchRec}>
          <RefreshCw className="h-4 w-4 mr-2" /> Retry
        </Button>
      </div>
    );
  }

  if (!rec) return <div className="text-muted-foreground">Recommendation not found.</div>;

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "market-intel", label: "Market Intel" },
    { id: "competitors", label: "Competitors" },
    { id: "product-ideas", label: "Product Ideas" },
    { id: "suppliers", label: "Suppliers" },
    { id: "reviews", label: "Reviews" },
    { id: "product", label: "Product Strategy" },
    { id: "blueprint", label: "Blueprint" },
    { id: "financials", label: "Financials" },
    { id: "marketing", label: "Marketing" },
    { id: "playbook", label: "Playbook" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => window.history.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2">
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          <h1 className="text-3xl font-bold">
            {rec.niche_name ? `${rec.niche_name.charAt(0).toUpperCase() + rec.niche_name.slice(1)}` : "Product Opportunity Brief"}
          </h1>
          <p className="text-muted-foreground mt-1">
            Generated {new Date(rec.generated_at).toLocaleDateString()}
          </p>
        </div>
        <ScoreBadge score={rec.omniscient_score} tier={rec.confidence_tier} size="lg" />
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard title="Sale Price" value={rec.recommended_sale_price ? formatCurrency(rec.recommended_sale_price) : "—"} icon={DollarSign} />
        <div className="relative">
          <StatCard title="Net Margin" value={rec.estimated_net_margin_pct ? formatPercent(rec.estimated_net_margin_pct) : "—"} icon={TrendingUp} />
          {rec.confidence_tier === "FAIL" && (
            <span className="absolute top-2 right-2 text-[10px] text-destructive font-medium">risk-adjusted</span>
          )}
        </div>
        <div className="relative">
          <StatCard title="Break-Even" value={rec.break_even_week_base ? `Week ${rec.break_even_week_base}` : "—"} icon={Clock} />
          {rec.confidence_tier === "FAIL" && (
            <span className="absolute top-2 right-2 text-[10px] text-destructive font-medium">risk-adjusted</span>
          )}
        </div>
        <StatCard title="Launch Capital" value={rec.total_launch_capital ? formatCurrency(rec.total_launch_capital) : "—"} icon={Target} />
      </div>

      {/* Tabs */}
      <div className="border-b overflow-x-auto">
        <div className="flex gap-4 min-w-max">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* Subscore Breakdown */}
          {rec.subscore_breakdown && Object.keys(rec.subscore_breakdown).length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Omniscient Score Breakdown</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 md:grid-cols-3 gap-3">
                  {Object.entries(rec.subscore_breakdown).map(([key, value]) => {
                    const label = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                    const score = typeof value === "number" ? value : 0;
                    const color = score >= 70 ? "text-green-600" : score >= 40 ? "text-yellow-600" : "text-red-600";
                    return (
                      <div key={key} className="p-3 rounded-lg border text-center">
                        <p className="text-xs text-muted-foreground mb-1">{label}</p>
                        <p className={`text-lg font-bold ${color}`}>{score}<span className="text-xs text-muted-foreground">/100</span></p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Market Stats from competitor_landscape */}
          {rec.competitor_landscape && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Market Snapshot</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Competitors</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.total_competitors ?? "—"}</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Avg Price</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.price_stats?.avg ? formatCurrency(rec.competitor_landscape.price_stats.avg) : "—"}</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Avg Rating</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.rating_stats?.avg ? `${rec.competitor_landscape.rating_stats.avg}★` : "—"}</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Avg Reviews</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.review_stats?.avg ? Math.round(rec.competitor_landscape.review_stats.avg) : "—"}</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Avg Listing Quality</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.avg_listing_quality ?? "—"}<span className="text-xs text-muted-foreground">/100</span></p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Entry Difficulty</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.entry_difficulty_score ?? "—"}<span className="text-xs text-muted-foreground">/100</span></p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Price Range</p>
                    <p className="text-xl font-bold mt-1">{rec.competitor_landscape.price_stats?.min != null ? `${formatCurrency(rec.competitor_landscape.price_stats.min)}-${formatCurrency(rec.competitor_landscape.price_stats.max)}` : "—"}</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <p className="text-xs text-muted-foreground">Vulnerable Competitors</p>
                    <p className="text-xl font-bold mt-1">{(rec.competitor_landscape.high_vulnerability_count || 0) + (rec.competitor_landscape.medium_vulnerability_count || 0)}</p>
                  </div>
                </div>
                {rec.competitor_landscape.opportunity_areas?.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium mb-2">Opportunity Areas</p>
                    <ul className="space-y-1">
                      {rec.competitor_landscape.opportunity_areas.map((area: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Lightbulb className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                          {area}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Break-Even Scenarios */}
            <Card>
              <CardHeader><CardTitle className="text-lg">Break-Even Analysis</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { label: "Bull (Optimistic)", week: rec.break_even_week_bull, color: "text-tier1" },
                    { label: "Base (Realistic)", week: rec.break_even_week_base, color: "text-primary" },
                    { label: "Bear (Pessimistic)", week: rec.break_even_week_bear, color: "text-rejected" },
                  ].map((s) => (
                    <div key={s.label} className="flex items-center justify-between">
                      <span className="text-sm">{s.label}</span>
                      <span className={`font-semibold ${s.color}`}>
                        {s.week ? `Week ${s.week}` : "N/A"}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* PPC Overview */}
            <Card>
              <CardHeader><CardTitle className="text-lg">PPC Overview</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span>30-day Budget</span>
                    <span className="font-semibold">{rec.ppc_budget_30d ? formatCurrency(rec.ppc_budget_30d) : "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>90-day Budget</span>
                    <span className="font-semibold">{rec.ppc_budget_90d ? formatCurrency(rec.ppc_budget_90d) : "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Break-Even ACOS</span>
                    <span className="font-semibold">{rec.break_even_acos ? `${rec.break_even_acos}%` : "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Estimated ACOS</span>
                    <span className="font-semibold">{rec.estimated_acos ? `${rec.estimated_acos}%` : "—"}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Review Strategy */}
            <Card>
              <CardHeader><CardTitle className="text-lg">Review Strategy</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span>Target Reviews</span>
                    <span className="font-semibold">{rec.review_threshold || "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Weeks to Target</span>
                    <span className="font-semibold">{rec.weeks_to_review_threshold || "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Vine Recommended</span>
                    <span className="font-semibold">
                      {rec.vine_recommended ? (
                        <Badge>Yes</Badge>
                      ) : (
                        <Badge variant="secondary">No</Badge>
                      )}
                    </span>
                  </div>
                  {rec.vine_cost && (
                    <div className="flex justify-between text-sm">
                      <span>Vine Cost</span>
                      <span className="font-semibold">{formatCurrency(rec.vine_cost)}</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Risk Flags & Hard Filters */}
            <Card>
              <CardHeader><CardTitle className="text-lg">Risk Flags</CardTitle></CardHeader>
              <CardContent>
                {rec.risk_flags?.fail_reasons?.length > 0 ? (
                  <div className="space-y-2">
                    {rec.risk_flags.fail_reasons.map((reason: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <AlertTriangle className="h-4 w-4 text-rejected shrink-0 mt-0.5" />
                        <span className="text-rejected">{reason}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-tier1">
                    <CheckCircle2 className="h-4 w-4" />
                    No risk flags detected
                  </div>
                )}
                {rec.risk_flags?.hard_filters?.length > 0 && (
                  <div className="mt-4 pt-4 border-t space-y-2">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Hard Filter Results</p>
                    {rec.risk_flags.hard_filters.map((f: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="capitalize">{f.filter?.replace(/_/g, " ")}</span>
                        <Badge variant={f.passed ? "outline" : "destructive"} className="text-[10px]">
                          {f.passed ? "Pass" : "Fail"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Market Intelligence Tab */}
      {tab === "market-intel" && (
        <div className="space-y-6">
          {rec.niche_overview ? (
            <>
              <Card>
                <CardHeader><CardTitle className="text-lg">Market Overview</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed whitespace-pre-line">
                    {rec.niche_overview.market_narrative}
                  </p>
                </CardContent>
              </Card>

              {rec.niche_overview.key_takeaway && (
                <Card className="border-primary/50 bg-primary/5">
                  <CardContent className="p-4">
                    <p className="font-semibold text-primary">{rec.niche_overview.key_takeaway}</p>
                  </CardContent>
                </Card>
              )}

              {rec.niche_overview.market_size_assessment && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Market Size Assessment</CardTitle></CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{rec.niche_overview.market_size_assessment}</p>
                  </CardContent>
                </Card>
              )}

              {rec.niche_overview.trend_analysis && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Trend Analysis</CardTitle></CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{rec.niche_overview.trend_analysis}</p>
                  </CardContent>
                </Card>
              )}

              {rec.niche_overview.competitive_dynamics && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Competitive Dynamics</CardTitle></CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{rec.niche_overview.competitive_dynamics}</p>
                  </CardContent>
                </Card>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader><CardTitle className="text-sm">Entry Barriers</CardTitle></CardHeader>
                  <CardContent>
                    {rec.niche_overview.entry_barriers?.length > 0 ? (
                      <ul className="space-y-2">
                        {rec.niche_overview.entry_barriers.map((barrier: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <AlertTriangle className="h-4 w-4 text-rejected shrink-0 mt-0.5" />
                            {barrier}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No entry barriers identified.</p>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-sm">Opportunities</CardTitle></CardHeader>
                  <CardContent>
                    {rec.niche_overview.opportunity_windows?.length > 0 ? (
                      <ul className="space-y-2">
                        {rec.niche_overview.opportunity_windows.map((opp: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <Lightbulb className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                            {opp}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No opportunities identified.</p>
                    )}
                  </CardContent>
                </Card>
              </div>
            </>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No market intelligence available.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Competitors Tab */}
      {tab === "competitors" && (
        <div className="space-y-4">
          {rec.product_overviews && rec.product_overviews.length > 0 ? (
            rec.product_overviews.map((p: any) => (
              <Card key={p.asin}>
                <CardContent className="p-4">
                  <div className="flex gap-4 items-start">
                    {p.image_url && (
                      <img
                        src={p.image_url}
                        alt={p.title || p.asin}
                        className="w-20 h-20 object-contain rounded border shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0 mr-3">
                          <h4 className="font-semibold text-sm">{p.title || p.asin}</h4>
                          <div className="flex flex-wrap gap-2 items-center mt-1 text-xs text-muted-foreground">
                            <a
                              href={`https://www.amazon.com/dp/${p.asin}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline font-mono"
                            >
                              {p.asin}
                            </a>
                            {p.price != null && <span className="font-semibold text-foreground">{formatCurrency(p.price)}</span>}
                            {p.rating != null && <span>{p.rating}&#9733;</span>}
                            {p.review_count != null && <span>{p.review_count.toLocaleString()} reviews</span>}
                            {p.bsr != null && <span>BSR: {p.bsr.toLocaleString()}</span>}
                          </div>
                          <p className="text-sm text-muted-foreground mt-2">{p.overview}</p>
                        </div>
                        <Badge variant={p.threat_level === "high" ? "destructive" : p.threat_level === "medium" ? "secondary" : "outline"}>
                          {p.threat_level} threat
                        </Badge>
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-3">
                    <div>
                      <p className="text-xs font-medium text-green-600 mb-1">Strengths</p>
                      <ul className="space-y-1">
                        {p.strengths?.map((s: string, i: number) => (
                          <li key={i} className="text-xs text-muted-foreground flex items-start gap-1">
                            <CheckCircle2 className="h-3 w-3 text-green-500 shrink-0 mt-0.5" />
                            {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-red-600 mb-1">Weaknesses</p>
                      <ul className="space-y-1">
                        {p.weaknesses?.map((w: string, i: number) => (
                          <li key={i} className="text-xs text-muted-foreground flex items-start gap-1">
                            <AlertTriangle className="h-3 w-3 text-red-500 shrink-0 mt-0.5" />
                            {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  {(p.what_they_do_well || p.vulnerability_to_exploit) && (
                    <div className="mt-3 pt-3 border-t grid grid-cols-2 gap-4">
                      {p.what_they_do_well && (
                        <div>
                          <p className="text-xs font-medium mb-1">What they do well</p>
                          <p className="text-xs text-muted-foreground">{p.what_they_do_well}</p>
                        </div>
                      )}
                      {p.vulnerability_to_exploit && (
                        <div>
                          <p className="text-xs font-medium mb-1">Vulnerability to exploit</p>
                          <p className="text-xs text-muted-foreground">{p.vulnerability_to_exploit}</p>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No competitor analysis available. This data requires LLM analysis to generate.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Product Ideas Tab */}
      {tab === "product-ideas" && (
        <div className="space-y-4">
          {rec.product_ideas && rec.product_ideas.length > 0 ? (
            rec.product_ideas.map((idea: any, i: number) => (
              <Card key={i}>
                <CardHeader>
                  <CardTitle className="text-base">{idea.idea_name}</CardTitle>
                  <div className="flex gap-2 flex-wrap">
                    {idea.target_price && <Badge>Target: {formatCurrency(idea.target_price)}</Badge>}
                    {idea.estimated_difficulty && <Badge variant="outline">{idea.estimated_difficulty} difficulty</Badge>}
                    {idea.estimated_margin && <Badge variant="outline">{idea.estimated_margin} margin</Badge>}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm">{idea.concept}</p>
                  {idea.key_differentiators?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium mb-1">Key Differentiators</p>
                      <ul className="space-y-1">
                        {idea.key_differentiators.map((d: string, j: number) => (
                          <li key={j} className="text-xs text-muted-foreground flex items-start gap-1">
                            <Lightbulb className="h-3 w-3 text-primary shrink-0 mt-0.5" />
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {idea.pain_points_addressed?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium mb-1">Pain Points Addressed</p>
                      <ul className="space-y-1">
                        {idea.pain_points_addressed.map((pp: string, j: number) => (
                          <li key={j} className="text-xs text-muted-foreground flex items-start gap-1">
                            <CheckCircle2 className="h-3 w-3 text-green-500 shrink-0 mt-0.5" />
                            {pp}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {idea.why_it_works && (
                    <p className="text-sm text-muted-foreground italic">{idea.why_it_works}</p>
                  )}
                  {idea.risk_factors?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium mb-1">Risk Factors</p>
                      <ul className="space-y-1">
                        {idea.risk_factors.map((r: string, j: number) => (
                          <li key={j} className="text-xs text-muted-foreground flex items-start gap-1">
                            <AlertTriangle className="h-3 w-3 text-rejected shrink-0 mt-0.5" />
                            {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {idea.supplier_search_terms?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium mb-1">1688 Search Terms</p>
                      <div className="flex gap-1 flex-wrap">
                        {idea.supplier_search_terms.map((term: string, j: number) => (
                          <Badge key={j} variant="secondary" className="text-xs">{term}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No product ideas available.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Suppliers Tab */}
      {tab === "suppliers" && (
        <div className="space-y-6">
          {rec.product_supplier_matches && rec.product_supplier_matches.length > 0 ? (
            rec.product_supplier_matches.map((pm: any) => (
              <Card key={pm.asin}>
                <CardHeader>
                  <CardTitle className="text-sm truncate">{pm.product_title}</CardTitle>
                  <p className="text-xs text-muted-foreground">{pm.asin}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  {pm.matched_suppliers?.length > 0 ? (
                    pm.matched_suppliers.map((s: any, i: number) => (
                      <div key={i} className="border rounded p-3">
                        <div className="flex gap-3 items-start">
                          {s.image_url && (
                            <img
                              src={s.image_url}
                              alt={s.product_title || s.supplier_name || "Supplier product"}
                              className="w-14 h-14 object-contain rounded border shrink-0"
                            />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-start">
                              <div className="min-w-0">
                                <span className="font-medium text-sm">{s.supplier_name || s.shop_name || "Unknown Supplier"}</span>
                                {s.product_title && (
                                  <p className="text-xs text-muted-foreground truncate">{s.product_title}</p>
                                )}
                              </div>
                              <Badge variant={s.match_score >= 90 ? "default" : "secondary"} className="shrink-0 ml-2">
                                {s.match_score}% match
                              </Badge>
                            </div>
                            {s.match_reasoning && (
                              <p className="text-xs text-muted-foreground mt-1">{s.match_reasoning}</p>
                            )}
                            <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                              {(s.price_min_usd != null || s.price_max_usd != null) && (
                                <span>
                                  {formatCurrency(s.price_min_usd || 0)}-{formatCurrency(s.price_max_usd || 0)}
                                </span>
                              )}
                              {s.moq && <span>MOQ: {s.moq}</span>}
                              {s.location && <span>{s.location}</span>}
                            </div>
                            {s.product_url && (
                              <a
                                href={s.product_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-primary mt-1 inline-block hover:underline"
                              >
                                View on 1688 &rarr;
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">No close supplier match found</p>
                  )}
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No per-product supplier matches available.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Reviews Intelligence Tab */}
      {tab === "reviews" && (
        <div className="space-y-6">
          {rec.review_intelligence ? (
            <>
              {/* Header stats */}
              <div className="grid grid-cols-3 gap-4">
                <StatCard
                  title="Reviews Analyzed"
                  value={rec.review_intelligence.total_reviews_analyzed?.toString() || "0"}
                  icon={Star}
                />
                <StatCard
                  title="Sentiment Score"
                  value={`${rec.review_intelligence.sentiment_score || 0}/100`}
                  icon={TrendingUp}
                />
                <StatCard
                  title="Overall Sentiment"
                  value={rec.review_intelligence.overall_sentiment || "N/A"}
                  icon={Target}
                />
              </div>

              {/* Key Insights */}
              {rec.review_intelligence.key_insights?.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Key Insights</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-0">
                      {rec.review_intelligence.key_insights.map((insight: any, i: number) => (
                        <div key={i} className="border-b last:border-0 py-3">
                          <div className="flex justify-between items-start">
                            <p className="text-sm font-medium flex-1 mr-2">{insight.insight}</p>
                            <div className="flex gap-1 shrink-0">
                              <Badge variant={insight.impact === "high" ? "destructive" : insight.impact === "medium" ? "secondary" : "outline"}>
                                {insight.impact}
                              </Badge>
                              {insight.category && <Badge variant="outline">{insight.category}</Badge>}
                            </div>
                          </div>
                          {insight.actionable_recommendation && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {insight.actionable_recommendation}
                            </p>
                          )}
                          {insight.products_affected && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Affects {insight.products_affected} products
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Customer Personas */}
              {rec.review_intelligence.customer_personas?.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Customer Personas</CardTitle></CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {rec.review_intelligence.customer_personas.map((persona: any, i: number) => (
                        <div key={i} className="p-4 rounded-lg border">
                          <div className="flex justify-between items-center mb-2">
                            <h4 className="font-medium text-sm">{persona.persona}</h4>
                            {persona.percentage && (
                              <Badge variant="secondary">{persona.percentage}%</Badge>
                            )}
                          </div>
                          {persona.needs?.length > 0 && (
                            <div className="mb-2">
                              <p className="text-xs text-muted-foreground">Needs: {persona.needs.join(", ")}</p>
                            </div>
                          )}
                          <div className="flex gap-3 text-xs text-muted-foreground">
                            {persona.price_sensitivity && <span>Price sensitivity: {persona.price_sensitivity}</span>}
                            {persona.brand_loyalty && <span>Brand loyalty: {persona.brand_loyalty}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Purchase Drivers vs Barriers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader><CardTitle className="text-sm text-green-600">Why People Buy</CardTitle></CardHeader>
                  <CardContent>
                    {rec.review_intelligence.purchase_drivers?.length > 0 ? (
                      <ul className="space-y-2">
                        {rec.review_intelligence.purchase_drivers.map((driver: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                            {driver}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No data available.</p>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-sm text-red-600">Why People Don&apos;t Buy</CardTitle></CardHeader>
                  <CardContent>
                    {rec.review_intelligence.purchase_barriers?.length > 0 ? (
                      <ul className="space-y-2">
                        {rec.review_intelligence.purchase_barriers.map((barrier: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                            {barrier}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No data available.</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Market Gaps */}
              {rec.review_intelligence.market_gaps?.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Market Gaps (Unmet Needs)</CardTitle></CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {rec.review_intelligence.market_gaps.map((gap: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Lightbulb className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                          {gap}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Best/Worst Reviewed Features */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {rec.review_intelligence.best_reviewed_features?.length > 0 && (
                  <Card>
                    <CardHeader><CardTitle className="text-sm text-green-600">Best Reviewed Features</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {rec.review_intelligence.best_reviewed_features.map((f: any, i: number) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span>{f.feature}</span>
                            <Badge variant="secondary">{f.avg_rating_when_mentioned}&#9733;</Badge>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
                {rec.review_intelligence.worst_reviewed_features?.length > 0 && (
                  <Card>
                    <CardHeader><CardTitle className="text-sm text-red-600">Worst Reviewed Features</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {rec.review_intelligence.worst_reviewed_features.map((f: any, i: number) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span>{f.feature}</span>
                            <Badge variant="destructive">{f.avg_rating_when_mentioned}&#9733;</Badge>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No review intelligence available.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Product Strategy Tab */}
      {tab === "product" && (
        <div className="space-y-6">
          {rec.product_description && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Differentiation Strategy</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{rec.product_description}</p>
              </CardContent>
            </Card>
          )}

          {rec.differentiation_features && rec.differentiation_features.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Key Features</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {rec.differentiation_features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Lightbulb className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                      {typeof feature === "string" ? feature : JSON.stringify(feature)}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle className="text-lg">Unit Economics</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-xs text-muted-foreground">Landed Cost</p>
                  <p className="text-xl font-bold mt-1">{rec.best_landed_cost ? formatCurrency(rec.best_landed_cost) : "—"}</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-xs text-muted-foreground">Sale Price</p>
                  <p className="text-xl font-bold mt-1">{rec.recommended_sale_price ? formatCurrency(rec.recommended_sale_price) : "—"}</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-xs text-muted-foreground">Net Margin</p>
                  <p className="text-xl font-bold mt-1">{rec.estimated_net_margin_pct ? formatPercent(rec.estimated_net_margin_pct) : "—"}</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-xs text-muted-foreground">Launch Capital</p>
                  <p className="text-xl font-bold mt-1">{rec.total_launch_capital ? formatCurrency(rec.total_launch_capital) : "—"}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Product Blueprint Tab */}
      {tab === "blueprint" && (
        <div className="space-y-6">
          {rec.product_blueprint ? (
            <>
              {/* Strategy Summary */}
              {rec.product_blueprint.product_blueprint?.strategy_summary && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Strategy Summary</CardTitle></CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed">{rec.product_blueprint.product_blueprint.strategy_summary}</p>
                    <div className="flex gap-4 mt-4">
                      {rec.product_blueprint.product_blueprint.target_price_point > 0 && (
                        <div className="text-center p-3 rounded-lg bg-muted">
                          <p className="text-xs text-muted-foreground">Target Price</p>
                          <p className="text-lg font-bold">{formatCurrency(rec.product_blueprint.product_blueprint.target_price_point)}</p>
                        </div>
                      )}
                      {rec.product_blueprint.product_blueprint.target_rating > 0 && (
                        <div className="text-center p-3 rounded-lg bg-muted">
                          <p className="text-xs text-muted-foreground">Target Rating</p>
                          <p className="text-lg font-bold">{rec.product_blueprint.product_blueprint.target_rating}★</p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Improvement Priorities */}
              {rec.product_blueprint.improvement_priorities?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Improvement Priorities</CardTitle>
                    <CardDescription>Ranked by impact: frequency × severity × feasibility × competitive gap</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {rec.product_blueprint.improvement_priorities.map((p: any, i: number) => (
                        <div key={i} className="p-4 rounded-lg border">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="flex items-center justify-center h-6 w-6 rounded-full bg-primary text-primary-foreground text-xs font-bold">
                                {p.rank || i + 1}
                              </span>
                              <h4 className="font-medium text-sm">{p.improvement}</h4>
                            </div>
                            <Badge variant={p.priority_score >= 70 ? "default" : "secondary"}>
                              {p.priority_score}/100
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mb-2">
                            Addresses: {p.addresses_complaint} ({p.category})
                          </p>
                          <div className="grid grid-cols-4 gap-2 text-xs">
                            <div className="text-center p-1 rounded bg-muted">
                              <div className="text-muted-foreground">Frequency</div>
                              <div className="font-semibold">{p.frequency_score}</div>
                            </div>
                            <div className="text-center p-1 rounded bg-muted">
                              <div className="text-muted-foreground">Severity</div>
                              <div className="font-semibold">{p.severity_score}</div>
                            </div>
                            <div className="text-center p-1 rounded bg-muted">
                              <div className="text-muted-foreground">Feasibility</div>
                              <div className="font-semibold">{p.feasibility_score}</div>
                            </div>
                            <div className="text-center p-1 rounded bg-muted">
                              <div className="text-muted-foreground">Gap</div>
                              <div className="font-semibold">{p.competitive_gap_score}</div>
                            </div>
                          </div>
                          {p.estimated_cost_impact && (
                            <p className="text-xs text-muted-foreground mt-2">
                              Cost impact: {p.estimated_cost_impact} | Expected uplift: {p.expected_review_uplift}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Must-Have Improvements */}
              {rec.product_blueprint.product_blueprint?.must_have_improvements?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Must-Have Improvements</CardTitle>
                    <CardDescription>Critical changes to beat competitors</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {rec.product_blueprint.product_blueprint.must_have_improvements.map((imp: any, i: number) => (
                        <div key={i} className="p-4 rounded-lg border">
                          <h4 className="font-medium text-sm mb-1">{imp.improvement}</h4>
                          <p className="text-xs text-muted-foreground mb-2">{imp.why}</p>
                          <div className="flex items-center gap-4 text-xs">
                            <span>
                              <Star className="inline h-3 w-3 mr-1" />
                              Supplier: <span className="text-primary">{imp.supplier_talking_point}</span>
                            </span>
                          </div>
                          <div className="flex gap-2 mt-2">
                            <Badge variant="secondary">Cost: {imp.cost_impact}</Badge>
                            <Badge variant="secondary">{imp.competitors_failing} competitors failing</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Differentiators */}
              {rec.product_blueprint.product_blueprint?.differentiators?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Differentiators</CardTitle>
                    <CardDescription>Unique features no competitor has</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {rec.product_blueprint.product_blueprint.differentiators.map((d: any, i: number) => (
                        <div key={i} className="p-4 rounded-lg border">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-medium text-sm">{d.feature}</h4>
                            <Badge variant="secondary">Cost: {d.cost_impact}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">Source: {d.source}</p>
                          <p className="text-xs mt-1">
                            <Megaphone className="inline h-3 w-3 mr-1" />
                            {d.marketing_angle}
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Weakness Matrix */}
              {rec.product_blueprint.weakness_matrix?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Competitor Weakness Matrix</CardTitle>
                    <CardDescription>Complaints mapped across competitors</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-left">
                            <th className="pb-2 pr-4">Complaint</th>
                            <th className="pb-2 pr-4">Category</th>
                            <th className="pb-2 pr-4 text-center">Affected</th>
                            <th className="pb-2 pr-4 text-center">%</th>
                            <th className="pb-2 text-center">Severity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rec.product_blueprint.weakness_matrix.map((w: any, i: number) => (
                            <tr key={i} className="border-b last:border-0">
                              <td className="py-2 pr-4">{w.complaint}</td>
                              <td className="py-2 pr-4 text-muted-foreground">{w.category}</td>
                              <td className="py-2 pr-4 text-center">{w.competitors_affected}/{w.total_competitors}</td>
                              <td className="py-2 pr-4 text-center">{w.pct_affected}%</td>
                              <td className="py-2 text-center">
                                <Badge variant={w.severity === "critical" || w.severity === "high" ? "destructive" : "secondary"}>
                                  {w.severity}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Listing Angles */}
              {rec.product_blueprint.listing_angles?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Listing Angles</CardTitle>
                    <CardDescription>Marketing angles that exploit competitor weaknesses</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {rec.product_blueprint.listing_angles.map((a: any, i: number) => (
                        <div key={i} className="p-4 rounded-lg border">
                          <h4 className="font-medium text-sm">{a.angle}</h4>
                          <p className="text-xs text-muted-foreground mt-1">Exploits: {a.addresses}</p>
                          {a.suggested_bullet && (
                            <p className="text-xs mt-2 p-2 bg-muted rounded italic">&ldquo;{a.suggested_bullet}&rdquo;</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Quality Benchmarks */}
              {rec.product_blueprint.product_blueprint?.quality_benchmarks?.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Quality Benchmarks</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {rec.product_blueprint.product_blueprint.quality_benchmarks.map((q: any, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-sm p-3 rounded border">
                          <ShieldCheck className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                          <div>
                            <p className="font-medium">{q.benchmark}</p>
                            <p className="text-xs text-muted-foreground">{q.reason}</p>
                            {q.test_method && <p className="text-xs text-muted-foreground mt-1">Test: {q.test_method}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No product blueprint available. Blueprint is generated from competitor review analysis.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Financials Tab */}
      {tab === "financials" && (
        <div className="space-y-6">
          {rec.financial_report ? (
            <>
              {/* FAIL Warning Banner */}
              {rec.confidence_tier === "FAIL" && (
                <Card className="border-destructive/50 bg-destructive/5">
                  <CardContent className="p-4 flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-destructive text-sm">
                        This niche failed hard filters — financials are risk-adjusted
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Sales projections have been reduced to account for competitive barriers
                        {rec.risk_flags?.fail_reasons?.length > 0 && (
                          <> ({rec.risk_flags.fail_reasons.join(", ")})</>
                        )}. Actual performance may be worse than shown. The unit economics are
                        accurate, but the sales volume assumptions are optimistic for a FAIL-tier niche.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Verdict Banner */}
              {rec.financial_report.key_metrics && (
                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <Badge variant={
                          rec.financial_report.key_metrics.verdict === "PROFITABLE" ? "default"
                          : rec.financial_report.key_metrics.verdict === "MARGINAL" ? "secondary"
                          : "destructive"
                        } className="text-sm px-3 py-1">
                          {rec.financial_report.key_metrics.verdict}
                        </Badge>
                        <p className="text-sm text-muted-foreground mt-2">
                          Annual ROI: {rec.financial_report.key_metrics.annual_roi_pct}% | Break-even: Week {rec.financial_report.key_metrics.break_even_week_base}
                        </p>
                        {rec.financial_report.key_metrics.risk_warning && (
                          <p className="text-xs text-destructive mt-1">
                            {rec.financial_report.key_metrics.risk_warning}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold">{formatCurrency(rec.financial_report.key_metrics.annual_profit_base)}</p>
                        <p className="text-xs text-muted-foreground">Annual profit (base)</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Per-Unit P&L Waterfall */}
              {rec.financial_report.per_unit_economics && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Per-Unit P&L Breakdown</CardTitle>
                    <CardDescription>Every cost from factory to customer&apos;s door</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const u = rec.financial_report.per_unit_economics;
                      const c = u.costs || {};
                      const rows = [
                        { label: "Selling Price", value: u.selling_price, bold: true },
                        { label: "Coupon Discount", value: -u.coupon_discount, indent: true, hide: !u.coupon_discount },
                        { label: "Effective Revenue", value: u.effective_revenue, bold: true },
                        { divider: true, label: "LANDED COST" },
                        { label: "FOB Cost (supplier)", value: c.fob_cost, indent: true },
                        { label: "Shipping", value: c.shipping, indent: true },
                        { label: "Customs Duty", value: c.customs_duty, indent: true },
                        { label: "Section 301 Tariff", value: c.section_301_tariff, indent: true },
                        { label: "Insurance", value: c.insurance, indent: true },
                        { label: "Inspection", value: c.inspection, indent: true },
                        { label: "Freight Forwarding", value: c.freight_forwarding, indent: true },
                        { label: "FBA Prep + Inbound", value: (c.fba_prep || 0) + (c.fba_inbound || 0), indent: true },
                        { label: "Total Landed Cost", value: c.total_landed_cost, bold: true, negative: true },
                        { divider: true, label: "AMAZON FEES" },
                        { label: `Referral Fee (${c.referral_fee_pct || 15}%)`, value: c.referral_fee, indent: true },
                        { label: "FBA Fulfillment Fee", value: c.fba_fulfillment_fee, indent: true },
                        { label: "Monthly Storage", value: c.monthly_storage, indent: true },
                        { label: `Returns (3%)`, value: c.returns_cost, indent: true },
                        { label: "Total Amazon Fees", value: c.total_amazon_fees, bold: true, negative: true },
                        { divider: true, label: "PROFIT" },
                        { label: "Pre-PPC Profit", value: u.pre_ppc_profit, bold: true, highlight: true },
                        { label: "Pre-PPC Margin", value: `${u.pre_ppc_margin_pct}%`, isPercent: true },
                        { label: "PPC Cost/Unit", value: c.ppc_cost_per_unit, indent: true, negative: true },
                        { label: "Post-PPC Profit", value: u.post_ppc_profit, bold: true, highlight: true },
                        { label: "Post-PPC Margin", value: `${u.post_ppc_margin_pct}%`, isPercent: true },
                      ];
                      return (
                        <div className="space-y-1">
                          {rows.filter((r: any) => !r.hide).map((r: any, i: number) => {
                            if (r.divider) return <div key={i} className="pt-3 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wide border-t mt-2">{r.label}</div>;
                            return (
                              <div key={i} className={`flex justify-between text-sm py-0.5 ${r.indent ? "pl-4" : ""} ${r.bold ? "font-semibold" : ""} ${r.highlight ? "text-primary" : ""}`}>
                                <span>{r.label}</span>
                                <span className={r.negative ? "text-rejected" : ""}>
                                  {r.isPercent ? r.value : formatCurrency(r.value || 0)}
                                </span>
                              </div>
                            );
                          })}
                          <div className="flex justify-between text-sm py-1 mt-2 border-t pt-2">
                            <span className="font-semibold">Break-Even Price</span>
                            <span>{formatCurrency(u.break_even_price || 0)}</span>
                          </div>
                          <div className="flex justify-between text-sm py-1">
                            <span className="font-semibold">ROI per Unit</span>
                            <span>{u.roi_per_unit_pct}%</span>
                          </div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
              )}

              {/* Launch Capital */}
              {rec.financial_report.launch_capital && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Launch Capital Required</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const lc = rec.financial_report.launch_capital;
                      const sections = [
                        { label: `Inventory (${lc.inventory?.quantity || 500} units)`, value: lc.inventory?.total },
                        { label: "PPC Budget (90 days)", value: lc.advertising?.ppc_90_day },
                        { label: "Coupon Budget", value: lc.advertising?.coupon_budget, hide: !lc.advertising?.coupon_budget },
                        { label: "Vine Enrollment", value: lc.vine_enrollment?.cost },
                        { label: "Photography", value: lc.creative?.photography },
                        { label: "A+ Content Design", value: lc.creative?.a_plus_design },
                        { label: "Samples + Misc", value: (lc.other?.samples || 0) + (lc.other?.misc || 0) },
                      ];
                      return (
                        <div className="space-y-2">
                          {sections.filter((s: any) => !s.hide).map((s, i) => (
                            <div key={i} className="flex justify-between text-sm">
                              <span>{s.label}</span>
                              <span>{formatCurrency(s.value || 0)}</span>
                            </div>
                          ))}
                          <div className="flex justify-between text-sm font-bold border-t pt-2 mt-2">
                            <span>Total Launch Capital</span>
                            <span>{formatCurrency(lc.total_launch_capital || 0)}</span>
                          </div>
                          {lc.recommended_buffer_15pct > 0 && (
                            <div className="flex justify-between text-sm text-muted-foreground">
                              <span>+ 15% Buffer</span>
                              <span>{formatCurrency(lc.recommended_buffer_15pct)}</span>
                            </div>
                          )}
                          <div className="flex justify-between text-sm font-bold text-primary">
                            <span>Total with Buffer</span>
                            <span>{formatCurrency(lc.total_with_buffer || lc.total_launch_capital || 0)}</span>
                          </div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
              )}

              {/* Scenario Comparison */}
              {rec.financial_report.scenarios && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Annual Scenarios</CardTitle>
                    <CardDescription>Bull (1.3x sales) / Base (1x) / Bear (0.7x)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left">
                            <th className="pb-2 pr-4">Metric</th>
                            <th className="pb-2 pr-4 text-center text-tier1">Bull</th>
                            <th className="pb-2 pr-4 text-center text-primary">Base</th>
                            <th className="pb-2 text-center text-rejected">Bear</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[
                            { label: "Annual Units", key: "annual_units", fmt: "num" },
                            { label: "Annual Revenue", key: "annual_revenue", fmt: "currency" },
                            { label: "Annual Profit", key: "annual_profit", fmt: "currency" },
                            { label: "ROI", key: "roi_pct", fmt: "pct" },
                            { label: "Break-Even Week", key: "break_even_week", fmt: "week" },
                          ].map((row) => (
                            <tr key={row.key} className="border-b last:border-0">
                              <td className="py-2 pr-4 font-medium">{row.label}</td>
                              {["bull", "base", "bear"].map((s) => {
                                const v = rec.financial_report.scenarios[s]?.[row.key];
                                let display = "—";
                                if (v != null) {
                                  if (row.fmt === "currency") display = formatCurrency(v);
                                  else if (row.fmt === "pct") display = `${v}%`;
                                  else if (row.fmt === "week") display = `Week ${v}`;
                                  else display = v.toLocaleString();
                                }
                                return <td key={s} className="py-2 pr-4 text-center">{display}</td>;
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Reorder Planning */}
              {rec.financial_report.reorder_plan && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Reorder Planning</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {[
                        { label: "Daily Sell-Through", value: `${rec.financial_report.reorder_plan.sell_through_rate_units_per_day} units/day` },
                        { label: "Days of Inventory", value: `${rec.financial_report.reorder_plan.days_of_inventory} days` },
                        { label: "Lead Time", value: `${rec.financial_report.reorder_plan.lead_time_days} days` },
                        { label: "Reorder Trigger", value: `${rec.financial_report.reorder_plan.reorder_trigger_units} units left` },
                        { label: "Reorder At", value: rec.financial_report.reorder_plan.reorder_trigger_date_approx },
                        { label: "Reorder Qty", value: `${rec.financial_report.reorder_plan.recommended_reorder_qty} units` },
                        { label: "Reorder Cost", value: formatCurrency(rec.financial_report.reorder_plan.reorder_cost || 0) },
                        { label: "Year 1 Inventory", value: formatCurrency(rec.financial_report.reorder_plan.total_year_1_inventory_investment || 0) },
                      ].map((item, i) => (
                        <div key={i} className="text-center p-3 rounded-lg bg-muted">
                          <p className="text-xs text-muted-foreground">{item.label}</p>
                          <p className="font-semibold mt-1">{item.value}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Cash Flow Timeline */}
              {rec.financial_report.cash_flow_timeline?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Cash Flow Timeline</CardTitle>
                    <CardDescription>When money goes out and comes back in</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-auto max-h-96">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-background">
                          <tr className="border-b text-left">
                            <th className="pb-2 pr-3">Week</th>
                            <th className="pb-2 pr-3">Event</th>
                            <th className="pb-2 pr-3 text-right text-rejected">Out</th>
                            <th className="pb-2 pr-3 text-right text-tier1">In</th>
                            <th className="pb-2 text-right">Balance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rec.financial_report.cash_flow_timeline.map((row: any, i: number) => (
                            <tr key={i} className="border-b last:border-0">
                              <td className="py-1.5 pr-3 font-mono">{row.week >= 0 ? `+${row.week}` : row.week}</td>
                              <td className="py-1.5 pr-3">{row.event}</td>
                              <td className="py-1.5 pr-3 text-right text-rejected">{row.cash_out ? formatCurrency(row.cash_out) : ""}</td>
                              <td className="py-1.5 pr-3 text-right text-tier1">{row.cash_in ? formatCurrency(row.cash_in) : ""}</td>
                              <td className={`py-1.5 text-right font-medium ${row.balance >= 0 ? "text-tier1" : "text-rejected"}`}>
                                {formatCurrency(row.balance)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Monthly P&L */}
              {rec.financial_report.monthly_summary?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Monthly P&L (12 Months)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-left">
                            <th className="pb-2 pr-2">Mo</th>
                            <th className="pb-2 pr-2 text-right">Units</th>
                            <th className="pb-2 pr-2 text-right">Revenue</th>
                            <th className="pb-2 pr-2 text-right">COGS</th>
                            <th className="pb-2 pr-2 text-right">Amazon Fees</th>
                            <th className="pb-2 pr-2 text-right">PPC</th>
                            <th className="pb-2 pr-2 text-right">Net Profit</th>
                            <th className="pb-2 pr-2 text-right">Margin</th>
                            <th className="pb-2 text-right">Cumulative</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rec.financial_report.monthly_summary.map((m: any) => (
                            <tr key={m.month} className="border-b last:border-0">
                              <td className="py-1.5 pr-2">{m.month}</td>
                              <td className="py-1.5 pr-2 text-right">{m.units_sold}</td>
                              <td className="py-1.5 pr-2 text-right">{formatCurrency(m.revenue)}</td>
                              <td className="py-1.5 pr-2 text-right">{formatCurrency(m.cogs)}</td>
                              <td className="py-1.5 pr-2 text-right">{formatCurrency(m.amazon_fees)}</td>
                              <td className="py-1.5 pr-2 text-right">{formatCurrency(m.ppc_spend)}</td>
                              <td className={`py-1.5 pr-2 text-right font-medium ${m.net_profit >= 0 ? "text-tier1" : "text-rejected"}`}>
                                {formatCurrency(m.net_profit)}
                              </td>
                              <td className="py-1.5 pr-2 text-right">{m.margin_pct}%</td>
                              <td className={`py-1.5 text-right ${m.cumulative_profit >= 0 ? "text-tier1" : "text-rejected"}`}>
                                {formatCurrency(m.cumulative_profit)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            /* Fallback to basic stats if no full financial report */
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Unit Economics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                  <div>
                    <p className="text-xs text-muted-foreground">Landed Cost</p>
                    <p className="text-lg font-bold">{rec.best_landed_cost ? formatCurrency(rec.best_landed_cost) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Recommended Price</p>
                    <p className="text-lg font-bold">{rec.recommended_sale_price ? formatCurrency(rec.recommended_sale_price) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Post-PPC Margin</p>
                    <p className="text-lg font-bold">{rec.estimated_net_margin_pct ? formatPercent(rec.estimated_net_margin_pct) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">PPC Budget (30d)</p>
                    <p className="text-lg font-bold">{rec.ppc_budget_30d ? formatCurrency(rec.ppc_budget_30d) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Break-Even ACOS</p>
                    <p className="text-lg font-bold">{rec.break_even_acos ? `${rec.break_even_acos}%` : "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Total Launch Capital</p>
                    <p className="text-lg font-bold">{rec.total_launch_capital ? formatCurrency(rec.total_launch_capital) : "—"}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Marketing Tab */}
      {tab === "marketing" && (
        <div className="space-y-6">
          {rec.marketing_channels ? (
            <Card>
              <CardHeader><CardTitle className="text-lg">Marketing Channels</CardTitle></CardHeader>
              <CardContent>
                {Array.isArray(rec.marketing_channels) ? (
                  <div className="space-y-4">
                    {rec.marketing_channels.map((ch: any, i: number) => (
                      <div key={i} className="p-4 rounded-lg border">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium">{ch.channel || ch.platform || `Channel ${i + 1}`}</h4>
                          {ch.expected_roi && <Badge variant="secondary">{ch.expected_roi} ROI</Badge>}
                        </div>
                        {ch.strategy && <p className="text-sm text-muted-foreground">{ch.strategy}</p>}
                        {ch.budget_amount && (
                          <p className="text-sm mt-1">Budget: {formatCurrency(ch.budget_amount)}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-96">
                    {JSON.stringify(rec.marketing_channels, null, 2)}
                  </pre>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No marketing data available.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Launch Playbook Tab */}
      {tab === "playbook" && (
        <div className="space-y-6">
          {rec.launch_playbook ? (
            <>
              {rec.launch_playbook.playbook_name && (
                <div>
                  <h2 className="text-xl font-bold">{rec.launch_playbook.playbook_name}</h2>
                  {rec.launch_playbook.total_budget && (
                    <p className="text-muted-foreground">Total 12-week budget: {formatCurrency(rec.launch_playbook.total_budget)}</p>
                  )}
                </div>
              )}

              {rec.launch_playbook.pre_launch_checklist && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Pre-Launch Checklist</CardTitle></CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {rec.launch_playbook.pre_launch_checklist.map((item: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <CheckCircle2 className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {rec.launch_playbook.weeks && (
                <Card>
                  <CardHeader><CardTitle className="text-lg">Week-by-Week Plan</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {rec.launch_playbook.weeks.map((week: any) => (
                        <div key={week.week} className="p-4 rounded-lg border">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="font-semibold">Week {week.week}: {week.theme}</h4>
                            {week.budget_allocation && (
                              <span className="text-xs text-muted-foreground">
                                PPC: {formatCurrency(week.budget_allocation.ppc || 0)}
                              </span>
                            )}
                          </div>
                          {week.priorities && (
                            <ul className="text-sm space-y-1">
                              {week.priorities.map((p: string, i: number) => (
                                <li key={i} className="text-muted-foreground">- {p}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No launch playbook available.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </motion.div>
  );
}
