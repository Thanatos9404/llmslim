"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "./Card";

export interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  change?: string;
  changeType?: "positive" | "negative" | "neutral";
  icon?: React.ReactNode;
  accentColor?: "emerald" | "cyan" | "violet";
  className?: string;
}

export function MetricCard({
  label,
  value,
  subValue,
  change,
  changeType = "positive",
  icon,
  accentColor = "emerald",
  className,
}: MetricCardProps) {
  const accentClasses = {
    emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    cyan: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    violet: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  };

  return (
    <Card glowColor={accentColor} className={cn("p-6", className)}>
      <div className="flex items-center justify-between gap-4 mb-3">
        <span className="text-xs font-mono uppercase tracking-wider text-slate-400">{label}</span>
        {icon && (
          <div className={cn("p-2 rounded-xl border", accentClasses[accentColor])}>{icon}</div>
        )}
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-3xl sm:text-4xl font-extrabold tracking-tight font-mono text-white"
        >
          {value}
        </motion.span>
        {change && (
          <span
            className={cn(
              "text-xs font-mono px-2 py-0.5 rounded-full border",
              changeType === "positive" && "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
              changeType === "negative" && "text-rose-400 bg-rose-500/10 border-rose-500/20",
              changeType === "neutral" && "text-slate-400 bg-slate-500/10 border-slate-500/20"
            )}
          >
            {change}
          </span>
        )}
      </div>

      {subValue && <p className="text-xs text-slate-400 mt-2 leading-relaxed">{subValue}</p>}
    </Card>
  );
}

export function MetricsGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4", className)}>
      {children}
    </div>
  );
}
