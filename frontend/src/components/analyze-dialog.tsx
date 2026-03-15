"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import api from "@/lib/api";
import { Search, Loader2 } from "lucide-react";

interface AnalyzeDialogProps {
  onJobStarted?: (taskId: string) => void;
}

export function AnalyzeDialog({ onJobStarted }: AnalyzeDialogProps) {
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await api.post("/api/v1/jobs/analyze", { keyword: keyword.trim() });
      onJobStarted?.(res.data.task_id);
      setKeyword("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Analyze New Niche</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Enter a niche keyword (e.g., 'silicone kitchen utensils')"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              disabled={loading}
            />
            <Button type="submit" disabled={loading || !keyword.trim()}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span className="ml-2">{loading ? "Analyzing..." : "Analyze"}</span>
            </Button>
          </div>
          {error && <p className="text-sm text-destructive mt-2">{error}</p>}
        </CardContent>
      </form>
    </Card>
  );
}
