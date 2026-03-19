"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/stat-card";
import { formatCurrency, formatPercent } from "@/lib/utils";
import api from "@/lib/api";
import {
  ArrowLeft,
  DollarSign,
  TrendingUp,
  ShoppingCart,
  Star,
  Package,
  BarChart3,
  ExternalLink,
  Award,
  Truck,
  Video,
  BookOpen,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Ruler,
  Weight,
  Tag,
  Image,
  List,
  Calendar,
  Users,
  MessageSquare,
  Layers,
  Zap,
  Link2,
} from "lucide-react";

interface Product {
  id: number;
  asin: string;
  niche_id: number | null;
  title: string | null;
  brand: string | null;
  category_id: string | null;
  current_price: number | null;
  current_bsr: number | null;
  review_count: number | null;
  rating: number | null;
  is_fba: boolean | null;
  is_amazon_choice: boolean | null;
  is_best_seller: boolean | null;
  has_a_plus: boolean | null;
  has_video: boolean | null;
  has_brand_story: boolean | null;
  image_count: number | null;
  bullet_count: number | null;
  estimated_monthly_units: number | null;
  estimated_monthly_revenue: number | null;
  listing_quality_score: number | null;
  fba_fee: number | null;
  referral_fee_pct: number | null;
  product_weight_lbs: number | null;
  product_dimensions: string | null;
  created_at: string;
  // Search position
  search_position: number | null;
  // Enriched fields
  list_price: number | null;
  date_first_available: string | null;
  star_distribution: Record<string, number> | null;
  variation_count: number | null;
  category_path: string | null;
  seller_count: number | null;
  fbt_asins: string[] | null;
  qa_count: number | null;
  deal_badge: string | null;
  amazons_choice_keyword: string | null;
  review_attributes: Array<{
    attribute: string;
    percentage: string;
    sentiment: string;
  }> | null;
  comparison_asins: string[] | null;
  weight: string | null;
}

function RatingStars({ rating }: { rating: number }) {
  const fullStars = Math.floor(rating);
  const hasHalf = rating - fullStars >= 0.25 && rating - fullStars < 0.75;
  const emptyStars = 5 - fullStars - (hasHalf ? 1 : 0);

  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: fullStars }).map((_, i) => (
        <Star key={`full-${i}`} className="h-4 w-4 fill-yellow-400 text-yellow-400" />
      ))}
      {hasHalf && (
        <div className="relative">
          <Star className="h-4 w-4 text-muted-foreground/30" />
          <div className="absolute inset-0 overflow-hidden w-[50%]">
            <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
          </div>
        </div>
      )}
      {Array.from({ length: emptyStars }).map((_, i) => (
        <Star key={`empty-${i}`} className="h-4 w-4 text-muted-foreground/30" />
      ))}
    </div>
  );
}

function ListingFlag({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: boolean | null;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const isActive = value === true;
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
        isActive
          ? "bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400"
          : "bg-muted/50 border-muted text-muted-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
      <span className="text-sm font-medium">{label}</span>
      {isActive ? (
        <CheckCircle2 className="h-3.5 w-3.5 ml-auto" />
      ) : (
        <XCircle className="h-3.5 w-3.5 ml-auto opacity-40" />
      )}
    </div>
  );
}

function StarDistributionBar({ distribution }: { distribution: Record<string, number> }) {
  const stars = [5, 4, 3, 2, 1];
  return (
    <div className="space-y-1.5">
      {stars.map((s) => {
        const pct = distribution[`${s}_star`] || 0;
        return (
          <div key={s} className="flex items-center gap-2 text-xs">
            <span className="w-12 text-right text-muted-foreground">{s} star</span>
            <div className="flex-1 h-3 rounded-full bg-secondary overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  s >= 4 ? "bg-green-500" : s === 3 ? "bg-yellow-500" : "bg-red-500"
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-10 text-right font-medium">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

export default function ProductDetailPage() {
  const params = useParams();
  const asin = params.asin as string;

  const [product, setProduct] = useState<Product | null>(null);
  const [velocity, setVelocity] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!asin) return;
    setLoading(true);
    setError(null);

    api.get(`/api/v1/products/${asin}/velocity`).then((res) => setVelocity(res.data)).catch(() => {});

    api
      .get(`/api/v1/products/${asin}`)
      .then((res) => setProduct(res.data))
      .catch((err) => {
        const status = err.response?.status;
        if (status === 404) {
          setError("Product not found. This ASIN may not have been analyzed yet.");
        } else if (status === 500 || !err.response) {
          setError("Unable to connect to the API server.");
        } else {
          setError(`Failed to load product data (${status}).`);
        }
      })
      .finally(() => setLoading(false));
  }, [asin]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-10 w-96" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="space-y-6">
        <button onClick={() => window.history.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <Card>
          <CardContent className="p-8">
            <div className="flex flex-col items-center text-center gap-4">
              <div className="p-4 rounded-full bg-orange-500/10">
                <AlertTriangle className="h-8 w-8 text-orange-500" />
              </div>
              <div>
                <h2 className="text-xl font-semibold mb-2">Product Unavailable</h2>
                <p className="text-muted-foreground max-w-md">{error || "No product data available."}</p>
              </div>
              <Badge variant="outline" className="font-mono">{asin}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const estimatedMarginPct =
    product.current_price && product.fba_fee && product.referral_fee_pct
      ? (((product.current_price - product.fba_fee - product.current_price * (product.referral_fee_pct / 100)) / product.current_price) * 100).toFixed(1)
      : null;

  const discountPct =
    product.list_price && product.current_price && product.list_price > product.current_price
      ? (((product.list_price - product.current_price) / product.list_price) * 100).toFixed(0)
      : null;

  return (
    <div className="space-y-6">
      <button onClick={() => window.history.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      {/* Product Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="font-mono text-xs">{product.asin}</Badge>
          {product.brand && <Badge variant="secondary">{product.brand}</Badge>}
          {product.deal_badge && (
            <Badge className="bg-red-500 text-white">{product.deal_badge}</Badge>
          )}
          {product.amazons_choice_keyword && (
            <Badge className="bg-orange-500 text-white">
              Amazon&apos;s Choice{product.amazons_choice_keyword !== "(badge present)" ? ` for "${product.amazons_choice_keyword}"` : ""}
            </Badge>
          )}
          <a href={`https://amazon.com/dp/${product.asin}`} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1 text-xs">
            View on Amazon <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <h1 className="text-2xl md:text-3xl font-bold leading-tight">{product.title || "Untitled Product"}</h1>

        {/* Category breadcrumb */}
        {product.category_path && (
          <p className="text-xs text-muted-foreground">{product.category_path}</p>
        )}

        <div className="flex items-center gap-4 flex-wrap">
          {product.current_price != null && (
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-primary">{formatCurrency(product.current_price)}</span>
              {product.list_price != null && product.list_price > product.current_price && (
                <>
                  <span className="text-sm text-muted-foreground line-through">{formatCurrency(product.list_price)}</span>
                  {discountPct && <Badge variant="destructive" className="text-xs">-{discountPct}%</Badge>}
                </>
              )}
            </div>
          )}
          {product.search_position != null && (
            <Badge variant="outline" className="text-xs">Rank #{product.search_position}</Badge>
          )}
          {product.current_bsr != null && (
            <span className="text-sm text-muted-foreground">BSR #{product.current_bsr.toLocaleString()}</span>
          )}
          {product.rating != null && (
            <div className="flex items-center gap-1.5">
              <RatingStars rating={product.rating} />
              <span className="text-sm font-medium">{product.rating}</span>
              {product.review_count != null && (
                <span className="text-sm text-muted-foreground">({product.review_count.toLocaleString()} reviews)</span>
              )}
            </div>
          )}
          {product.date_first_available && (
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" />
              <span>Listed {product.date_first_available}</span>
            </div>
          )}
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard title="Monthly Revenue" value={product.estimated_monthly_revenue ? formatCurrency(product.estimated_monthly_revenue) : "\u2014"} icon={DollarSign} />
        <StatCard title="Monthly Units" value={product.estimated_monthly_units ? product.estimated_monthly_units.toLocaleString() : "\u2014"} icon={ShoppingCart} />
        <StatCard title="Listing Quality" value={product.listing_quality_score != null ? `${product.listing_quality_score}/100` : "\u2014"} icon={BarChart3} />
        <StatCard title="FBA Fee" value={product.fba_fee ? formatCurrency(product.fba_fee) : "\u2014"} icon={Truck} />
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {product.variation_count != null && (
          <div className="flex items-center gap-2 p-3 rounded-lg border bg-card">
            <Layers className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{product.variation_count}</p>
              <p className="text-xs text-muted-foreground">Variations</p>
            </div>
          </div>
        )}
        {product.seller_count != null && (
          <div className="flex items-center gap-2 p-3 rounded-lg border bg-card">
            <Users className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{product.seller_count}</p>
              <p className="text-xs text-muted-foreground">Sellers</p>
            </div>
          </div>
        )}
        {product.qa_count != null && (
          <div className="flex items-center gap-2 p-3 rounded-lg border bg-card">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{product.qa_count}</p>
              <p className="text-xs text-muted-foreground">Q&amp;A</p>
            </div>
          </div>
        )}
        {product.fbt_asins && product.fbt_asins.length > 0 && (
          <div className="flex items-center gap-2 p-3 rounded-lg border bg-card">
            <Link2 className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{product.fbt_asins.length}</p>
              <p className="text-xs text-muted-foreground">FBT Products</p>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Listing Flags */}
        <Card>
          <CardHeader><CardTitle className="text-lg">Listing Flags</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <ListingFlag label="FBA" value={product.is_fba} icon={Truck} />
              <ListingFlag label="Amazon's Choice" value={product.is_amazon_choice} icon={Award} />
              <ListingFlag label="Best Seller" value={product.is_best_seller} icon={TrendingUp} />
              <ListingFlag label="A+ Content" value={product.has_a_plus} icon={BookOpen} />
              <ListingFlag label="Video" value={product.has_video} icon={Video} />
              <ListingFlag label="Brand Story" value={product.has_brand_story} icon={Tag} />
            </div>
            <div className="flex items-center gap-4 mt-4 pt-4 border-t text-sm text-muted-foreground">
              {product.image_count != null && (
                <div className="flex items-center gap-1.5">
                  <Image className="h-4 w-4" />
                  <span>{product.image_count} image{product.image_count !== 1 ? "s" : ""}</span>
                </div>
              )}
              {product.bullet_count != null && (
                <div className="flex items-center gap-1.5">
                  <List className="h-4 w-4" />
                  <span>{product.bullet_count} bullet{product.bullet_count !== 1 ? "s" : ""}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Star Distribution */}
        {product.star_distribution && Object.keys(product.star_distribution).length > 0 ? (
          <Card>
            <CardHeader><CardTitle className="text-lg">Rating Distribution</CardTitle></CardHeader>
            <CardContent>
              <StarDistributionBar distribution={product.star_distribution} />
              {product.review_count != null && (
                <p className="text-xs text-muted-foreground mt-3 pt-3 border-t">
                  Based on {product.review_count.toLocaleString()} ratings
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader><CardTitle className="text-lg">Cost Structure</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span>Selling Price</span>
                  <span className="font-semibold">{product.current_price != null ? formatCurrency(product.current_price) : "\u2014"}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>FBA Fee</span>
                  <span className="font-semibold">{product.fba_fee != null ? formatCurrency(product.fba_fee) : "\u2014"}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Referral Fee</span>
                  <span className="font-semibold">{product.referral_fee_pct != null ? formatPercent(product.referral_fee_pct) : "\u2014"}</span>
                </div>
                <div className="border-t pt-3 flex justify-between text-sm">
                  <span className="font-semibold">Estimated Margin</span>
                  <span className={`font-bold ${estimatedMarginPct ? (Number(estimatedMarginPct) >= 30 ? "text-green-600 dark:text-green-400" : Number(estimatedMarginPct) >= 15 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400") : ""}`}>
                    {estimatedMarginPct ? `${estimatedMarginPct}%` : "\u2014"}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Cost Structure (shown if star distribution took the other slot) */}
      {product.star_distribution && Object.keys(product.star_distribution).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Cost Structure</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Selling Price</p>
                <p className="text-lg font-bold">{product.current_price != null ? formatCurrency(product.current_price) : "\u2014"}</p>
              </div>
              {product.list_price != null && (
                <div>
                  <p className="text-xs text-muted-foreground">List Price</p>
                  <p className="text-lg font-bold text-muted-foreground line-through">{formatCurrency(product.list_price)}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-muted-foreground">FBA Fee</p>
                <p className="text-lg font-bold">{product.fba_fee != null ? formatCurrency(product.fba_fee) : "\u2014"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Referral Fee</p>
                <p className="text-lg font-bold">{product.referral_fee_pct != null ? `${product.referral_fee_pct}%` : "\u2014"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Est. Margin</p>
                <p className={`text-lg font-bold ${estimatedMarginPct ? (Number(estimatedMarginPct) >= 30 ? "text-green-600 dark:text-green-400" : Number(estimatedMarginPct) >= 15 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400") : ""}`}>
                  {estimatedMarginPct ? `${estimatedMarginPct}%` : "\u2014"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Review Attributes */}
      {product.review_attributes && product.review_attributes.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Customer Sentiment</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {product.review_attributes.map((attr, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border">
                  <span className="text-sm font-medium">{attr.attribute}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold">{attr.percentage}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      attr.sentiment === "positive" ? "bg-green-500/10 text-green-600 dark:text-green-400" :
                      attr.sentiment === "negative" ? "bg-red-500/10 text-red-600 dark:text-red-400" :
                      "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                    }`}>
                      {attr.sentiment}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sales Velocity */}
      {velocity && velocity.timeseries && velocity.timeseries.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Sales Velocity</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-2xl font-bold">{velocity.estimated_daily_sales ?? "\u2014"}</div>
                <div className="text-xs text-muted-foreground">Est. Daily Sales</div>
              </div>
              <div>
                <div className={`text-2xl font-bold ${velocity.sales_velocity_trend === "increasing" ? "text-green-600 dark:text-green-400" : velocity.sales_velocity_trend === "decreasing" ? "text-red-600 dark:text-red-400" : ""}`}>
                  {velocity.sales_velocity_trend === "increasing" ? "↑" : velocity.sales_velocity_trend === "decreasing" ? "↓" : "→"}{" "}
                  {velocity.sales_velocity_trend || "unknown"}
                </div>
                <div className="text-xs text-muted-foreground">Trend</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{velocity.last_stock_level ?? "\u2014"}</div>
                <div className="text-xs text-muted-foreground">Last Stock Level</div>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="p-2 text-left">Date</th>
                    <th className="p-2 text-right">Est. Sales</th>
                    <th className="p-2 text-right">BSR Delta</th>
                    <th className="p-2 text-right">Stock</th>
                    <th className="p-2 text-left">Method</th>
                  </tr>
                </thead>
                <tbody>
                  {velocity.timeseries.slice(-14).map((point: any, i: number) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="p-2">{point.date}</td>
                      <td className="p-2 text-right font-medium">{point.estimated_daily_sales ?? "\u2014"}</td>
                      <td className="p-2 text-right">{point.bsr_delta ?? "\u2014"}</td>
                      <td className="p-2 text-right">{point.stock_end ?? "\u2014"}</td>
                      <td className="p-2"><span className="px-1.5 py-0.5 rounded bg-muted text-xs">{point.estimation_method || "\u2014"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Product Details */}
      <Card>
        <CardHeader><CardTitle className="text-lg">Product Details</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted"><Weight className="h-5 w-5 text-muted-foreground" /></div>
              <div>
                <p className="text-xs text-muted-foreground">Weight</p>
                <p className="text-sm font-semibold mt-0.5">
                  {product.weight || (product.product_weight_lbs != null ? `${product.product_weight_lbs} lbs` : "\u2014")}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted"><Ruler className="h-5 w-5 text-muted-foreground" /></div>
              <div>
                <p className="text-xs text-muted-foreground">Dimensions</p>
                <p className="text-sm font-semibold mt-0.5">{product.product_dimensions || "\u2014"}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted"><Package className="h-5 w-5 text-muted-foreground" /></div>
              <div>
                <p className="text-xs text-muted-foreground">Category</p>
                <p className="text-sm font-semibold mt-0.5">{product.category_path || product.category_id || "\u2014"}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Frequently Bought Together */}
      {product.fbt_asins && product.fbt_asins.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Frequently Bought Together</CardTitle></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {product.fbt_asins.map((fbtAsin) => (
                <a key={fbtAsin} href={`/products/${fbtAsin}`} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border hover:bg-muted transition-colors text-sm font-mono">
                  {fbtAsin}
                  <ExternalLink className="h-3 w-3 text-muted-foreground" />
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comparison ASINs */}
      {product.comparison_asins && product.comparison_asins.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Amazon Comparison Products</CardTitle></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {product.comparison_asins.map((compAsin) => (
                <a key={compAsin} href={`/products/${compAsin}`} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border hover:bg-muted transition-colors text-sm font-mono">
                  {compAsin}
                  <ExternalLink className="h-3 w-3 text-muted-foreground" />
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Footer metadata */}
      <div className="text-xs text-muted-foreground text-right">
        Added {new Date(product.created_at).toLocaleDateString()} | Product ID: {product.id}
        {product.niche_id && <span> | Niche ID: {product.niche_id}</span>}
      </div>
    </div>
  );
}
