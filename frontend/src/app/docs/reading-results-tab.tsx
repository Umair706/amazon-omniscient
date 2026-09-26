import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { BookOpen } from "lucide-react";

// Every metric a seller sees in a brief, in plain words: what it is, and how
// to act on it. Kept in one list so the glossary stays easy to scan.
const GLOSSARY = [
  {
    term: "Omniscient Score (0-100)",
    meaning: "A weighted blend of nine sub-scores. It ranks how attractive a niche looks overall.",
    read: "Treat it as a shortlist tool, not a verdict. A high score with a failed hard filter is still a FAIL.",
  },
  {
    term: "Confidence tier",
    meaning: "HIGH (80+), MEDIUM (60-79), LOW (40-59), VERY LOW (under 40), or FAIL if any hard filter fails.",
    read: "FAIL means a dealbreaker was hit. HIGH and MEDIUM are worth a closer look; LOW and below rarely justify the capital.",
  },
  {
    term: "BSR (Best Sellers Rank)",
    meaning: "Amazon's popularity rank within a category. Lower is better; rank 500 sells far more than rank 50,000.",
    read: "We convert BSR to an estimated sales figure. A very high BSR is weak demand and can fail the demand filter.",
  },
  {
    term: "Estimated sales / units per month",
    meaning: "Derived from BSR using a category power-law curve. It is a model output, not a measured number.",
    read: "For the US it is calibrated. For Australia it is uncalibrated and flagged as a data gap, so treat AU volumes as rough.",
  },
  {
    term: "Review moat",
    meaning: "The median review count of the competing listings. It measures how entrenched the incumbents are.",
    read: "A high moat means buyers trust established sellers, so you need many reviews to compete. The default ceiling is 2000 (US) or 500 (AU); you can change it in Settings.",
  },
  {
    term: "Review velocity",
    meaning: "How fast competitors gain reviews relative to their sales. An abnormally high rate can signal manipulation.",
    read: "A flagged velocity trap warns that the shelf may be defended with grey-hat review tactics you cannot match cleanly.",
  },
  {
    term: "Margin (pre- and post-PPC)",
    meaning: "Profit as a percent of price. Pre-PPC is after landed cost and Amazon fees; post-PPC also subtracts ad spend.",
    read: "Post-PPC margin is the one that pays you. The default floor is 25% pre-PPC; raise it in Settings if you want more cushion.",
  },
  {
    term: "Landed cost",
    meaning: "The all-in cost to get one unit into an Amazon warehouse: factory price, freight, and duty.",
    read: "If the supplier section is empty, landed cost is assumed, not sourced. Confirm it with a real quote before trusting the margin.",
  },
  {
    term: "FBA fees",
    meaning: "Amazon's referral fee plus the fulfilment fee, estimated from the product's price, weight, and size.",
    read: "Heavy or bulky items eat margin through fulfilment fees. Watch this on low-price products especially.",
  },
  {
    term: "Amazon dominance",
    meaning: "The share of top listings sold by Amazon itself rather than third-party sellers.",
    read: "Above 30% of the shelf being Amazon's own is a hard filter. Competing against Amazon on its own store rarely pays.",
  },
  {
    term: "Opportunity pre-score (Discover)",
    meaning: "A fast demand-versus-ease pre-screen shown on Discover cards. It only looks at search-result signals.",
    read: "It is a filter to decide what to analyse fully, not the real score. Always run a full analysis before deciding.",
  },
  {
    term: "Data gap",
    meaning: "A marker that a value was assumed or estimated because it could not be measured.",
    read: "Every data gap is a place to do your own homework. The more gaps, the less weight the score deserves.",
  },
];

// A scannable glossary that ties each brief metric to a decision.
export function ReadingResultsTab() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Reading your results
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          What each number in a brief means, and what to do about it.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {GLOSSARY.map(({ term, meaning, read }) => (
          <div key={term} className="rounded-lg border bg-muted/30 p-4">
            <p className="font-semibold text-sm">{term}</p>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{meaning}</p>
            <p className="mt-1 text-sm leading-relaxed">
              <span className="font-medium">How to read it: </span>
              <span className="text-muted-foreground">{read}</span>
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
