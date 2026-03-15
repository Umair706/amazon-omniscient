"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
  generated_at: string;
}

type TabId = "overview" | "product" | "financials" | "marketing" | "playbook";

export default function OpportunityBriefPage() {
  const params = useParams();
  const id = params.id as string;

  const [rec, setRec] = useState<RecommendationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    api
      .get(`/api/v1/recommendations/${id}`)
      .then((res) => setRec(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!rec) return <div className="text-muted-foreground">Recommendation not found.</div>;

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "product", label: "Product Strategy" },
    { id: "financials", label: "Unit Economics" },
    { id: "marketing", label: "Marketing" },
    { id: "playbook", label: "Launch Playbook" },
  ];

  return (
    <div className="space-y-6">
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
        <StatCard title="Net Margin" value={rec.estimated_net_margin_pct ? formatPercent(rec.estimated_net_margin_pct) : "—"} icon={TrendingUp} />
        <StatCard title="Break-Even" value={rec.break_even_week_base ? `Week ${rec.break_even_week_base}` : "—"} icon={Clock} />
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

      {/* Financials Tab */}
      {tab === "financials" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Detailed Unit Economics</CardTitle>
            <CardDescription>View this niche's financial projections on the Niche Detail page.</CardDescription>
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
    </div>
  );
}
