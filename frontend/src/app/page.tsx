"use client";
import { useEffect, useState, useCallback, Suspense } from "react";
import { motion } from "framer-motion";
import { StatCard } from "@/components/stat-card";
import { AnalyzeDialog } from "@/components/analyze-dialog";
import { RecentNichesTable } from "@/components/recent-niches-table";
import { BarChart3, TrendingUp, Target, DollarSign, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import type { NicheStats } from "@/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<NicheStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setError(null);
    try {
      // The database computes these totals in one query, so this stays
      // correct no matter how many niches exist (the old version averaged
      // only the first 100 niches in the browser).
      const response = await api.get<NicheStats>("/api/v1/niches/stats");
      setStats(response.data);
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
          value={stats?.avg_score == null ? "\u2014" : `${Math.round(stats.avg_score)}/100`}
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
        <Suspense fallback={null}>
          <AnalyzeDialog />
        </Suspense>
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
