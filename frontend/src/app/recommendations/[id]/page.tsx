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
  risk_flags: any;
  ppc_strategy: any;
  marketing_channels: any;
  launch_playbook: any;
  product_blueprint: any;
  financial_report: any;
  generated_at: string;
}

type TabId = "overview" | "product" | "blueprint" | "financials" | "marketing" | "playbook";

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
    { id: "product", label: "Product Strategy" },
    { id: "blueprint", label: "Product Blueprint" },
    { id: "financials", label: "Unit Economics" },
    { id: "marketing", label: "Marketing" },
    { id: "playbook", label: "Launch Playbook" },
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
          <h1 className="text-3xl font-bold">Product Opportunity Brief</h1>
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

      {/* Overview Tab */}
      {tab === "overview" && (
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

          {/* Risk Flags */}
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
            </CardContent>
          </Card>
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
