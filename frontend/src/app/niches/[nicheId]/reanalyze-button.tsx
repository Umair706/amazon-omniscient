"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { RefreshCw, Loader2 } from "lucide-react";

// The backend owns "is this niche being analyzed" via the niche's status
// (analyzing -> completed/failed), set by the pipeline. We read that instead of
// tracking the job on the client, so the running state is correct after a
// refresh, on another device, and without any client-side bookkeeping.
const POLL_MS = 4000;
const ANALYZING = "analyzing";

export function ReanalyzeButton({ nicheId, status }: { nicheId: number; status: string | null }) {
  const [running, setRunning] = useState(status === ANALYZING);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Only treat "not analyzing" as finished once we've actually seen it analyzing,
  // so the brief gap between starting and the task flipping the status doesn't
  // read as "done" immediately.
  const sawAnalyzing = useRef(status === ANALYZING);

  const stop = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = null;
  };

  const pollStatus = useCallback(() => {
    stop();
    intervalRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/niches/${nicheId}`);
        const s: string | null = res.data?.status ?? null;
        if (s === ANALYZING) {
          sawAnalyzing.current = true;
        } else if (sawAnalyzing.current) {
          stop();
          if (s === "failed") {
            setRunning(false);
            setError(res.data?.last_error || "Analysis failed");
          } else {
            window.location.reload();
          }
        }
      } catch {
        // transient — keep polling
      }
    }, POLL_MS);
  }, [nicheId]);

  // Resume the running view after a refresh/navigation: the niche's status,
  // fetched by the page, tells us whether a run is in flight.
  useEffect(() => {
    if (status === ANALYZING) {
      setRunning(true);
      sawAnalyzing.current = true;
      pollStatus();
    }
    return stop;
  }, [status, pollStatus]);

  const start = useCallback(async () => {
    setRunning(true);
    setError("");
    sawAnalyzing.current = false;
    try {
      await api.post("/api/v1/jobs/reanalyze-niche", { niche_id: nicheId });
      pollStatus();
    } catch (err: any) {
      setRunning(false);
      setError(err.response?.data?.detail || "Could not start the re-run");
    }
  }, [nicheId, pollStatus]);

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="outline" size="sm" onClick={start} disabled={running}>
        {running ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
        {running ? "Analysis running…" : "Re-run analysis"}
      </Button>
      <span className="max-w-[210px] text-right text-[10px] leading-tight text-muted-foreground">
        {error ? (
          <span className="text-destructive">{error}</span>
        ) : running ? (
          "Runs in the background — safe to leave or refresh. AI steps use your local model, so it takes a few minutes."
        ) : (
          "Reuses scraped products; regenerates AI and score without re-scraping."
        )}
      </span>
    </div>
  );
}
