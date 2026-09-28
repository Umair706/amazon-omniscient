import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils";
import { AlertTriangle, Megaphone, Target } from "lucide-react";

interface Phase {
  days?: string;
  daily_budget?: number;
  monthly_budget?: number;
  estimated_acos?: number;
  strategy?: string;
}

interface PpcStrategy {
  avg_cpc?: number;
  total_keywords?: number;
  target_acos?: number;
  phases?: Record<string, Phase>;
  total_90_day_budget?: number;
  top_keywords?: string[];
  break_even?: { break_even_acos?: number; target_acos?: number };
  llm_strategy?: {
    budget_burn_warning?: string;
    kill_criteria?: string;
    campaign_structure?: Array<Record<string, unknown>>;
  };
}

const PHASE_ORDER = ["launch", "growth", "steady_state"];
const PHASE_LABEL: Record<string, string> = {
  launch: "Launch (days 1-30)",
  growth: "Growth (days 31-90)",
  steady_state: "Steady state (day 91+)",
};

// Render the full PPC plan a seller needs to launch ads: budget by phase, the
// ACOS targets, expected spend, and the plain warnings about burning money.
export function PpcPlan({ ppc, marketplace }: { ppc: PpcStrategy | null; marketplace?: string }) {
  if (!ppc || !ppc.phases) return null;
  const money = (v: number | null | undefined) => formatCurrency(v, marketplace);
  const breakEven = ppc.break_even?.break_even_acos ?? null;
  const target = ppc.target_acos ?? ppc.break_even?.target_acos ?? null;
  const burn = ppc.llm_strategy?.budget_burn_warning;
  const kill = ppc.llm_strategy?.kill_criteria;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Megaphone className="h-5 w-5 text-primary" /> PPC plan
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          How to run ads: budget by phase and the ACOS you must beat to profit.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* ACOS targets + spend headline */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground flex items-center gap-1"><Target className="h-3 w-3" /> Break-even ACOS</p>
            <p className="text-lg font-bold">{breakEven != null ? `${breakEven}%` : "—"}</p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Target ACOS</p>
            <p className="text-lg font-bold">{target != null ? `${target}%` : "—"}</p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Avg CPC</p>
            <p className="text-lg font-bold">{ppc.avg_cpc != null ? money(ppc.avg_cpc) : "—"}</p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">90-day ad spend</p>
            <p className="text-lg font-bold">{ppc.total_90_day_budget != null ? money(ppc.total_90_day_budget) : "—"}</p>
          </div>
        </div>

        {/* Phase-by-phase budget */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {PHASE_ORDER.filter((k) => ppc.phases?.[k]).map((key) => {
            const p = ppc.phases![key];
            return (
              <div key={key} className="rounded-lg border p-4">
                <p className="font-semibold text-sm">{PHASE_LABEL[key] ?? key}</p>
                <div className="mt-2 space-y-1 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">Daily budget</span><span className="font-medium">{money(p.daily_budget)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Monthly</span><span className="font-medium">{money(p.monthly_budget)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Est. ACOS</span><span className="font-medium">{p.estimated_acos != null ? `${p.estimated_acos}%` : "—"}</span></div>
                </div>
                {p.strategy && <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{p.strategy}</p>}
              </div>
            );
          })}
        </div>

        {/* Top keywords */}
        {ppc.top_keywords && ppc.top_keywords.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Top target keywords</p>
            <div className="flex flex-wrap gap-2">
              {ppc.top_keywords.map((k) => <Badge key={k} variant="outline">{k}</Badge>)}
            </div>
          </div>
        )}

        {/* Plain-language warnings from the model */}
        {(burn || kill) && (
          <div className="space-y-2">
            {burn && (
              <div className="flex items-start gap-2 rounded-md border border-tier3/30 bg-tier3/5 p-3 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-tier3" />
                <span><span className="font-medium">Budget burn: </span>{burn}</span>
              </div>
            )}
            {kill && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                <span><span className="font-medium">Kill criteria: </span>{kill}</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
