"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";
import type { NicheListItem, PaginatedResponse } from "@/types";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  Filter,
} from "lucide-react";

type SortField = "opportunity_score" | "avg_sale_price" | "monthly_search_volume" | "avg_review_count" | "name";
type SortDir = "asc" | "desc";

export default function NicheExplorerPage() {
  const [niches, setNiches] = useState<NicheListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("opportunity_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [minScore, setMinScore] = useState<number | "">("");
  const [tierFilter, setTierFilter] = useState<string>("");

  const fetchNiches = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        page,
        per_page: perPage,
        sort_by: sortBy,
        sort_dir: sortDir,
      };
      if (search) params.search = search;
      if (minScore !== "") params.min_score = minScore;
      if (tierFilter) params.confidence_tier = tierFilter;

      const res = await api.get<PaginatedResponse<NicheListItem>>("/api/v1/niches/", { params });
      setNiches(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch {
      setNiches([]);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, sortDir, search, minScore, tierFilter]);

  useEffect(() => {
    fetchNiches();
  }, [fetchNiches]);

  const totalPages = Math.ceil(total / perPage);

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(1);
  };

  const SortButton = ({ field, label }: { field: SortField; label: string }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 font-medium hover:text-foreground transition-colors"
    >
      {label}
      <ArrowUpDown className={`h-3 w-3 ${sortBy === field ? "text-primary" : "text-muted-foreground"}`} />
    </button>
  );

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
        <h1 className="text-3xl font-bold">Niche Explorer</h1>
        <p className="text-muted-foreground mt-1">Browse and filter analyzed niches</p>
      </motion.div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search niches..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  className="pl-9"
                />
              </div>
            </div>
            <div className="w-32">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Min Score</label>
              <Input
                type="number"
                placeholder="0"
                min={0}
                max={100}
                value={minScore}
                onChange={(e) => { setMinScore(e.target.value ? parseInt(e.target.value) : ""); setPage(1); }}
              />
            </div>
            <div className="w-40">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Confidence</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={tierFilter}
                onChange={(e) => { setTierFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Tiers</option>
                <option value="HIGH">High (80+)</option>
                <option value="MEDIUM">Medium (60-79)</option>
                <option value="LOW">Low (40-59)</option>
                <option value="VERY_LOW">Very Low (&lt;40)</option>
                <option value="FAIL">Disqualified</option>
              </select>
            </div>
            <Button variant="outline" onClick={() => { setSearch(""); setMinScore(""); setTierFilter(""); setPage(1); }}>
              <Filter className="h-4 w-4 mr-1" /> Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="p-4"><SortButton field="name" label="Niche" /></th>
                  <th className="p-4"><SortButton field="opportunity_score" label="Score" /></th>
                  <th className="p-4"><SortButton field="avg_sale_price" label="Avg Price" /></th>
                  <th className="p-4"><SortButton field="monthly_search_volume" label="Search Vol" /></th>
                  <th className="p-4"><SortButton field="avg_review_count" label="Avg Reviews" /></th>
                  <th className="p-4">Seasonal</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b">
                      <td colSpan={7} className="p-4"><Skeleton className="h-8 w-full" /></td>
                    </tr>
                  ))
                ) : niches.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-12 text-center text-muted-foreground">
                      No niches found. Try adjusting your filters.
                    </td>
                  </tr>
                ) : (
                  niches.map((niche) => (
                    <tr
                      key={niche.id}
                      className="border-b last:border-0 hover:bg-muted/50 cursor-pointer transition-colors"
                      onClick={() => window.location.href = `/niches/${niche.id}`}
                    >
                      <td className="p-4">
                        <div>
                          <p className="font-medium">{niche.name || niche.primary_keyword}</p>
                          <p className="text-xs text-muted-foreground">{niche.primary_keyword}</p>
                        </div>
                      </td>
                      <td className="p-4">
                        {niche.opportunity_score != null ? (
                          <ScoreBadge score={niche.opportunity_score} tier={niche.confidence_tier || "LOW"} size="sm" />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="p-4">{niche.avg_sale_price ? formatCurrency(niche.avg_sale_price) : "—"}</td>
                      <td className="p-4">{niche.monthly_search_volume?.toLocaleString() || "—"}</td>
                      <td className="p-4">{niche.avg_review_count?.toLocaleString() || "—"}</td>
                      <td className="p-4">
                        {niche.is_seasonal ? (
                          <Badge variant="destructive">Yes</Badge>
                        ) : (
                          <Badge variant="secondary">No</Badge>
                        )}
                      </td>
                      <td className="p-4">
                        <Badge variant={niche.confidence_tier === "HIGH" ? "default" : "secondary"}>
                          {niche.confidence_tier || "Pending"}
                        </Badge>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t p-4">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of {total}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
