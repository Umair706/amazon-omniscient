import { Badge } from "@/components/ui/badge";
import { InfoHint } from "@/components/info-hint";
import { marketplaceLabel } from "@/lib/marketplace";

// Human labels for the threshold keys stored in the snapshot.
const THRESHOLD_LABELS: Record<string, string> = {
  price_min: "Min price",
  price_max: "Max price",
  review_moat_max: "Max review moat",
  bsr_max: "Max BSR",
  margin_min: "Min margin %",
  amazon_dominance_max: "Max Amazon %",
  review_velocity_max: "Max review velocity",
};

interface Snapshot {
  engine_version?: string;
  marketplace?: string;
  is_custom?: boolean;
  thresholds?: Record<string, number>;
  sales_multiplier?: number;
  allow_seasonal?: boolean;
}

// Shows the exact rules a recommendation was scored under, so an old result
// stays explainable after the settings change.
export function ScoredUnder({ snapshot, fingerprint }: { snapshot: Snapshot | null; fingerprint: string | null }) {
  if (!snapshot) return null;

  const custom = !!snapshot.is_custom;
  const thresholds = snapshot.thresholds ?? {};

  return (
    <div className="mt-4 pt-4 border-t">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-medium text-muted-foreground">Scored under</p>
        <Badge variant={custom ? "default" : "secondary"} className="text-xs">
          {custom ? "Your custom rules" : "Default rules"}
        </Badge>
        <InfoHint text="The exact scoring rules used for this niche, frozen at analysis time. Two niches are only directly comparable when they share the same rules." />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {marketplaceLabel(snapshot.marketplace)}
        {snapshot.engine_version ? ` · engine v${snapshot.engine_version}` : ""}
        {fingerprint ? ` · rules ${fingerprint}` : ""}
      </p>

      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-primary">Show the exact rules</summary>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-3">
          {Object.entries(THRESHOLD_LABELS).map(([key, label]) => (
            <div key={key} className="flex justify-between gap-2">
              <span>{label}</span>
              <span className="font-medium text-foreground tabular-nums">{thresholds[key] ?? "—"}</span>
            </div>
          ))}
          <div className="flex justify-between gap-2">
            <span>Sales multiplier</span>
            <span className="font-medium text-foreground tabular-nums">{snapshot.sales_multiplier ?? "—"}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span>Allow seasonal</span>
            <span className="font-medium text-foreground">{snapshot.allow_seasonal ? "Yes" : "No"}</span>
          </div>
        </div>
      </details>
    </div>
  );
}
