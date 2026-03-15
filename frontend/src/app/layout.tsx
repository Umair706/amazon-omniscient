import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
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
          <Sidebar />
          <main className="flex-1 p-8 md:p-8 pt-16 md:pt-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
