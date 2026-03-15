"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BookOpen,
  Cpu,
  Search,
  ShoppingCart,
  BarChart3,
  MessageSquare,
  Lightbulb,
  Factory,
  DollarSign,
  Star,
  LineChart,
  Award,
  Target,
  TrendingUp,
  Shield,
  Percent,
  Activity,
  Truck,
  Megaphone,
  Rocket,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Server,
} from "lucide-react";

type TabKey = "pipeline" | "scoring" | "api";

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: "pipeline", label: "How It Works", icon: Cpu },
  { key: "scoring", label: "Scoring System", icon: Award },
  { key: "api", label: "API Reference", icon: Server },
];

const PIPELINE_STEPS = [
  {
    step: 1,
    title: "Search Scraping",
    icon: Search,
    description:
      "Playwright scrapes Amazon for 180+ product results across 3 pages of search results for the target keyword.",
  },
  {
    step: 2,
    title: "Product Detail Scraping",
    icon: ShoppingCart,
    description:
      "Top 20 products get detailed page scraping including BSR, price, reviews, listing features, bullet points, and images.",
  },
  {
    step: 3,
    title: "Competitor Analysis",
    icon: BarChart3,
    description:
      "Listing quality scoring and vulnerability detection for each competitor. Identifies weak listings ripe for displacement.",
  },
  {
    step: 4,
    title: "Review Analysis",
    icon: MessageSquare,
    description:
      "LLM-powered pain point extraction from customer reviews. Identifies recurring complaints and unmet needs (when configured).",
  },
  {
    step: 5,
    title: "Product Blueprint",
    icon: Lightbulb,
    description:
      "AI generates improvement priorities, must-have features, and differentiators based on competitor gaps and customer pain points.",
  },
  {
    step: 6,
    title: "Supplier Sourcing",
    icon: Factory,
    description:
      "Scrapes 1688.com for Chinese wholesale suppliers with landed cost calculation including shipping, duties, and Amazon fees.",
  },
  {
    step: 7,
    title: "PPC Strategy",
    icon: Megaphone,
    description:
      "Break-even ACOS calculation, keyword portfolio building, and estimated ad spend for launch and maintenance phases.",
  },
  {
    step: 8,
    title: "Review Strategy",
    icon: Star,
    description:
      "Vine enrollment plan, organic review growth timeline, and review threshold targeting to reach competitive parity.",
  },
  {
    step: 9,
    title: "Financial Projections",
    icon: LineChart,
    description:
      "52-week bull/base/bear scenarios with weekly P&L including revenue, COGS, ad spend, fees, and net profit.",
  },
  {
    step: 10,
    title: "Omniscient Score",
    icon: Award,
    description:
      "9 weighted sub-scores (0-100) combined into a single opportunity score, plus 9 hard disqualification filters.",
  },
];

const SUB_SCORES = [
  { name: "Demand", weight: "15%", icon: Target, description: "Search volume, BSR velocity" },
  { name: "Competition", weight: "15%", icon: Shield, description: "Listing quality, review moats, brand dominance" },
  { name: "Revenue", weight: "12%", icon: DollarSign, description: "Monthly revenue per seller, market size" },
  { name: "Margin", weight: "15%", icon: Percent, description: "Pre/post-PPC profit margins" },
  { name: "Trend", weight: "8%", icon: TrendingUp, description: "Search volume trajectory, seasonality" },
  { name: "Review Feasibility", weight: "10%", icon: Star, description: "How achievable the review moat is" },
  { name: "Supplier", weight: "10%", icon: Truck, description: "Supplier reliability, cost competitiveness" },
  { name: "PPC Viability", weight: "8%", icon: Megaphone, description: "ACOS sustainability, keyword opportunity" },
  { name: "Launch Feasibility", weight: "7%", icon: Rocket, description: "Capital requirements, break-even timeline" },
];

const CONFIDENCE_TIERS = [
  { tier: "HIGH", range: "80-100", color: "bg-tier1", description: "Strong opportunity" },
  { tier: "MEDIUM", range: "60-79", color: "bg-tier2", description: "Viable with caveats" },
  { tier: "LOW", range: "40-59", color: "bg-tier3", description: "Significant risks" },
  { tier: "VERY LOW", range: "20-39", color: "bg-rejected", description: "Major concerns" },
  { tier: "FAIL", range: "--", color: "bg-destructive", description: "One or more hard filters failed" },
];

const HARD_FILTERS = [
  "Price range ($15-$70)",
  "Review moat (median < 2,000)",
  "BSR demand (avg BSR < 50,000)",
  "Minimum margin (pre-PPC > 25%)",
  "Amazon dominance (< 30%)",
  "Restricted category check",
  "IP/patent risk check",
  "Seasonality check",
];

interface EndpointRow {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  description: string;
}

interface EndpointGroup {
  name: string;
  count: number;
  endpoints: EndpointRow[];
}

const API_GROUPS: EndpointGroup[] = [
  {
    name: "Niches",
    count: 10,
    endpoints: [
      { method: "GET", path: "/api/v1/niches", description: "List all analyzed niches with pagination and filtering" },
      { method: "POST", path: "/api/v1/niches/analyze", description: "Start a new niche analysis job" },
      { method: "GET", path: "/api/v1/niches/{id}", description: "Get full niche details and scores" },
      { method: "DELETE", path: "/api/v1/niches/{id}", description: "Delete a niche and all associated data" },
      { method: "GET", path: "/api/v1/niches/{id}/products", description: "List products scraped for a niche" },
      { method: "GET", path: "/api/v1/niches/{id}/competitors", description: "Get competitor analysis results" },
      { method: "GET", path: "/api/v1/niches/{id}/reviews", description: "Get review analysis and pain points" },
      { method: "GET", path: "/api/v1/niches/{id}/suppliers", description: "Get supplier sourcing results" },
      { method: "GET", path: "/api/v1/niches/{id}/ppc", description: "Get PPC strategy and keyword data" },
      { method: "GET", path: "/api/v1/niches/{id}/forecast", description: "Get 52-week financial projections" },
    ],
  },
  {
    name: "Products",
    count: 3,
    endpoints: [
      { method: "GET", path: "/api/v1/products", description: "List all tracked products" },
      { method: "GET", path: "/api/v1/products/{asin}", description: "Get product details by ASIN" },
      { method: "GET", path: "/api/v1/products/{asin}/history", description: "Get BSR and price history time-series" },
    ],
  },
  {
    name: "Recommendations",
    count: 2,
    endpoints: [
      { method: "GET", path: "/api/v1/recommendations", description: "List generated opportunity briefs" },
      { method: "GET", path: "/api/v1/recommendations/{id}", description: "Get full recommendation with all sections" },
    ],
  },
  {
    name: "Jobs",
    count: 3,
    endpoints: [
      { method: "GET", path: "/api/v1/jobs", description: "List all background analysis jobs" },
      { method: "GET", path: "/api/v1/jobs/{id}", description: "Get job status and progress" },
      { method: "POST", path: "/api/v1/jobs/{id}/cancel", description: "Cancel a running analysis job" },
    ],
  },
  {
    name: "Exports",
    count: 2,
    endpoints: [
      { method: "GET", path: "/api/v1/exports/niches/{id}/csv", description: "Export niche data as CSV" },
      { method: "GET", path: "/api/v1/exports/niches/{id}/pdf", description: "Export niche report as PDF" },
    ],
  },
  {
    name: "Settings",
    count: 2,
    endpoints: [
      { method: "GET", path: "/api/v1/settings", description: "Get current user settings and credential status" },
      { method: "PUT", path: "/api/v1/settings", description: "Update API credentials and preferences" },
    ],
  },
  {
    name: "Health",
    count: 1,
    endpoints: [
      { method: "GET", path: "/api/v1/health", description: "Service health check with dependency status" },
    ],
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-tier1/15 text-tier1 border-tier1/30",
  POST: "bg-tier2/15 text-tier2 border-tier2/30",
  PUT: "bg-tier3/15 text-tier3 border-tier3/30",
  DELETE: "bg-rejected/15 text-rejected border-rejected/30",
};

export default function DocsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("pipeline");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <BookOpen className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Documentation</h1>
        </div>
        <p className="text-muted-foreground mt-1">
          How Omniscient analyzes Amazon niches, scores opportunities, and exposes data via API.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "pipeline" && <PipelineTab />}
      {activeTab === "scoring" && <ScoringTab />}
      {activeTab === "api" && <ApiTab />}
    </div>
  );
}

/* ─── How It Works Tab ─── */
function PipelineTab() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          Analysis Pipeline
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Each niche analysis runs through a 10-step pipeline from raw scraping to final scoring.
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-0">
          {PIPELINE_STEPS.map(({ step, title, icon: Icon, description }, idx) => (
            <div key={step} className="relative flex gap-4">
              {/* Timeline connector */}
              <div className="flex flex-col items-center">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10 border border-primary/20 shrink-0">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                {idx < PIPELINE_STEPS.length - 1 && (
                  <div className="w-px flex-1 bg-border my-1" />
                )}
              </div>

              {/* Content */}
              <div className={`pb-8 ${idx === PIPELINE_STEPS.length - 1 ? "pb-0" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="secondary" className="text-xs tabular-nums">
                    Step {step}
                  </Badge>
                  <h3 className="font-semibold">{title}</h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ─── Scoring System Tab ─── */
function ScoringTab() {
  return (
    <div className="space-y-6">
      {/* Sub-scores */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            Sub-Scores
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            The Omniscient Score is a weighted composite of 9 sub-scores, each rated 0-100.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {SUB_SCORES.map(({ name, weight, icon: Icon, description }) => (
              <div
                key={name}
                className="flex items-start gap-3 p-3 rounded-lg border bg-muted/30"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-md bg-primary/10 shrink-0">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{name}</span>
                    <Badge variant="outline" className="text-xs tabular-nums">
                      {weight}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Confidence Tiers */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            Confidence Tiers
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            The final score maps to a confidence tier that summarizes the opportunity quality.
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {CONFIDENCE_TIERS.map(({ tier, range, color, description }) => (
              <div
                key={tier}
                className="flex items-center gap-4 p-3 rounded-lg border bg-muted/30"
              >
                <div className={`w-3 h-3 rounded-full ${color} shrink-0`} />
                <span className="font-mono font-semibold text-sm w-24">{tier}</span>
                <span className="text-sm text-muted-foreground tabular-nums w-16">{range}</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                <span className="text-sm">{description}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Hard Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-destructive" />
            Hard Disqualification Filters
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Any single filter failure overrides the composite score and sets the tier to FAIL.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {HARD_FILTERS.map((filter) => (
              <div
                key={filter}
                className="flex items-center gap-2 p-2.5 rounded-md border bg-muted/30"
              >
                <XCircle className="h-4 w-4 text-destructive shrink-0" />
                <span className="text-sm">{filter}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-start gap-2 p-3 rounded-md bg-destructive/5 border border-destructive/20">
            <CheckCircle2 className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
            <p className="text-sm text-muted-foreground">
              All 8 filters must pass for the niche to receive a numerical score and confidence tier.
              If any filter fails, the niche is marked as <span className="font-semibold text-destructive">FAIL</span> regardless
              of its sub-score performance.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── API Reference Tab ─── */
function ApiTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            REST API Endpoints
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            23 endpoints grouped by resource. Base URL: <code className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono">http://localhost:8000</code>
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Quick summary */}
          <div className="flex flex-wrap gap-2">
            {API_GROUPS.map(({ name, count }) => (
              <Badge key={name} variant="secondary" className="text-xs">
                {name} ({count})
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {API_GROUPS.map(({ name, endpoints }) => (
        <Card key={name}>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">{name}</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="px-6 py-3 w-24">Method</th>
                    <th className="px-6 py-3">Path</th>
                    <th className="px-6 py-3">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.map(({ method, path, description }) => (
                    <tr
                      key={`${method}-${path}`}
                      className="border-b last:border-0 hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-6 py-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-bold font-mono border ${METHOD_COLORS[method]}`}
                        >
                          {method}
                        </span>
                      </td>
                      <td className="px-6 py-3 font-mono text-xs">{path}</td>
                      <td className="px-6 py-3 text-muted-foreground">{description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
