export default function ProductDetailPage({ params }: { params: { asin: string } }) {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Product: {params.asin}</h1>
      <p className="text-muted-foreground">Loading product data...</p>
    </div>
  );
}
