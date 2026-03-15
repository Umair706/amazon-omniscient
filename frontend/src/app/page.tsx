"use client";
import { useEffect, useState } from "react";
import { StatCard } from "@/components/stat-card";
import { AnalyzeDialog } from "@/components/analyze-dialog";
import { RecentNichesTable } from "@/components/recent-niches-table";
import { BarChart3, TrendingUp, Target, DollarSign } from "lucide-react";
import api from "@/lib/api";

interface DashboardStats {
  total_niches: number;
  avg_score: number;
  high_confidence_count: number;
  total_recommendations: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    // Fetch aggregated stats from niches and recommendations
    Promise.all([
      api.get("/api/v1/niches/", { params: { per_page: 1 } }).catch(() => ({ data: { total: 0 } })),
      api.get("/api/v1/recommendations/", { params: { per_page: 1 } }).catch(() => ({ data: { total: 0 } })),
      api.get("/api/v1/niches/", { params: { per_page: 100 } }).catch(() => ({ data: { items: [] } })),
    ]).then(([nichesRes, recsRes, allNiches]) => {
      const items = allNiches.data.items || [];
      const scores = items
        .filter((n: any) => n.opportunity_score != null)
        .map((n: any) => n.opportunity_score);
      const avgScore =
        scores.length > 0
          ? Math.round(scores.reduce((a: number, b: number) => a + b, 0) / scores.length)
          : 0;
      const highConf = items.filter((n: any) => n.confidence_tier === "HIGH").length;

      setStats({
        total_niches: nichesRes.data.total || 0,
        avg_score: avgScore,
        high_confidence_count: highConf,
        total_recommendations: recsRes.data.total || 0,
      });
    });
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your Amazon product research</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Niches Analyzed"
          value={stats?.total_niches ?? "\u2014"}
          icon={BarChart3}
        />
        <StatCard
          title="Average Score"
          value={stats?.avg_score ? `${stats.avg_score}/100` : "\u2014"}
          icon={Target}
        />
        <StatCard
          title="High Confidence"
          value={stats?.high_confidence_count ?? "\u2014"}
          subtitle="Score 80+"
          icon={TrendingUp}
        />
        <StatCard
          title="Recommendations"
          value={stats?.total_recommendations ?? "\u2014"}
          icon={DollarSign}
        />
      </div>

      {/* Analyze New Niche */}
      <AnalyzeDialog />

      {/* Recent Niches Table */}
      <RecentNichesTable />
    </div>
  );
}
