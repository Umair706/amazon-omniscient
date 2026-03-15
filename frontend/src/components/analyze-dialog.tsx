"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import api from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { CheckCircle2, XCircle, Loader2, Search, ArrowRight, Layers } from "lucide-react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Step label mapping
// ---------------------------------------------------------------------------

const STEP_LABELS: Record<string, string> = {
  scraping_search: "Searching Amazon...",
  scraping_products: "Scraping product details...",
  products_scraped: "Products collected",
  detecting_sub_niches: "Detecting product categories...",
  clustering: "Clustering into sub-niches...",
  loading_products: "Loading product data...",
  competitor_analysis: "Analyzing competitors...",
  review_analysis: "Analyzing reviews...",
  review_intelligence: "Analyzing review patterns...",
  niche_intelligence: "Generating market intelligence...",
  product_blueprint: "Building product blueprint...",
  product_spec: "Generating product spec...",
  product_ideas: "Generating product ideas...",
  supplier_scraping: "Finding suppliers on 1688...",
  supplier_matching: "Finding per-product suppliers...",
  translating_suppliers: "Translating supplier data...",
  supplier_analysis: "Calculating costs...",
  ppc_strategy: "Building PPC strategy...",
  review_strategy: "Building review strategy...",
  financial_projections: "Running financial projections...",
  marketing_plan: "Creating marketing plan...",
  financial_report: "Building financial report...",
  scoring: "Computing Omniscient Score...",
  saving_recommendation: "Saving recommendation...",
  complete: "Analysis complete!",
};

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = "omniscient_active_job";

interface SubNiche {
  label: string;
  description: string;
  asin_list: string[];
  avg_price: number;
  product_count: number;
}

interface StoredJob {
  jobId: string;
  keyword: string;
  startedAt: string;
  phase: "discovery" | "analysis";
  parentNicheId?: number;
  subNiches?: SubNiche[];
}

function saveActiveJob(job: StoredJob) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(job));
  } catch {}
}

function loadActiveJob(): StoredJob | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredJob;
  } catch {
    return null;
  }
}

function clearActiveJob() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobStatus =
  | "idle"
  | "submitting"
  | "discovering"
  | "sub_niche_selection"
  | "analyzing"
  | "completed"
  | "failed";

interface AnalyzeDialogProps {
  onJobStarted?: (jobId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AnalyzeDialog({ onJobStarted }: AnalyzeDialogProps) {
  const [keyword, setKeyword] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState("");
  const [jobResult, setJobResult] = useState<Record<string, any> | null>(null);
  const [jobError, setJobError] = useState("");
  const [subNiches, setSubNiches] = useState<SubNiche[]>([]);
  const [parentNicheId, setParentNicheId] = useState<number | null>(null);

  // ---- Resume from localStorage on mount ----
  useEffect(() => {
    const stored = loadActiveJob();
    if (stored) {
      setJobId(stored.jobId);
      setKeyword(stored.keyword);
      if (stored.parentNicheId) setParentNicheId(stored.parentNicheId);

      if (stored.subNiches && stored.subNiches.length > 0) {
        // Restore sub-niche selection state
        setSubNiches(stored.subNiches);
        setJobStatus("sub_niche_selection");
      } else if (stored.phase === "discovery") {
        setJobStatus("discovering");
      } else {
        setJobStatus("analyzing");
      }
    }
  }, []);

  // ---- Polling for discovery phase ----
  useEffect(() => {
    if (!jobId || jobStatus !== "discovering") return;

    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/jobs/${jobId}/status`);
        const data = res.data;

        setProgress(data.progress ?? 0);
        setStep(data.result?.step || "");

        if (data.status === "completed") {
          clearInterval(interval);
          const result = data.result;

          if (result?.is_broad && result?.sub_niches?.length > 0) {
            // Broad keyword — show sub-niche selection
            setSubNiches(result.sub_niches);
            setParentNicheId(result.niche_id);
            setJobStatus("sub_niche_selection");
            // Save to localStorage for resume
            saveActiveJob({
              jobId: jobId,
              keyword,
              startedAt: new Date().toISOString(),
              phase: "discovery",
              parentNicheId: result.niche_id,
              subNiches: result.sub_niches,
            });
          } else {
            // Narrow keyword — auto-continue to full analysis
            const nicheId = result?.niche_id;
            if (nicheId) {
              try {
                const analyzeRes = await api.post("/api/v1/jobs/analyze", {
                  keyword,
                  force: true,
                });
                const newJobId = analyzeRes.data.job_id;
                setJobId(newJobId);
                setJobStatus("analyzing");
                setProgress(0);
                setStep("");
                saveActiveJob({
                  jobId: newJobId,
                  keyword,
                  startedAt: new Date().toISOString(),
                  phase: "analysis",
                });
                onJobStarted?.(newJobId);
              } catch (err: any) {
                setJobStatus("failed");
                setJobError(err.response?.data?.detail || "Failed to start full analysis");
                clearActiveJob();
              }
            }
          }
        } else if (data.status === "failed") {
          setJobStatus("failed");
          setJobError(data.error || "Discovery failed");
          clearActiveJob();
          clearInterval(interval);
        }
      } catch {
        // Silently retry on network errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus, keyword, onJobStarted]);

  // ---- Polling for analysis phase ----
  useEffect(() => {
    if (!jobId || jobStatus !== "analyzing") return;

    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/jobs/${jobId}/status`);
        const data = res.data;

        setProgress(data.progress ?? 0);
        setStep(data.result?.step || "");

        if (data.status === "completed") {
          setJobStatus("completed");
          setJobResult(data.result);
          setProgress(100);
          clearActiveJob();
          clearInterval(interval);
        } else if (data.status === "failed") {
          setJobStatus("failed");
          setJobError(data.error || "Analysis failed");
          clearActiveJob();
          clearInterval(interval);
        }
      } catch {
        // Silently retry on network errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus]);

  // ---- Submit (starts discovery) ----
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = keyword.trim();
      if (!trimmed) return;

      setJobStatus("submitting");
      setJobError("");
      setJobResult(null);
      setSubNiches([]);
      setParentNicheId(null);
      setProgress(0);
      setStep("");

      try {
        const res = await api.post("/api/v1/jobs/discover", { keyword: trimmed });
        const { job_id, result } = res.data;
        setJobId(job_id);
        setJobStatus("discovering");
        saveActiveJob({
          jobId: job_id,
          keyword: trimmed,
          startedAt: new Date().toISOString(),
          phase: "discovery",
          parentNicheId: result?.niche_id,
        });
        onJobStarted?.(job_id);
      } catch (err: any) {
        setJobStatus("failed");
        setJobError(err.response?.data?.detail || "Failed to start discovery");
      }
    },
    [keyword, onJobStarted],
  );

  // ---- Sub-niche selection ----
  const handleSubNicheSelect = useCallback(
    async (sn: SubNiche) => {
      if (!parentNicheId) return;

      setJobStatus("submitting");
      setJobError("");

      try {
        const res = await api.post("/api/v1/jobs/analyze-sub-niche", {
          parent_niche_id: parentNicheId,
          sub_niche_label: sn.label,
          product_asins: sn.asin_list,
        });
        const { job_id } = res.data;
        setJobId(job_id);
        setJobStatus("analyzing");
        setSubNiches([]);
        setProgress(0);
        setStep("");
        saveActiveJob({
          jobId: job_id,
          keyword,
          startedAt: new Date().toISOString(),
          phase: "analysis",
          parentNicheId,
        });
        onJobStarted?.(job_id);
      } catch (err: any) {
        setJobStatus("failed");
        setJobError(err.response?.data?.detail || "Failed to start sub-niche analysis");
      }
    },
    [parentNicheId, keyword, onJobStarted],
  );

  // ---- Reset ----
  const handleReset = useCallback(() => {
    setJobId(null);
    setJobStatus("idle");
    setProgress(0);
    setStep("");
    setJobResult(null);
    setJobError("");
    setKeyword("");
    setSubNiches([]);
    setParentNicheId(null);
    clearActiveJob();
  }, []);

  // ---- Derived UI values ----
  const stepLabel = STEP_LABELS[step] || step || "Processing...";
  const isInputDisabled =
    jobStatus === "submitting" ||
    jobStatus === "discovering" ||
    jobStatus === "analyzing" ||
    jobStatus === "sub_niche_selection";
  const recommendationId = jobResult?.recommendation_id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Analyze New Niche</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* ---------- Input form ---------- */}
        <form onSubmit={handleSubmit}>
          <div className="flex gap-2">
            <Input
              placeholder="Enter a niche keyword (e.g., 'silicone kitchen utensils')"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              disabled={isInputDisabled}
            />
            <Button
              type="submit"
              disabled={isInputDisabled || !keyword.trim()}
            >
              {jobStatus === "submitting" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="ml-2">
                {jobStatus === "submitting" ? "Starting..." : "Analyze"}
              </span>
            </Button>
          </div>
        </form>

        {/* ---------- Submitting ---------- */}
        {jobStatus === "submitting" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Starting analysis...
          </div>
        )}

        {/* ---------- Discovering (progress) ---------- */}
        {jobStatus === "discovering" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {stepLabel}
              </span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">
              Scanning products to determine if this keyword needs sub-niche segmentation...
            </p>
          </div>
        )}

        {/* ---------- Sub-niche selection ---------- */}
        {jobStatus === "sub_niche_selection" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Layers className="h-5 w-5 text-primary" />
              <span className="font-medium">Multiple product categories detected</span>
            </div>
            <p className="text-sm text-muted-foreground">
              &ldquo;{keyword}&rdquo; spans multiple product categories. Select one to analyze:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {subNiches.map((sn) => (
                <Card
                  key={sn.label}
                  className="cursor-pointer hover:border-primary transition-colors"
                  onClick={() => handleSubNicheSelect(sn)}
                >
                  <CardContent className="p-4">
                    <h4 className="font-semibold text-sm">{sn.label}</h4>
                    <p className="text-xs text-muted-foreground mt-1">{sn.description}</p>
                    <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                      <span>{sn.product_count} products</span>
                      <span>Avg {formatCurrency(sn.avg_price)}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <Button size="sm" variant="outline" onClick={handleReset}>
              Start Over
            </Button>
          </div>
        )}

        {/* ---------- Analyzing (progress) ---------- */}
        {jobStatus === "analyzing" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {stepLabel}
              </span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">
              This may take a few minutes. You can close this dialog and come
              back later.
            </p>
          </div>
        )}

        {/* ---------- Completed ---------- */}
        {jobStatus === "completed" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle2 className="h-5 w-5" />
              <span className="font-medium">Analysis complete!</span>
            </div>
            <Progress value={100} indicatorClassName="bg-green-500" />
            <div className="flex gap-2">
              {recommendationId && (
                <Link href={`/recommendations/${recommendationId}`}>
                  <Button size="sm">
                    View Results
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              )}
              <Button size="sm" variant="outline" onClick={handleReset}>
                Analyze Another
              </Button>
            </div>
          </div>
        )}

        {/* ---------- Failed ---------- */}
        {jobStatus === "failed" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <XCircle className="h-5 w-5" />
              <span className="font-medium">{jobError}</span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={handleReset}>
                Try Again
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
