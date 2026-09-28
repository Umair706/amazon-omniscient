"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { InfoHint } from "@/components/info-hint";
import api from "@/lib/api";
import { MARKETPLACE_CODES, marketplaceLabel } from "@/lib/marketplace";
import type { ScoringConfig, ScoringDefaults } from "@/types";
import { Loader2, RotateCcw, Save } from "lucide-react";

// The numeric threshold fields, in display order, with a plain-English label.
const THRESHOLD_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: "price_min", label: "Min price", hint: "Cheapest acceptable average selling price." },
  { key: "price_max", label: "Max price", hint: "Dearest acceptable average selling price." },
  { key: "review_moat_max", label: "Max review moat", hint: "Most reviews a typical competitor can have before the niche is too hard to enter." },
  { key: "bsr_max", label: "Max BSR", hint: "Worst (highest) average Best Sellers Rank still counted as real demand." },
  { key: "margin_min", label: "Min margin %", hint: "Lowest acceptable pre-PPC profit margin." },
  { key: "amazon_dominance_max", label: "Max Amazon %", hint: "Most of the top shelf Amazon itself can own before you walk away." },
  { key: "review_velocity_max", label: "Max review velocity", hint: "Review-velocity ratio above which a niche looks manipulated." },
];

const WEIGHT_LABELS: Record<string, string> = {
  demand: "Demand",
  competition: "Competition",
  revenue: "Revenue",
  margin: "Margin",
  trend: "Trend",
  review_feasibility: "Review feasibility",
  supplier: "Supplier",
  ppc_viability: "PPC viability",
  launch_feasibility: "Launch feasibility",
};

// A text map keyed by field: "" means "use the default".
type FieldText = Record<string, string>;

// Build the initial per-marketplace text from a stored config (blank when unset).
function thresholdTextFor(marketplace: string, config: ScoringConfig | null): FieldText {
  const stored = config?.thresholds?.[marketplace] ?? {};
  const text: FieldText = {};
  for (const { key } of THRESHOLD_FIELDS) {
    text[key] = stored[key] != null ? String(stored[key]) : "";
  }
  return text;
}

export function ScoringConfigEditor() {
  const [defaults, setDefaults] = useState<ScoringDefaults | null>(null);
  const [thresholdText, setThresholdText] = useState<Record<string, FieldText>>({});
  const [salesText, setSalesText] = useState<Record<string, string>>({});
  const [allowSeasonal, setAllowSeasonal] = useState<Record<string, boolean>>({});
  const [weightText, setWeightText] = useState<FieldText>({});
  const [customWeights, setCustomWeights] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load both the built-in defaults and the seller's stored config, then seed
  // the form from them.
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [defaultsRes, settingsRes] = await Promise.all([
        api.get("/api/v1/settings/scoring-defaults"),
        api.get("/api/v1/settings/"),
      ]);
      const def: ScoringDefaults = defaultsRes.data;
      const config: ScoringConfig | null = settingsRes.data?.scoring_config ?? null;
      setDefaults(def);

      const nextThresholds: Record<string, FieldText> = {};
      const nextSales: Record<string, string> = {};
      const nextSeasonal: Record<string, boolean> = {};
      for (const code of MARKETPLACE_CODES) {
        nextThresholds[code] = thresholdTextFor(code, config);
        nextSales[code] = config?.sales_multiplier?.[code] != null ? String(config.sales_multiplier[code]) : "";
        nextSeasonal[code] = !!config?.allow_seasonal?.[code];
      }
      setThresholdText(nextThresholds);
      setSalesText(nextSales);
      setAllowSeasonal(nextSeasonal);

      const storedWeights = config?.weights;
      setCustomWeights(!!storedWeights);
      const weightSource = storedWeights ?? def.weights;
      const wt: FieldText = {};
      for (const key of Object.keys(def.weights)) {
        // Store weights as whole percents in the form for readability.
        wt[key] = String(Math.round((weightSource[key] ?? 0) * 100));
      }
      setWeightText(wt);
    } catch {
      setMessage({ type: "error", text: "Could not load scoring settings." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const weightPercentTotal = useMemo(
    () => Object.values(weightText).reduce((sum, v) => sum + (parseFloat(v) || 0), 0),
    [weightText],
  );

  // Assemble a scoring_config from the form, omitting anything left at default.
  const buildConfig = useCallback((): ScoringConfig => {
    const config: ScoringConfig = {};

    const thresholds: Record<string, Record<string, number>> = {};
    const salesMultiplier: Record<string, number> = {};
    const seasonal: Record<string, boolean> = {};
    for (const code of MARKETPLACE_CODES) {
      const perMarket: Record<string, number> = {};
      for (const { key } of THRESHOLD_FIELDS) {
        const raw = thresholdText[code]?.[key] ?? "";
        if (raw.trim() !== "") perMarket[key] = Number(raw);
      }
      if (Object.keys(perMarket).length > 0) thresholds[code] = perMarket;

      const salesRaw = salesText[code] ?? "";
      if (salesRaw.trim() !== "") salesMultiplier[code] = Number(salesRaw);

      if (allowSeasonal[code]) seasonal[code] = true;
    }
    if (Object.keys(thresholds).length > 0) config.thresholds = thresholds;
    if (Object.keys(salesMultiplier).length > 0) config.sales_multiplier = salesMultiplier;
    if (Object.keys(seasonal).length > 0) config.allow_seasonal = seasonal;

    // Weights are all-or-nothing: only send them when the seller opted in.
    if (customWeights) {
      const weights: Record<string, number> = {};
      for (const key of Object.keys(weightText)) weights[key] = (parseFloat(weightText[key]) || 0) / 100;
      config.weights = weights;
    }
    return config;
  }, [thresholdText, salesText, allowSeasonal, customWeights, weightText]);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage(null);
    try {
      const config = buildConfig();
      // An empty object means every knob is at default; store null instead.
      const payload = Object.keys(config).length === 0 ? null : config;
      await api.put("/api/v1/settings/", { scoring_config: payload });
      setMessage({ type: "success", text: "Scoring rules saved." });
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const text = detail?.scoring_config?.join(" ") || "Could not save scoring rules.";
      setMessage({ type: "error", text });
    } finally {
      setSaving(false);
    }
  }, [buildConfig, load]);

  const resetAll = useCallback(async () => {
    setSaving(true);
    setMessage(null);
    try {
      await api.put("/api/v1/settings/", { scoring_config: null });
      setMessage({ type: "success", text: "Reset to the built-in defaults." });
      await load();
    } catch {
      setMessage({ type: "error", text: "Could not reset scoring rules." });
    } finally {
      setSaving(false);
    }
  }, [load]);

  const setThreshold = (code: string, key: string, value: string) =>
    setThresholdText((prev) => ({ ...prev, [code]: { ...prev[code], [key]: value } }));

  if (loading || !defaults) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Scoring rules</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading your rules...
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          Scoring rules
          <InfoHint text="Your own definition of a good product. Leave a field blank to use our built-in default for that marketplace." />
        </CardTitle>
        <CardDescription>
          Tune the hard filters, sub-score weights, and sales estimate. Blank means use our default.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
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

        {/* Per-marketplace thresholds */}
        {MARKETPLACE_CODES.map((code) => (
          <div key={code} className="rounded-lg border p-4">
            <h3 className="font-semibold text-sm mb-3">{marketplaceLabel(code)}</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {THRESHOLD_FIELDS.map(({ key, label, hint }) => (
                <div key={key}>
                  <label className="text-xs font-medium flex items-center gap-1">
                    {label}
                    <InfoHint text={hint} />
                  </label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={thresholdText[code]?.[key] ?? ""}
                    onChange={(e) => setThreshold(code, key, e.target.value)}
                    placeholder={`Default: ${defaults.thresholds[code]?.[key]}`}
                  />
                </div>
              ))}
              <div>
                <label className="text-xs font-medium flex items-center gap-1">
                  Sales multiplier
                  <InfoHint text="Scales the BSR-to-sales estimate. Use it to calibrate against real known figures. 1 keeps our curve." />
                </label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={salesText[code] ?? ""}
                  onChange={(e) => setSalesText((p) => ({ ...p, [code]: e.target.value }))}
                  placeholder={`Default: ${defaults.sales_multiplier}`}
                />
              </div>
            </div>
            <label className="mt-3 flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={allowSeasonal[code] ?? false}
                onChange={(e) => setAllowSeasonal((p) => ({ ...p, [code]: e.target.checked }))}
                className="mt-1 h-4 w-4 rounded border-input"
              />
              <span>
                Allow seasonal-only niches
                <span className="block text-xs text-muted-foreground">Off by default.</span>
              </span>
            </label>
          </div>
        ))}

        {/* Sub-score weights */}
        <div className="rounded-lg border p-4">
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={customWeights}
              onChange={(e) => setCustomWeights(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            Customise sub-score weights
          </label>
          <p className="mt-1 text-xs text-muted-foreground">
            How much each factor counts toward the score. They must add up to 100%.
          </p>
          {customWeights && (
            <>
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Object.keys(defaults.weights).map((key) => (
                  <div key={key}>
                    <label className="text-xs font-medium">{WEIGHT_LABELS[key] ?? key}</label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      value={weightText[key] ?? ""}
                      onChange={(e) => setWeightText((p) => ({ ...p, [key]: e.target.value }))}
                      placeholder={`${Math.round((defaults.weights[key] ?? 0) * 100)}`}
                    />
                  </div>
                ))}
              </div>
              <p className={`mt-2 text-xs ${Math.abs(weightPercentTotal - 100) < 0.5 ? "text-muted-foreground" : "text-destructive"}`}>
                Total: {Math.round(weightPercentTotal)}% {Math.abs(weightPercentTotal - 100) < 0.5 ? "" : "(must be 100%)"}
              </p>
            </>
          )}
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={resetAll} disabled={saving}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to defaults
          </Button>
          <Button
            onClick={save}
            disabled={saving || (customWeights && Math.abs(weightPercentTotal - 100) >= 0.5)}
          >
            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            Save scoring rules
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
