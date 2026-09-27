"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { InfoHint } from "@/components/info-hint";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { MARKETPLACE_CODES, marketplaceLabel } from "@/lib/marketplace";
import { Compass, Loader2, Search, Sparkles } from "lucide-react";

interface Candidate {
  keyword: string;
  opportunity_score: number;
  label: string;
  reason: string;
  volume_tier: string;
  total_results: number;
  sponsored_count: number;
  brand_count: number;
}

type Phase = "idle" | "running" | "done" | "failed";

// A round score chip, coloured green/amber/red by the opportunity pre-score band.
function ScorePill({ score }: { score: number }) {
  const tone =
    score >= 60 ? "text-tier2 border-tier2 bg-tier2/10"
    : score >= 45 ? "text-tier3 border-tier3 bg-tier3/10"
    : "text-rejected border-rejected bg-rejected/10";
  return (
    <div className={cn("shrink-0 rounded-full border-2 flex items-center justify-center font-bold w-12 h-12 text-lg", tone)}>
      {score}
    </div>
  );
}

export default function DiscoverPage() {
  const router = useRouter();
  const [seed, setSeed] = useState("");
  const [marketplace, setMarketplace] = useState("AU");
  const [phase, setPhase] = useState<Phase>("idle");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState("");

  const poll = useCallback((jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/jobs/${jobId}/status`);
        const data = res.data;
        if (data.status === "completed") {
          clearInterval(interval);
          setCandidates(data.result?.candidates || []);
          setPhase("done");
        } else if (data.status === "failed") {
          clearInterval(interval);
          setError(data.error || "Discovery failed");
          setPhase("failed");
        }
      } catch {
        // transient network error — keep polling
      }
    }, 3000);
  }, []);

  const start = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = seed.trim();
    if (!trimmed) return;
    setPhase("running");
    setError("");
    setCandidates([]);
    try {
      const res = await api.post("/api/v1/jobs/discover-opportunities", { seed: trimmed, marketplace });
      poll(res.data.job_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start discovery");
      setPhase("failed");
    }
  }, [seed, marketplace, poll]);

  // Hand the chosen keyword to the dashboard's analysis flow. That flow already
  // runs discovery -> optional sub-niche pick -> full analysis with progress,
  // so we reuse it here instead of duplicating the polling.
  const analyze = useCallback((keyword: string) => {
    const params = new URLSearchParams({ keyword, marketplace });
    router.push(`/?${params.toString()}`);
  }, [marketplace, router]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2"><Compass className="h-7 w-7 text-primary" /> Discover Niches</h1>
        <p className="text-muted-foreground mt-1">
          Enter a broad seed and get candidate niches ranked by a quick opportunity pre-score, then analyze the best.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Find opportunities</CardTitle>
          <CardDescription>e.g. &ldquo;kitchen gadgets&rdquo;, &ldquo;home office&rdquo;, &ldquo;pet supplies&rdquo;</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={start} className="flex flex-col gap-2 sm:flex-row">
            <select
              aria-label="Amazon marketplace"
              value={marketplace}
              onChange={(e) => setMarketplace(e.target.value)}
              disabled={phase === "running"}
              className="h-10 shrink-0 rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
            >
              {MARKETPLACE_CODES.map((code) => <option key={code} value={code}>{code}</option>)}
            </select>
            <Input
              placeholder="Enter a broad seed keyword"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              disabled={phase === "running"}
            />
            <Button type="submit" disabled={phase === "running" || !seed.trim()}>
              {phase === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span className="ml-2">{phase === "running" ? "Scanning…" : "Discover"}</span>
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted-foreground">
            Scanning {marketplaceLabel(marketplace)}. This scrapes several searches and takes a minute or two.
          </p>
        </CardContent>
      </Card>

      {phase === "failed" && (
        <EmptyState title="Discovery failed" reason={error || "Something went wrong. Try a different seed."} />
      )}

      {phase === "done" && candidates.length === 0 && (
        <EmptyState
          title="No candidates found"
          reason="Amazon returned nothing usable for that seed (or the store was unreachable). Try a broader term."
        />
      )}

      {candidates.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {candidates.map((c) => (
            <Card key={c.keyword}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{c.keyword}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{c.reason}</p>
                  </div>
                  <ScorePill score={c.opportunity_score} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">{c.label}</Badge>
                  <span>Demand: {c.volume_tier.replace("_", " ")}</span>
                  <span>{c.total_results.toLocaleString()} listings</span>
                  <span>{c.brand_count} brands</span>
                  <span>{c.sponsored_count} sponsored</span>
                </div>
                <Button size="sm" className="mt-3" onClick={() => analyze(c.keyword)}>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Analyze this niche
                </Button>
              </CardContent>
            </Card>
          ))}
          <p className="col-span-full text-xs text-muted-foreground flex items-center gap-1">
            <InfoHint text="A quick pre-screen from demand vs. ease of entry — not the full Omniscient Score. Analyze a candidate for the real verdict." />
            Opportunity pre-score: a quick pre-screen, not the full analysis.
          </p>
        </div>
      )}
    </div>
  );
}
