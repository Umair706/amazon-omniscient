"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { RefreshCw, Loader2 } from "lucide-react";

type State = "idle" | "running" | "error";

// Re-runs the analysis on this niche WITHOUT re-scraping: reuses the products
// already captured and regenerates the AI intelligence, suppliers, financials,
// and score. Handy after configuring an LLM or changing the scoring rules.
export function ReanalyzeButton({ nicheId }: { nicheId: number }) {
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");

  const poll = useCallback((jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/jobs/${jobId}/status`);
        if (res.data.status === "completed") {
          clearInterval(interval);
          window.location.reload();
        } else if (res.data.status === "failed") {
          clearInterval(interval);
          setState("error");
          setMessage(res.data.error || "Re-run failed");
        }
      } catch {
        // transient — keep polling
      }
    }, 3000);
  }, []);

  const start = useCallback(async () => {
    setState("running");
    setMessage("");
    try {
      const res = await api.post("/api/v1/jobs/reanalyze-niche", { niche_id: nicheId });
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
      <span className="max-w-[190px] text-right text-[10px] leading-tight text-muted-foreground">
        {state === "error" ? (
          <span className="text-destructive">{message}</span>
        ) : (
          "Reuses scraped products; regenerates AI and score without re-scraping."
        )}
      </span>
    </div>
  );
}
