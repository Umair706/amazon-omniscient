"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import type { UserSettings } from "@/types";
import { Save, Loader2, Download, Eye, EyeOff } from "lucide-react";

export default function SettingsPage() {
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
  const [defaultMarketplace, setDefaultMarketplace] = useState("US");

  useEffect(() => {
    api
      .get("/api/v1/settings/")
      .then((res) => {
        const data: UserSettings = res.data;
        setSettings(data);
        setDefaultMarketplace(data.default_marketplace || "US");
      })
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

      await api.put("/api/v1/settings/", payload);
      setMessage({ type: "success", text: "Settings saved successfully" });
      // Clear secret fields after save
      setSpApiClientSecret("");
      setAdsClientSecret("");
      setLlmApiKey("");

      // Refresh settings state
      const res = await api.get("/api/v1/settings/");
      setSettings(res.data);
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
    } catch {
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
          <CardTitle className="text-lg">Preferences</CardTitle>
          <CardDescription>Analysis defaults and marketplace</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Default Marketplace</label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={defaultMarketplace}
              onChange={(e) => setDefaultMarketplace(e.target.value)}
            >
              <option value="US">United States (US)</option>
              <option value="AU">Australia (AU)</option>
              <option value="UK">United Kingdom (UK)</option>
              <option value="DE">Germany (DE)</option>
              <option value="CA">Canada (CA)</option>
              <option value="JP">Japan (JP)</option>
            </select>
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
          <Button variant="outline" onClick={() => handleExportCsv()}>
            <Download className="h-4 w-4 mr-2" /> Export Latest Niche (CSV)
          </Button>
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
