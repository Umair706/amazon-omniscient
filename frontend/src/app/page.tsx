"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { StatCard } from "@/components/stat-card";
import { AnalyzeDialog } from "@/components/analyze-dialog";
import { RecentNichesTable } from "@/components/recent-niches-table";
import { BarChart3, TrendingUp, Target, DollarSign, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

interface DashboardStats {
  total_niches: number;
  avg_score: number;
  high_confidence_count: number;
  total_recommendations: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setError(null);
    try {
      const [nichesRes, recsRes, allNiches] = await Promise.all([
        api.get("/api/v1/niches/", { params: { per_page: 1 } }),
        api.get("/api/v1/recommendations/", { params: { per_page: 1 } }),
        api.get("/api/v1/niches/", { params: { per_page: 100 } }),
      ]);
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
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load dashboard data");
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

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
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your Amazon product research</p>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex items-center justify-center gap-3 p-6 rounded-lg border border-destructive/30 bg-destructive/5"
        >
          <AlertTriangle className="h-5 w-5 text-destructive" />
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchStats}>
            <RefreshCw className="h-4 w-4 mr-2" /> Retry
          </Button>
        </motion.div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Niches Analyzed"
          value={stats?.total_niches ?? "\u2014"}
          icon={BarChart3}
          index={0}
        />
        <StatCard
          title="Average Score"
          value={stats?.avg_score ? `${stats.avg_score}/100` : "\u2014"}
          icon={Target}
          index={1}
        />
        <StatCard
          title="High Confidence"
          value={stats?.high_confidence_count ?? "\u2014"}
          subtitle="Score 80+"
          icon={TrendingUp}
          index={2}
        />
        <StatCard
          title="Recommendations"
          value={stats?.total_recommendations ?? "\u2014"}
          icon={DollarSign}
          index={3}
        />
      </div>

      {/* Analyze New Niche */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.4 }}
      >
        <AnalyzeDialog />
      </motion.div>

      {/* Empty State or Recent Niches */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.5 }}
      >
        {stats && stats.total_niches === 0 && !error ? (
          <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
            <div className="p-4 rounded-full bg-primary/10">
              <BarChart3 className="h-12 w-12 text-primary" />
            </div>
            <h2 className="text-xl font-semibold">No Niches Analyzed Yet</h2>
            <p className="text-muted-foreground max-w-md">
              Enter a keyword above to start your first niche analysis. Omniscient will scrape Amazon,
              analyze competitors, find suppliers, and generate a scored recommendation.
            </p>
          </div>
        ) : (
          <RecentNichesTable />
        )}
      </motion.div>
    </motion.div>
  );
}
