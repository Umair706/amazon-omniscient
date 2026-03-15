import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omniscient — Amazon Product Research",
  description: "High-performance Amazon product research engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="w-64 border-r bg-card p-6 hidden md:block">
            <h1 className="text-xl font-bold mb-8">Omniscient</h1>
            <nav className="space-y-2">
              <a href="/" className="block px-3 py-2 rounded-md hover:bg-accent text-sm font-medium">
                Dashboard
              </a>
              <a href="/niches" className="block px-3 py-2 rounded-md hover:bg-accent text-sm font-medium">
                Niche Explorer
              </a>
              <a href="/recommendations" className="block px-3 py-2 rounded-md hover:bg-accent text-sm font-medium">
                Recommendations
              </a>
              <a href="/settings" className="block px-3 py-2 rounded-md hover:bg-accent text-sm font-medium">
                Settings
              </a>
            </nav>
          </aside>

          {/* Main content */}
          <main className="flex-1 p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
