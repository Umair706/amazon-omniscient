"use client";
import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";
import { motion, useInView } from "framer-motion";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  className?: string;
  index?: number;
}

function AnimatedNumber({ value }: { value: string | number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  const [displayed, setDisplayed] = useState<string | number>(typeof value === "number" ? 0 : value);

  useEffect(() => {
    if (!isInView) return;
    if (typeof value !== "number") {
      setDisplayed(value);
      return;
    }

    const duration = 600;
    const startTime = performance.now();
    const startVal = 0;

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(startVal + (value - startVal) * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [value, isInView]);

  return <span ref={ref}>{displayed}</span>;
}

export function StatCard({ title, value, subtitle, icon: Icon, trend, className, index = 0 }: StatCardProps) {
  const numericValue = typeof value === "string" ? NaN : value;
  const isNumeric = !isNaN(numericValue);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: "easeOut" }}
    >
      <Card className={cn("glass glow-primary", className)}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{title}</p>
              <p className="text-2xl font-bold mt-1">
                {isNumeric ? <AnimatedNumber value={numericValue} /> : value}
              </p>
              {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
              {trend && (
                <p className={cn("text-xs mt-1 font-medium", trend.value >= 0 ? "text-tier1" : "text-rejected")}>
                  {trend.value >= 0 ? "+" : ""}{trend.value}% {trend.label}
                </p>
              )}
            </div>
            <div className="p-3 rounded-lg bg-primary/10">
              <Icon className="h-6 w-6 text-primary" />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
