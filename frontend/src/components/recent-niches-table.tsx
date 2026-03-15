"use client";
import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import type { NicheListItem } from "@/types";

export function RecentNichesTable() {
  const [niches, setNiches] = useState<NicheListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/api/v1/niches", { params: { page: 1, per_page: 10, sort_by: "analyzed_at", sort_dir: "desc" } })
      .then((res) => setNiches(res.data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
                <th className="pb-3 font-medium">Reviews</th>
                <th className="pb-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {niches.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
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
                  <td className="py-3">{niche.avg_review_count?.toLocaleString() || "\u2014"}</td>
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
