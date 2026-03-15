"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import api from "@/lib/api";
import { CheckCircle2, XCircle, Loader2, Search, ArrowRight } from "lucide-react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Step label mapping
// ---------------------------------------------------------------------------

const STEP_LABELS: Record<string, string> = {
  scraping_search: "Searching Amazon...",
  scraping_products: "Scraping product details...",
  products_scraped: "Products collected",
  competitor_analysis: "Analyzing competitors...",
  review_analysis: "Analyzing reviews...",
  product_blueprint: "Building product blueprint...",
  product_spec: "Generating product spec...",
  supplier_scraping: "Finding suppliers on 1688...",
  supplier_analysis: "Calculating costs...",
  ppc_strategy: "Building PPC strategy...",
  review_strategy: "Building review strategy...",
  financial_projections: "Running financial projections...",
  marketing_plan: "Creating marketing plan...",
  financial_report: "Building financial report...",
  scoring: "Computing Omniscient Score...",
  complete: "Analysis complete!",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobStatus = "idle" | "submitting" | "analyzing" | "completed" | "failed";

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

  // ---- Polling ----
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
          clearInterval(interval);
        } else if (data.status === "failed") {
          setJobStatus("failed");
          setJobError(data.error || "Analysis failed");
          clearInterval(interval);
        }
      } catch {
        // Silently retry on network errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus]);

  // ---- Submit ----
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = keyword.trim();
      if (!trimmed) return;

      setJobStatus("submitting");
      setJobError("");
      setJobResult(null);
      setProgress(0);
      setStep("");

      try {
        const res = await api.post("/api/v1/jobs/analyze", { keyword: trimmed });
        const { job_id } = res.data;
        setJobId(job_id);
        setJobStatus("analyzing");
        onJobStarted?.(job_id);
      } catch (err: any) {
        setJobStatus("failed");
        setJobError(err.response?.data?.detail || "Failed to start analysis");
      }
    },
    [keyword, onJobStarted],
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
  }, []);

  // ---- Derived UI values ----
  const stepLabel = STEP_LABELS[step] || step || "Processing...";
  const isInputDisabled = jobStatus === "submitting" || jobStatus === "analyzing";
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
