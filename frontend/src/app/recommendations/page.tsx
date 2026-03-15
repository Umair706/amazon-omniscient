"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import type { RecommendationSummary } from "@/types";

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<RecommendationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/api/v1/recommendations", { params: { per_page: 50 } })
      .then((res) => setRecs(res.data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Recommendations</h1>
        <p className="text-muted-foreground mt-1">All product opportunity briefs</p>
      </div>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : recs.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No recommendations yet. Analyze a niche to generate one.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {recs.map((rec) => (
            <Card
              key={rec.id}
              className="hover:bg-muted/50 cursor-pointer transition-colors"
              onClick={() => window.location.href = `/recommendations/${rec.id}`}
            >
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <ScoreBadge score={rec.omniscient_score} tier={rec.confidence_tier} size="sm" />
                    <div>
                      <h3 className="font-semibold">{rec.niche_name}</h3>
                      <div className="flex gap-4 text-sm text-muted-foreground mt-1">
                        <span>Price: {formatCurrency(rec.recommended_sale_price)}</span>
                        <span>Margin: {rec.estimated_net_margin_pct?.toFixed(1)}%</span>
                        <span>Break-even: Week {rec.break_even_week_base || "N/A"}</span>
                        <span>Capital: {formatCurrency(rec.total_launch_capital)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge variant={rec.confidence_tier === "HIGH" ? "default" : "secondary"}>
                      {rec.confidence_tier}
                    </Badge>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(rec.generated_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
