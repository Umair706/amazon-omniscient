import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omniscient — Amazon Product Research",
  description: "High-performance Amazon product research engine",
};

// Applies the saved theme before first paint so there is no light/dark flash.
// Default is dark (the app's original look); users switch via the sidebar toggle.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('omni_theme')||'dark';var dark=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',dark);}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
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
