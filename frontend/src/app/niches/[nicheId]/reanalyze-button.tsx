"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { RefreshCw, Loader2 } from "lucide-react";

type State = "idle" | "running" | "error";

// Plain-English labels for the pipeline steps the status endpoint reports.
const STEP_LABELS: Record<string, string> = {
  loading_products: "Loading products",
  products_scraped: "Products ready",
  competitor_analysis: "Analyzing competitors",
  review_analysis: "Reading reviews",
  niche_intelligence: "Market intelligence (AI)",
  product_blueprint: "Product blueprint (AI)",
  product_spec: "Product spec (AI)",
  supplier_scraping: "Finding suppliers",
  supplier_matching: "Matching suppliers (AI)",
  supplier_analysis: "Costing suppliers",
  ppc_strategy: "PPC strategy (AI)",
  review_strategy: "Review strategy (AI)",
  financial_projections: "Financial projections",
  marketing_plan: "Marketing plan (AI)",
  financial_report: "Financial report (AI)",
  scoring: "Scoring",
  saving_recommendation: "Saving",
};

// A re-run can take many minutes on a local model. Persist the running job per
// niche so a refresh or navigating away and back reconnects to it instead of
// losing the progress. The Celery task itself always runs in the background.
const STORAGE_PREFIX = "omni_reanalyze_niche_";
const STALE_AFTER_MS = 40 * 60 * 1000; // stop tracking a job older than this

interface StoredJob {
  jobId: string;
  startedAt: number;
}

function loadJob(nicheId: number): StoredJob | null {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + nicheId);
    if (!raw) return null;
    const job = JSON.parse(raw) as StoredJob;
    if (Date.now() - job.startedAt > STALE_AFTER_MS) {
      localStorage.removeItem(STORAGE_PREFIX + nicheId);
      return null;
    }
    return job;
  } catch {
    return null;
  }
}

function saveJob(nicheId: number, job: StoredJob) {
  try {
    localStorage.setItem(STORAGE_PREFIX + nicheId, JSON.stringify(job));
  } catch {}
}

function clearJob(nicheId: number) {
  try {
    localStorage.removeItem(STORAGE_PREFIX + nicheId);
  } catch {}
}

export function ReanalyzeButton({ nicheId }: { nicheId: number }) {
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback((jobId: string) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/jobs/${jobId}/status`);
        const data = res.data;
        setProgress(data.progress ?? 0);
        setStep(data.result?.step || "");
        if (data.status === "completed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          clearJob(nicheId);
          window.location.reload();
        } else if (data.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          clearJob(nicheId);
          setState("error");
          setMessage(data.error || "Re-run failed");
        }
      } catch {
        // transient — keep polling
      }
    }, 3000);
  }, [nicheId]);

  // Reconnect to an in-flight re-run for this niche after a refresh/navigation.
  useEffect(() => {
    const job = loadJob(nicheId);
    if (job) {
      setState("running");
      poll(job.jobId);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [nicheId, poll]);

  const start = useCallback(async () => {
    setState("running");
    setMessage("");
    setProgress(0);
    setStep("");
    try {
      const res = await api.post("/api/v1/jobs/reanalyze-niche", { niche_id: nicheId });
      saveJob(nicheId, { jobId: res.data.job_id, startedAt: Date.now() });
      poll(res.data.job_id);
    } catch (err: any) {
      setState("error");
      setMessage(err.response?.data?.detail || "Could not start the re-run");
    }
  }, [nicheId, poll]);

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="outline" size="sm" onClick={start} disabled={state === "running"}>
        {state === "running" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
        {state === "running" ? "Re-running…" : "Re-run analysis"}
      </Button>
      <span className="max-w-[210px] text-right text-[10px] leading-tight text-muted-foreground">
        {state === "error" ? (
          <span className="text-destructive">{message}</span>
        ) : state === "running" ? (
          <>
            {progress > 0 ? `${progress}% · ` : ""}{STEP_LABELS[step] || "Working"}
            <span className="block">Runs in the background — safe to leave or refresh. AI steps use your local model, so it takes a few minutes.</span>
          </>
        ) : (
          "Reuses scraped products; regenerates AI and score without re-scraping."
        )}
      </span>
    </div>
  );
}
