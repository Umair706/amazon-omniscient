import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Compass, Search, FileText, CheckCircle2, AlertTriangle } from "lucide-react";

// The two ways a seller can begin, in the order most people should try them.
const START_PATHS = [
  {
    icon: Compass,
    title: "Start from a broad idea (Discover)",
    body: "Go to Discover, type a broad seed like \"kitchen gadgets\", and pick your marketplace. Omniscient expands the seed into real sub-niches, does a quick pre-screen of each, and ranks them. Use this when you do not yet have a specific product in mind.",
  },
  {
    icon: Search,
    title: "Start from a keyword you already have (Analyse)",
    body: "On the Dashboard, enter a specific keyword like \"silicone baking mat\". Omniscient runs the full analysis and produces a scored recommendation. Use this when you already know the product you want to check.",
  },
];

// A plain-English checklist a seller uses to read a finished brief.
const DECISION_CHECKLIST = [
  {
    label: "Does it pass every hard filter?",
    body: "One failed filter sets the tier to FAIL no matter how good the score is. A FAIL means walk away, or retune the rule in Settings > Scoring rules if the filter does not match your strategy. Every threshold, the sub-score weights, and the sales estimate are yours to change, per marketplace, with our defaults built in.",
  },
  {
    label: "Is the money real after all costs?",
    body: "Look at the margin after landed cost, Amazon fees, and PPC. A high price with a thin post-PPC margin is a trap. Aim for margin that survives a bad launch, not just an average one.",
  },
  {
    label: "Can you actually win the shelf?",
    body: "Check the review moat and Amazon dominance. If the top sellers each have thousands of reviews, or Amazon itself owns the shelf, breaking in costs far more than the score alone suggests.",
  },
  {
    label: "Can you source it?",
    body: "Check the supplier section. If it is empty or marked as a data gap, treat sourcing as unproven. You cannot sell what you cannot buy at the modelled cost.",
  },
];

// Turn a broad seed into a shortlist, then analyse the best, then decide.
export function GettingStartedTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Compass className="h-5 w-5 text-primary" />
            Two ways to start
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Pick your marketplace first. It changes the thresholds and the sales model, so an AU run is judged by AU rules, not US ones.
          </p>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {START_PATHS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-lg border bg-muted/30 p-4">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 shrink-0">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <h3 className="font-semibold text-sm">{title}</h3>
              </div>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{body}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Reading a recommendation like a seller
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            The score is a starting point, not the decision. Work through these four questions before you commit capital.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {DECISION_CHECKLIST.map(({ label, body }, index) => (
            <div key={label} className="flex gap-3 rounded-lg border bg-muted/30 p-3">
              <Badge variant="secondary" className="h-6 shrink-0 tabular-nums">{index + 1}</Badge>
              <div>
                <p className="font-medium text-sm">{label}</p>
                <p className="mt-0.5 text-sm text-muted-foreground leading-relaxed">{body}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-primary" />
            What the tool will and will not claim
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground leading-relaxed">
          <p className="flex gap-2">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-tier1" />
            When a number is measured from a real listing, it is shown as a fact.
          </p>
          <p className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-tier3" />
            When a number is estimated or assumed, it is flagged as a data gap so you never mistake a guess for a measurement. The Australian sales estimate, for example, is uncalibrated and labelled as such.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
