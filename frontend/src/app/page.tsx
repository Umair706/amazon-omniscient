"use client";
import { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { StatCard } from "@/components/stat-card";
import { AnalyzeDialog } from "@/components/analyze-dialog";
import { RecentNichesTable } from "@/components/recent-niches-table";
import { BarChart3, TrendingUp, Target, DollarSign, AlertTriangle, RefreshCw, Compass, Search, FileText, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
        <p className="text-muted-foreground mt-1">
          Your Amazon product research at a glance.{" "}
          <Link href="/docs" className="text-primary hover:underline">New here? Read the 2-minute guide</Link>.
        </p>
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
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Start here</h2>
              <p className="text-muted-foreground mt-1">Three steps from an idea to a go/no-go decision.</p>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {[
                { n: 1, icon: Compass, title: "Discover niches", body: "No keyword yet? Enter a broad idea and get ranked candidates.", href: "/discover", cta: "Open Discover" },
                { n: 2, icon: Search, title: "Analyze a keyword", body: "Know the product? Enter its keyword in the box above to run a full analysis.", href: null, cta: "Use the box above" },
                { n: 3, icon: FileText, title: "Read your brief", body: "Get a scored recommendation with financials, suppliers, and a launch plan.", href: "/recommendations", cta: "View briefs" },
              ].map((s) => (
                <Card key={s.n} className="flex flex-col">
                  <CardContent className="p-5 flex flex-col h-full">
                    <div className="flex items-center gap-2">
                      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">{s.n}</span>
                      <s.icon className="h-4 w-4 text-primary" />
                      <h3 className="font-semibold">{s.title}</h3>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2 flex-1">{s.body}</p>
                    {s.href ? (
                      <Link href={s.href} className="mt-3">
                        <Button variant="outline" size="sm" className="w-full">{s.cta}<ArrowRight className="ml-2 h-4 w-4" /></Button>
                      </Link>
                    ) : (
                      <p className="mt-3 text-xs text-muted-foreground italic">{s.cta}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ) : (
          <RecentNichesTable />
        )}
      </motion.div>
    </motion.div>
  );
}
