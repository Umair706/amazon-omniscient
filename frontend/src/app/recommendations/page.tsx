"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreBadge } from "@/components/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import type { RecommendationSummary } from "@/types";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<RecommendationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/v1/recommendations/", { params: { per_page: 50 } });
      setRecs(res.data.items || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecs();
  }, [fetchRecs]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h1 className="text-3xl font-bold">Recommendations</h1>
        <p className="text-muted-foreground mt-1">All product opportunity briefs</p>
      </motion.div>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-12 text-center space-y-4">
            <AlertTriangle className="h-10 w-10 text-destructive mx-auto" />
            <p className="text-destructive font-medium">{error}</p>
            <Button variant="outline" onClick={fetchRecs}>
              <RefreshCw className="h-4 w-4 mr-2" /> Retry
            </Button>
          </CardContent>
        </Card>
      ) : recs.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground space-y-3">
            <p>No recommendations yet. Analyze a niche to generate one.</p>
            <Button variant="outline" onClick={() => window.location.href = "/"}>
              Go to Dashboard
            </Button>
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
                        <span>Margin: {rec.estimated_net_margin_pct != null ? `${parseFloat(String(rec.estimated_net_margin_pct)).toFixed(1)}%` : "N/A"}</span>
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
                      {rec.generated_at ? new Date(rec.generated_at).toLocaleDateString() : "N/A"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </motion.div>
  );
}
