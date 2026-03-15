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

export default function ProductDetailPage() {
  const params = useParams();
  const asin = params.asin as string;

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!asin) return;
    setLoading(true);
    setError(null);

    api
      .get(`/api/v1/products/${asin}`)
      .then((res) => setProduct(res.data))
      .catch((err) => {
        const status = err.response?.status;
        if (status === 404) {
          setError(
            "Product not found. This ASIN may not have been analyzed yet. Add it to a niche and run an analysis to populate product data."
          );
        } else if (status === 500 || !err.response) {
          setError(
            "Unable to connect to the API server. Please make sure the backend is running on http://localhost:8000."
          );
        } else {
          setError(
            `Failed to load product data (${status}). The product-by-ASIN endpoint may not be available yet.`
          );
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
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => window.history.back()}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
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
                <p className="text-muted-foreground max-w-md">{error}</p>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className="font-mono">
                  {asin}
                </Badge>
                <a
                  href={`https://amazon.com/dp/${asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1 text-sm"
                >
                  View on Amazon <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => window.history.back()}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="text-muted-foreground">No product data available.</div>
      </div>
    );
  }

  const estimatedMarginPct =
    product.current_price && product.fba_fee && product.referral_fee_pct
      ? (
          ((product.current_price -
            product.fba_fee -
            product.current_price * (product.referral_fee_pct / 100)) /
            product.current_price) *
          100
        ).toFixed(1)
      : null;

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => window.history.back()}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      {/* Product Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="font-mono text-xs">
              {product.asin}
            </Badge>
            {product.brand && (
              <Badge variant="secondary">{product.brand}</Badge>
            )}
            <a
              href={`https://amazon.com/dp/${product.asin}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1 text-xs"
            >
              View on Amazon <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold leading-tight">
            {product.title || "Untitled Product"}
          </h1>
          <div className="flex items-center gap-4 flex-wrap">
            {product.current_price != null && (
              <span className="text-2xl font-bold text-primary">
                {formatCurrency(product.current_price)}
              </span>
            )}
            {product.current_bsr != null && (
              <span className="text-sm text-muted-foreground">
                BSR #{product.current_bsr.toLocaleString()}
              </span>
            )}
            {product.rating != null && (
              <div className="flex items-center gap-1.5">
                <RatingStars rating={product.rating} />
                <span className="text-sm font-medium">{product.rating}</span>
                {product.review_count != null && (
                  <span className="text-sm text-muted-foreground">
                    ({product.review_count.toLocaleString()} reviews)
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Monthly Revenue"
          value={
            product.estimated_monthly_revenue
              ? formatCurrency(product.estimated_monthly_revenue)
              : "\u2014"
          }
          icon={DollarSign}
        />
        <StatCard
          title="Monthly Units"
          value={
            product.estimated_monthly_units
              ? product.estimated_monthly_units.toLocaleString()
              : "\u2014"
          }
          icon={ShoppingCart}
        />
        <StatCard
          title="Listing Quality"
          value={
            product.listing_quality_score != null
              ? `${product.listing_quality_score}/100`
              : "\u2014"
          }
          icon={BarChart3}
        />
        <StatCard
          title="FBA Fee"
          value={product.fba_fee ? formatCurrency(product.fba_fee) : "\u2014"}
          icon={Truck}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Listing Flags */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Listing Flags</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <ListingFlag label="FBA" value={product.is_fba} icon={Truck} />
              <ListingFlag
                label="Amazon's Choice"
                value={product.is_amazon_choice}
                icon={Award}
              />
              <ListingFlag
                label="Best Seller"
                value={product.is_best_seller}
                icon={TrendingUp}
              />
              <ListingFlag
                label="A+ Content"
                value={product.has_a_plus}
                icon={BookOpen}
              />
              <ListingFlag
                label="Video"
                value={product.has_video}
                icon={Video}
              />
              <ListingFlag
                label="Brand Story"
                value={product.has_brand_story}
                icon={Tag}
              />
            </div>
            <div className="flex items-center gap-4 mt-4 pt-4 border-t text-sm text-muted-foreground">
              {product.image_count != null && (
                <div className="flex items-center gap-1.5">
                  <Image className="h-4 w-4" />
                  <span>
                    {product.image_count} image{product.image_count !== 1 ? "s" : ""}
                  </span>
                </div>
              )}
              {product.bullet_count != null && (
                <div className="flex items-center gap-1.5">
                  <List className="h-4 w-4" />
                  <span>
                    {product.bullet_count} bullet{product.bullet_count !== 1 ? "s" : ""}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Cost Structure */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Cost Structure</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span>Selling Price</span>
                <span className="font-semibold">
                  {product.current_price != null
                    ? formatCurrency(product.current_price)
                    : "\u2014"}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span>FBA Fee</span>
                <span className="font-semibold">
                  {product.fba_fee != null
                    ? formatCurrency(product.fba_fee)
                    : "\u2014"}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Referral Fee</span>
                <span className="font-semibold">
                  {product.referral_fee_pct != null
                    ? formatPercent(product.referral_fee_pct)
                    : "\u2014"}
                  {product.current_price != null && product.referral_fee_pct != null && (
                    <span className="text-muted-foreground ml-1">
                      ({formatCurrency(product.current_price * (product.referral_fee_pct / 100))})
                    </span>
                  )}
                </span>
              </div>
              <div className="border-t pt-3 flex justify-between text-sm">
                <span className="font-semibold">Estimated Margin (pre-COGS)</span>
                <span
                  className={`font-bold ${
                    estimatedMarginPct
                      ? Number(estimatedMarginPct) >= 30
                        ? "text-green-600 dark:text-green-400"
                        : Number(estimatedMarginPct) >= 15
                        ? "text-yellow-600 dark:text-yellow-400"
                        : "text-red-600 dark:text-red-400"
                      : ""
                  }`}
                >
                  {estimatedMarginPct ? `${estimatedMarginPct}%` : "\u2014"}
                </span>
              </div>
              {estimatedMarginPct && (
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      Number(estimatedMarginPct) >= 30
                        ? "bg-green-500"
                        : Number(estimatedMarginPct) >= 15
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${Math.min(Number(estimatedMarginPct), 100)}%` }}
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Product Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Product Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <Weight className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Weight</p>
                <p className="text-sm font-semibold mt-0.5">
                  {product.product_weight_lbs != null
                    ? `${product.product_weight_lbs} lbs`
                    : "\u2014"}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <Ruler className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Dimensions</p>
                <p className="text-sm font-semibold mt-0.5">
                  {product.product_dimensions || "\u2014"}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <Package className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Category</p>
                <p className="text-sm font-semibold mt-0.5">
                  {product.category_id || "\u2014"}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer metadata */}
      <div className="text-xs text-muted-foreground text-right">
        Added {new Date(product.created_at).toLocaleDateString()} | Product ID: {product.id}
        {product.niche_id && <span> | Niche ID: {product.niche_id}</span>}
      </div>
    </div>
  );
}
