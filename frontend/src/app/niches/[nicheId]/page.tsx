"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBadge } from "@/components/score-badge";
import { StatCard } from "@/components/stat-card";
import { ScoreRadar, ProfitChart, SalesChart, CompetitorBarChart } from "@/components/charts";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import {
  TrendingUp,
  DollarSign,
  BarChart3,
  Star,
  ShoppingCart,
  Users,
  ArrowLeft,
  ExternalLink,
  Search,
} from "lucide-react";

interface NicheDetail {
  id: number;
  name: string;
  keyword: string;
  status: string;
  opportunity_score: number | null;
  confidence_tier: string | null;
  demand_score: number | null;
  competition_score: number | null;
  revenue_score: number | null;
  margin_score: number | null;
  trend_score: number | null;
  review_feasibility_score: number | null;
  supplier_score: number | null;
  ppc_viability_score: number | null;
  launch_feasibility_score: number | null;
  avg_bsr: number | null;
  avg_price: number | null;
  avg_rating: number | null;
  avg_review_count: number | null;
  total_monthly_revenue: number | null;
  estimated_monthly_sales: number | null;
  top_keyword_search_volume: number | null;
  is_seasonal: boolean;
  hard_filter_passed: boolean | null;
  hard_filter_fail_reasons: string[];
  analyzed_at: string | null;
}

interface ProductItem {
  id: number;
  asin: string;
  title: string;
  current_price: number | null;
  bsr_current: number | null;
  current_bsr: number | null;
  rating: number | null;
  review_count: number;
  main_image_url: string | null;
  image_url: string | null;
  estimated_daily_sales: number | null;
  sales_velocity_trend: string | null;
  search_position: number | null;
  variation_count: number | null;
  seller_count: number | null;
  deal_badge: string | null;
  amazons_choice_keyword: string | null;
}

interface CompetitorItem {
  id: number;
  asin: string;
  title: string;
  listing_quality_score: number | null;
  review_count: number;
  rating: number | null;
  vulnerabilities: string[];
}

interface KeywordItem {
  id: number;
  keyword: string;
  search_volume: number | null;
  competition_level: string | null;
  sponsored_result_count: number | null;
  relevance_score: number | null;
  avg_cpc: number | null;
  source: string | null;
}

type TabId = "overview" | "products" | "competitors" | "keywords" | "financials";

function VelocityBadge({ trend }: { trend: string | null }) {
  if (!trend) return <span className="text-muted-foreground">—</span>;
  const colors: Record<string, string> = {
    increasing: "text-tier1",
    stable: "text-muted-foreground",
    decreasing: "text-rejected",
  };
  const arrows: Record<string, string> = {
    increasing: "↑",
    stable: "→",
    decreasing: "↓",
  };
  return (
    <span className={`font-medium ${colors[trend] || "text-muted-foreground"}`}>
      {arrows[trend] || ""} {trend}
    </span>
  );
}

function RelevanceBar({ score }: { score: number | null }) {
  if (score == null) return <span className="text-muted-foreground">—</span>;
  const numScore = Number(score);
  const color = numScore >= 70 ? "bg-tier1" : numScore >= 40 ? "bg-tier3" : "bg-rejected";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 rounded-full bg-secondary overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${numScore}%` }} />
      </div>
      <span className="text-xs font-medium">{Math.round(numScore)}</span>
    </div>
  );
}

function CompetitionBadge({ level }: { level: string | null }) {
  if (!level) return <span className="text-muted-foreground">—</span>;
  const colors: Record<string, string> = {
    high: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || "bg-secondary text-secondary-foreground"}`}>
      {level}
    </span>
  );
}

export default function NicheDetailPage() {
  const params = useParams();
  const nicheId = params.nicheId as string;

  const [tab, setTab] = useState<TabId>("overview");
  const [niche, setNiche] = useState<NicheDetail | null>(null);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [competitors, setCompetitors] = useState<CompetitorItem[]>([]);
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [financials, setFinancials] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [nicheVelocity, setNicheVelocity] = useState<any>(null);

  useEffect(() => {
    if (!nicheId) return;
    setLoading(true);

    Promise.all([
      api.get(`/api/v1/niches/${nicheId}`).catch(() => ({ data: null })),
      api.get(`/api/v1/niches/${nicheId}/products`).catch(() => ({ data: { items: [] } })),
      api.get(`/api/v1/niches/${nicheId}/competitors`).catch(() => ({ data: { items: [] } })),
      api.get(`/api/v1/niches/${nicheId}/financials`).catch(() => ({ data: { items: [] } })),
      api.get(`/api/v1/niches/${nicheId}/keywords`).catch(() => ({ data: [] })),
      api.get(`/api/v1/niches/${nicheId}/velocity`).catch(() => ({ data: null })),
    ]).then(([nicheRes, productsRes, competitorsRes, financialsRes, keywordsRes, velocityRes]) => {
      setNiche(nicheRes.data);
      setProducts(productsRes.data.items || []);
      setCompetitors(competitorsRes.data.items || []);
      setFinancials(financialsRes.data);
      setKeywords(Array.isArray(keywordsRes.data) ? keywordsRes.data : []);
      setNicheVelocity(velocityRes.data);
      setLoading(false);
    });
  }, [nicheId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!niche) {
    return <div className="text-muted-foreground">Niche not found.</div>;
  }

  const subScores: Record<string, number> = {
    demand: niche.demand_score ?? 0,
    competition: niche.competition_score ?? 0,
    revenue: niche.revenue_score ?? 0,
    margin: niche.margin_score ?? 0,
    trend: niche.trend_score ?? 0,
    review_feasibility: niche.review_feasibility_score ?? 0,
    supplier: niche.supplier_score ?? 0,
    ppc_viability: niche.ppc_viability_score ?? 0,
    launch_feasibility: niche.launch_feasibility_score ?? 0,
  };

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "products", label: `Products (${products.length})` },
    { id: "competitors", label: `Competitors (${competitors.length})` },
    { id: "keywords", label: `Keywords (${keywords.length})` },
    { id: "financials", label: "Financials" },
  ];

  const projectionItems = financials?.items || [];
  const bullData = projectionItems.filter((p: any) => p.scenario === "bull");
  const baseData = projectionItems.filter((p: any) => p.scenario === "base");
  const bearData = projectionItems.filter((p: any) => p.scenario === "bear");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => window.history.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2">
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          <h1 className="text-3xl font-bold">{niche.name || niche.keyword}</h1>
          <p className="text-muted-foreground mt-1">{niche.keyword}</p>
        </div>
        {niche.opportunity_score != null && (
          <ScoreBadge score={niche.opportunity_score} tier={niche.confidence_tier || "LOW"} size="lg" />
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard title="Avg Price" value={niche.avg_price ? formatCurrency(niche.avg_price) : "—"} icon={DollarSign} />
        <StatCard title="Avg BSR" value={niche.avg_bsr?.toLocaleString() || "—"} icon={TrendingUp} />
        <StatCard title="Monthly Sales" value={niche.estimated_monthly_sales?.toLocaleString() || "—"} icon={ShoppingCart} />
        <StatCard title="Search Volume" value={niche.top_keyword_search_volume?.toLocaleString() || "—"} icon={BarChart3} />
        <StatCard title="Avg Rating" value={niche.avg_rating ? `${niche.avg_rating}/5` : "—"} icon={Star} />
        <StatCard title="Avg Reviews" value={niche.avg_review_count?.toLocaleString() || "—"} icon={Users} />
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex gap-4">
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

      {/* Tab Content */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle className="text-lg">Sub-Score Radar</CardTitle></CardHeader>
            <CardContent>
              <ScoreRadar subScores={subScores} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-lg">Hard Filters</CardTitle></CardHeader>
            <CardContent>
              {niche.hard_filter_fail_reasons && niche.hard_filter_fail_reasons.length > 0 ? (
                <div className="space-y-2">
                  <Badge variant="destructive">Failed</Badge>
                  <ul className="text-sm space-y-1 mt-2">
                    {niche.hard_filter_fail_reasons.map((reason, i) => (
                      <li key={i} className="text-rejected">{reason}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div>
                  <Badge>All Passed</Badge>
                  <p className="text-sm text-muted-foreground mt-2">All 8 hard disqualification filters passed.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {nicheVelocity && nicheVelocity.total_estimated_daily_sales > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Sales Velocity</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-2xl font-bold">{Math.round(nicheVelocity.total_estimated_daily_sales)}</div>
                    <div className="text-xs text-muted-foreground">Est. Daily Sales</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">{Math.round(nicheVelocity.total_estimated_monthly_sales).toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">Est. Monthly Sales</div>
                  </div>
                  <div>
                    <VelocityBadge trend={nicheVelocity.velocity_trend} />
                    <div className="text-xs text-muted-foreground mt-1">Trend</div>
                  </div>
                  <div>
                    <div className="text-lg font-medium">{nicheVelocity.products_with_velocity_data || 0}/{nicheVelocity.product_count || 0}</div>
                    <div className="text-xs text-muted-foreground">Products Tracked</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className={nicheVelocity && nicheVelocity.total_estimated_daily_sales > 0 ? "" : "lg:col-span-2"}>
            <CardHeader><CardTitle className="text-lg">Sub-Score Breakdown</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 md:grid-cols-5 gap-4">
                {Object.entries(subScores).map(([key, value]) => (
                  <div key={key} className="text-center">
                    <div className="text-2xl font-bold">{Math.round(value)}</div>
                    <div className="text-xs text-muted-foreground capitalize">{key.replace(/_/g, " ")}</div>
                    <div className="mt-1 h-2 rounded-full bg-secondary overflow-hidden">
                      <div
                        className={`h-full rounded-full ${value >= 70 ? "bg-tier1" : value >= 40 ? "bg-tier3" : "bg-rejected"}`}
                        style={{ width: `${value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "products" && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-4">#</th>
                    <th className="p-4">Product</th>
                    <th className="p-4">Price</th>
                    <th className="p-4">BSR</th>
                    <th className="p-4">Est. Daily Sales</th>
                    <th className="p-4">Velocity</th>
                    <th className="p-4">Rating</th>
                    <th className="p-4">Reviews</th>
                    <th className="p-4">Badges</th>
                    <th className="p-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.length === 0 ? (
                    <tr><td colSpan={10} className="p-8 text-center text-muted-foreground">No products found.</td></tr>
                  ) : (
                    products.map((p) => (
                      <tr key={p.id} className="border-b last:border-0 hover:bg-muted/50">
                        <td className="p-4 text-center text-xs text-muted-foreground">
                          {p.search_position != null ? p.search_position : "—"}
                        </td>
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            {(p.main_image_url || p.image_url) && (
                              <img src={p.main_image_url || p.image_url || ""} alt="" className="w-10 h-10 rounded object-cover" />
                            )}
                            <div className="min-w-0">
                              <a href={`/products/${p.asin}`} className="font-medium line-clamp-2 max-w-[280px] hover:text-primary transition-colors">
                                {p.title}
                              </a>
                              <span className="block text-xs font-mono text-muted-foreground mt-0.5">{p.asin}</span>
                            </div>
                          </div>
                        </td>
                        <td className="p-4">{p.current_price ? formatCurrency(p.current_price) : "—"}</td>
                        <td className="p-4">{(p.bsr_current || p.current_bsr)?.toLocaleString() || "—"}</td>
                        <td className="p-4">{p.estimated_daily_sales != null ? p.estimated_daily_sales : "—"}</td>
                        <td className="p-4"><VelocityBadge trend={p.sales_velocity_trend} /></td>
                        <td className="p-4">{p.rating ? `${p.rating}/5` : "—"}</td>
                        <td className="p-4">{p.review_count?.toLocaleString() || "0"}</td>
                        <td className="p-4">
                          <div className="flex flex-wrap gap-1">
                            {p.deal_badge && (
                              <Badge className="bg-red-500 text-white text-[10px] px-1.5 py-0">{p.deal_badge}</Badge>
                            )}
                            {p.amazons_choice_keyword && (
                              <Badge className="bg-orange-500 text-white text-[10px] px-1.5 py-0">AC</Badge>
                            )}
                            {p.variation_count != null && p.variation_count > 1 && (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0">{p.variation_count} vars</Badge>
                            )}
                            {p.seller_count != null && p.seller_count > 1 && (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0">{p.seller_count} sellers</Badge>
                            )}
                          </div>
                        </td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <a
                              href={`/products/${p.asin}`}
                              className="text-primary hover:underline text-xs"
                            >
                              Details
                            </a>
                            <a
                              href={`https://amazon.com/dp/${p.asin}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "competitors" && (
        <div className="space-y-6">
          {competitors.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Listing Quality Comparison</CardTitle></CardHeader>
              <CardContent>
                <CompetitorBarChart
                  competitors={competitors.map((c) => ({
                    name: c.title.substring(0, 30),
                    listing_quality_score: c.listing_quality_score ?? 0,
                    review_count: c.review_count,
                    rating: c.rating ?? 0,
                  }))}
                  metric="listing_quality_score"
                />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="p-4">Competitor</th>
                      <th className="p-4">ASIN</th>
                      <th className="p-4">Quality</th>
                      <th className="p-4">Rating</th>
                      <th className="p-4">Reviews</th>
                      <th className="p-4">Vulnerabilities</th>
                    </tr>
                  </thead>
                  <tbody>
                    {competitors.length === 0 ? (
                      <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">No competitor data.</td></tr>
                    ) : (
                      competitors.map((c) => (
                        <tr key={c.id} className="border-b last:border-0 hover:bg-muted/50">
                          <td className="p-4 max-w-[250px]"><span className="line-clamp-2">{c.title}</span></td>
                          <td className="p-4 font-mono text-xs">{c.asin}</td>
                          <td className="p-4">
                            {c.listing_quality_score != null ? (
                              <span className={`font-semibold ${c.listing_quality_score >= 70 ? "text-tier1" : c.listing_quality_score >= 40 ? "text-tier3" : "text-rejected"}`}>
                                {c.listing_quality_score}
                              </span>
                            ) : "—"}
                          </td>
                          <td className="p-4">{c.rating ? `${c.rating}/5` : "—"}</td>
                          <td className="p-4">{c.review_count?.toLocaleString()}</td>
                          <td className="p-4">
                            <div className="flex flex-wrap gap-1">
                              {(c.vulnerabilities || []).slice(0, 3).map((v, i) => (
                                <Badge key={i} variant="outline" className="text-xs">{v}</Badge>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "keywords" && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-4">Keyword</th>
                    <th className="p-4">Est. Search Volume</th>
                    <th className="p-4">Competition</th>
                    <th className="p-4">Sponsored Density</th>
                    <th className="p-4">Est. CPC</th>
                    <th className="p-4">Relevance</th>
                    <th className="p-4">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {keywords.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-muted-foreground">
                        <div className="flex flex-col items-center gap-2">
                          <Search className="h-8 w-8 text-muted-foreground/50" />
                          <span>No keyword data yet. Run an analysis to discover keywords.</span>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    keywords.map((k) => (
                      <tr key={k.id} className="border-b last:border-0 hover:bg-muted/50">
                        <td className="p-4 font-medium">{k.keyword}</td>
                        <td className="p-4">{k.search_volume?.toLocaleString() || "—"}</td>
                        <td className="p-4"><CompetitionBadge level={k.competition_level} /></td>
                        <td className="p-4">{k.sponsored_result_count ?? "—"}</td>
                        <td className="p-4">{k.avg_cpc != null ? `$${Number(k.avg_cpc).toFixed(2)}` : "—"}</td>
                        <td className="p-4"><RelevanceBar score={k.relevance_score != null ? Number(k.relevance_score) : null} /></td>
                        <td className="p-4">
                          <Badge variant="outline" className="text-xs">{k.source || "—"}</Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "financials" && (
        <div className="space-y-6">
          {baseData.length > 0 ? (
            <>
              <Card>
                <CardHeader><CardTitle className="text-lg">Cumulative Profit — Bull / Base / Bear</CardTitle></CardHeader>
                <CardContent>
                  <ProfitChart bull={bullData} base={baseData} bear={bearData} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-lg">Weekly Sales & Review Growth (Base)</CardTitle></CardHeader>
                <CardContent>
                  <SalesChart projections={baseData} />
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No financial projections available. Run a full analysis to generate projections.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
