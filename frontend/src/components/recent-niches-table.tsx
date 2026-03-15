"use client";
import { useEffect, useState, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreBadge } from "@/components/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import type { NicheListItem } from "@/types";
import { AlertTriangle, RefreshCw } from "lucide-react";

export function RecentNichesTable() {
  const [niches, setNiches] = useState<NicheListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNiches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/v1/niches/", { params: { page: 1, per_page: 10, sort_by: "analyzed_at", sort_dir: "desc" } });
      setNiches(res.data.items || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load niches");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNiches();
  }, [fetchNiches]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>Recent Analyses</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader><CardTitle>Recent Analyses</CardTitle></CardHeader>
        <CardContent className="text-center space-y-3 py-8">
          <AlertTriangle className="h-8 w-8 text-destructive mx-auto" />
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchNiches}>
            <RefreshCw className="h-4 w-4 mr-2" /> Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Analyses</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-3 font-medium">Niche</th>
                <th className="pb-3 font-medium">Score</th>
                <th className="pb-3 font-medium">Avg Price</th>
                <th className="pb-3 font-medium">Search Volume</th>
                <th className="pb-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {niches.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted-foreground">
                    No niches analyzed yet. Start by entering a keyword above.
                  </td>
                </tr>
              )}
              {niches.map((niche) => (
                <tr
                  key={niche.id}
                  className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                  onClick={() => window.location.href = `/niches/${niche.id}`}
                >
                  <td className="py-3">
                    <div>
                      <p className="font-medium">{niche.name || niche.primary_keyword}</p>
                      <p className="text-xs text-muted-foreground">{niche.primary_keyword}</p>
                    </div>
                  </td>
                  <td className="py-3">
                    {niche.opportunity_score != null ? (
                      <ScoreBadge score={niche.opportunity_score} tier={niche.confidence_tier || "LOW"} size="sm" />
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </td>
                  <td className="py-3">{niche.avg_sale_price ? formatCurrency(niche.avg_sale_price) : "\u2014"}</td>
                  <td className="py-3">{niche.monthly_search_volume?.toLocaleString() || "\u2014"}</td>
                  <td className="py-3">
                    <Badge variant={niche.confidence_tier === "HIGH" ? "default" : "secondary"}>
                      {niche.confidence_tier || "Pending"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
