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
  rating: number | null;
  review_count: number;
  main_image_url: string | null;
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

type TabId = "overview" | "products" | "competitors" | "financials";

export default function NicheDetailPage() {
  const params = useParams();
  const nicheId = params.nicheId as string;

  const [tab, setTab] = useState<TabId>("overview");
  const [niche, setNiche] = useState<NicheDetail | null>(null);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [competitors, setCompetitors] = useState<CompetitorItem[]>([]);
  const [financials, setFinancials] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!nicheId) return;
    setLoading(true);

    Promise.all([
      api.get(`/api/v1/niches/${nicheId}`).catch(() => ({ data: null })),
      api.get(`/api/v1/niches/${nicheId}/products`).catch(() => ({ data: { items: [] } })),
      api.get(`/api/v1/niches/${nicheId}/competitors`).catch(() => ({ data: { items: [] } })),
      api.get(`/api/v1/niches/${nicheId}/financials`).catch(() => ({ data: { items: [] } })),
    ]).then(([nicheRes, productsRes, competitorsRes, financialsRes]) => {
      setNiche(nicheRes.data);
      setProducts(productsRes.data.items || []);
      setCompetitors(competitorsRes.data.items || []);
      setFinancials(financialsRes.data);
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

          <Card className="lg:col-span-2">
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
                    <th className="p-4">Product</th>
                    <th className="p-4">ASIN</th>
                    <th className="p-4">Price</th>
                    <th className="p-4">BSR</th>
                    <th className="p-4">Rating</th>
                    <th className="p-4">Reviews</th>
                    <th className="p-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.length === 0 ? (
                    <tr><td colSpan={7} className="p-8 text-center text-muted-foreground">No products found.</td></tr>
                  ) : (
                    products.map((p) => (
                      <tr key={p.id} className="border-b last:border-0 hover:bg-muted/50">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            {p.main_image_url && (
                              <img src={p.main_image_url} alt="" className="w-10 h-10 rounded object-cover" />
                            )}
                            <span className="font-medium line-clamp-2 max-w-[300px]">{p.title}</span>
                          </div>
                        </td>
                        <td className="p-4 font-mono text-xs">{p.asin}</td>
                        <td className="p-4">{p.current_price ? formatCurrency(p.current_price) : "—"}</td>
                        <td className="p-4">{p.bsr_current?.toLocaleString() || "—"}</td>
                        <td className="p-4">{p.rating ? `${p.rating}/5` : "—"}</td>
                        <td className="p-4">{p.review_count?.toLocaleString() || "0"}</td>
                        <td className="p-4">
                          <a
                            href={`https://amazon.com/dp/${p.asin}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline inline-flex items-center gap-1 text-xs"
                          >
                            Amazon <ExternalLink className="h-3 w-3" />
                          </a>
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
