"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { useLicense } from "@/lib/use-license";
import type { UserSettings } from "@/types";
import { Save, Loader2, Download, Eye, EyeOff, Lock } from "lucide-react";

export default function SettingsPage() {
  const { has } = useLicense();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSecrets, setShowSecrets] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form state
  const [spApiClientId, setSpApiClientId] = useState("");
  const [spApiClientSecret, setSpApiClientSecret] = useState("");
  const [spApiRefreshToken, setSpApiRefreshToken] = useState("");
  const [adsClientId, setAdsClientId] = useState("");
  const [adsClientSecret, setAdsClientSecret] = useState("");
  const [adsRefreshToken, setAdsRefreshToken] = useState("");
  const [llmProvider, setLlmProvider] = useState("qwen");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [defaultMarketplace, setDefaultMarketplace] = useState("AU");
  const [minMargin, setMinMargin] = useState("");
  const [maxReviewMoat, setMaxReviewMoat] = useState("");
  const [allowSeasonal, setAllowSeasonal] = useState(false);

  // Load the stored settings into the form. Blank threshold fields mean
  // "use the smart per-marketplace default", so a null value stays blank.
  const syncFormFromSettings = (data: UserSettings) => {
    setSettings(data);
    setDefaultMarketplace(data.default_marketplace || "AU");
    setMinMargin(data.min_margin_threshold != null ? String(data.min_margin_threshold) : "");
    setMaxReviewMoat(data.max_review_moat != null ? String(data.max_review_moat) : "");
    setAllowSeasonal(!!data.allow_seasonal);
  };

  useEffect(() => {
    api
      .get("/api/v1/settings/")
      .then((res) => syncFormFromSettings(res.data as UserSettings))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {};

      // SP-API credentials — send as dict if any field filled
      if (spApiClientId || spApiClientSecret || spApiRefreshToken) {
        payload.sp_api_credentials = {
          client_id: spApiClientId || undefined,
          client_secret: spApiClientSecret || undefined,
          refresh_token: spApiRefreshToken || undefined,
        };
      }

      // Ads API credentials
      if (adsClientId || adsClientSecret || adsRefreshToken) {
        payload.ads_api_credentials = {
          client_id: adsClientId || undefined,
          client_secret: adsClientSecret || undefined,
          refresh_token: adsRefreshToken || undefined,
        };
      }

      // Preferences
      if (defaultMarketplace) payload.default_marketplace = defaultMarketplace;

      // Threshold overrides. A blank field sends null, which reverts that
      // filter to the marketplace default rather than forcing a value.
      payload.min_margin_threshold = minMargin.trim() === "" ? null : Number(minMargin);
      payload.max_review_moat = maxReviewMoat.trim() === "" ? null : Number(maxReviewMoat);
      payload.allow_seasonal = allowSeasonal;

      await api.put("/api/v1/settings/", payload);
      setMessage({ type: "success", text: "Settings saved successfully" });
      // Clear secret fields after save
      setSpApiClientSecret("");
      setAdsClientSecret("");
      setLlmApiKey("");

      // Refresh settings state and re-sync the form to normalised values
      const res = await api.get("/api/v1/settings/");
      syncFormFromSettings(res.data as UserSettings);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setMessage({ type: "error", text: error.response?.data?.detail || "Failed to save settings" });
    } finally {
      setSaving(false);
    }
  };

  const handleExportCsv = async (nicheId?: number) => {
    try {
      // If no niche ID given, fetch the first niche
      let targetId = nicheId;
      if (!targetId) {
        const res = await api.get("/api/v1/niches/", { params: { per_page: 1 } });
        const items = res.data.items || [];
        if (items.length === 0) {
          setMessage({ type: "error", text: "No niches to export. Analyze a niche first." });
          return;
        }
        targetId = items[0].id;
      }
      const res = await api.get(`/api/v1/exports/niches/${targetId}/csv`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `omniscient-export-${new Date().toISOString().split("T")[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      if (err?.response?.status === 402) {
        setMessage({ type: "error", text: "CSV export is a Pro feature. See docs/LICENSING.md to obtain a key." });
        return;
      }
      setMessage({ type: "error", text: "Export failed. Make sure you have analyzed at least one niche." });
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">Configure API credentials and preferences</p>
      </div>

      {message && (
        <div
          className={`p-3 rounded-md text-sm ${
            message.type === "success"
              ? "bg-tier1/10 text-tier1 border border-tier1/20"
              : "bg-destructive/10 text-destructive border border-destructive/20"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Amazon SP-API */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Amazon SP-API</CardTitle>
              <CardDescription>Seller Partner API credentials for product data</CardDescription>
            </div>
            <Badge variant={settings?.has_sp_api_credentials ? "default" : "secondary"}>
              {settings?.has_sp_api_credentials ? "Configured" : "Not Configured"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Client ID</label>
            <Input value={spApiClientId} onChange={(e) => setSpApiClientId(e.target.value)} placeholder="amzn1.application-oa2-client.xxx" />
          </div>
          <div>
            <label className="text-sm font-medium">Client Secret</label>
            <div className="relative">
              <Input
                type={showSecrets ? "text" : "password"}
                value={spApiClientSecret}
                onChange={(e) => setSpApiClientSecret(e.target.value)}
                placeholder="Leave blank to keep existing"
              />
              <button
                type="button"
                onClick={() => setShowSecrets(!showSecrets)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showSecrets ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Refresh Token</label>
            <Input
              type={showSecrets ? "text" : "password"}
              value={spApiRefreshToken}
              onChange={(e) => setSpApiRefreshToken(e.target.value)}
              placeholder="Leave blank to keep existing"
            />
          </div>
        </CardContent>
      </Card>

      {/* Amazon Ads API */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Amazon Advertising API</CardTitle>
              <CardDescription>For PPC data and campaign management</CardDescription>
            </div>
            <Badge variant={settings?.has_ads_api_credentials ? "default" : "secondary"}>
              {settings?.has_ads_api_credentials ? "Configured" : "Not Configured"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Client ID</label>
            <Input value={adsClientId} onChange={(e) => setAdsClientId(e.target.value)} placeholder="amzn1.application-oa2-client.xxx" />
          </div>
          <div>
            <label className="text-sm font-medium">Client Secret</label>
            <Input
              type={showSecrets ? "text" : "password"}
              value={adsClientSecret}
              onChange={(e) => setAdsClientSecret(e.target.value)}
              placeholder="Leave blank to keep existing"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Refresh Token</label>
            <Input
              type={showSecrets ? "text" : "password"}
              value={adsRefreshToken}
              onChange={(e) => setAdsRefreshToken(e.target.value)}
              placeholder="Leave blank to keep existing"
            />
          </div>
        </CardContent>
      </Card>

      {/* LLM Config */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">LLM Provider</CardTitle>
          <CardDescription>Configure the AI model used for analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Provider</label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
            >
              <option value="qwen">Qwen (Default)</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
              <option value="ollama">Ollama (Local)</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Model</label>
            <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} placeholder="e.g., qwen-max-latest" />
          </div>
          <div>
            <label className="text-sm font-medium">API Key</label>
            <Input
              type={showSecrets ? "text" : "password"}
              value={llmApiKey}
              onChange={(e) => setLlmApiKey(e.target.value)}
              placeholder="Leave blank to keep existing"
            />
          </div>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Analysis preferences</CardTitle>
          <CardDescription>
            Your default marketplace and the hard-filter thresholds used when scoring a niche.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Default marketplace</label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={defaultMarketplace}
              onChange={(e) => setDefaultMarketplace(e.target.value)}
            >
              <option value="AU">Australia — Amazon.com.au (AU)</option>
              <option value="US">United States — Amazon.com (US)</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">Minimum margin %</label>
            <Input
              type="number"
              inputMode="decimal"
              value={minMargin}
              onChange={(e) => setMinMargin(e.target.value)}
              placeholder="Leave blank to use the marketplace default (25%)"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              A niche whose pre-PPC margin falls below this is disqualified. Blank uses the default for your marketplace.
            </p>
          </div>

          <div>
            <label className="text-sm font-medium">Maximum review moat</label>
            <Input
              type="number"
              inputMode="numeric"
              value={maxReviewMoat}
              onChange={(e) => setMaxReviewMoat(e.target.value)}
              placeholder="Leave blank to use the marketplace default (US 2000, AU 500)"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              The most reviews a typical competitor can have before the niche is too hard to break into. Blank uses the marketplace default.
            </p>
          </div>

          <div className="flex items-start gap-2">
            <input
              id="allow-seasonal"
              type="checkbox"
              checked={allowSeasonal}
              onChange={(e) => setAllowSeasonal(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-input"
            />
            <label htmlFor="allow-seasonal" className="text-sm">
              Allow seasonal-only niches
              <span className="block text-xs text-muted-foreground">
                Off by default. When off, a niche with demand only part of the year is disqualified.
              </span>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Export */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Data Export</CardTitle>
          <CardDescription>Export your analysis data</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => handleExportCsv()} disabled={!has("export")}>
            {has("export") ? <Download className="h-4 w-4 mr-2" /> : <Lock className="h-4 w-4 mr-2" />}
            Export Latest Niche (CSV)
          </Button>
          {!has("export") && (
            <p className="text-xs text-muted-foreground mt-2">
              CSV and PDF export is a Pro feature. See docs/LICENSING.md to obtain a license key.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
          {saving ? "Saving..." : "Save Settings"}
        </Button>
      </div>
    </div>
  );
}
