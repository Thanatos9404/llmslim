"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AuroraBackgroundProps {
  children?: React.ReactNode;
  className?: string;
  showRadialGradient?: boolean;
}

export function AuroraBackground({
  children,
  className,
  showRadialGradient = true,
}: AuroraBackgroundProps) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center min-h-screen bg-[#030508] text-slate-100 transition-colors overflow-hidden",
        className
      )}
    >
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{
            scale: [1, 1.08, 1],
            opacity: [0.18, 0.32, 0.18],
            x: ["-10%", "10%", "-10%"],
          }}
          transition={{
            duration: 14,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute -top-[20%] -left-[10%] w-[60vw] h-[60vw] rounded-full bg-emerald-500/06 blur-[140px]"
        />

        <motion.div
          animate={{
            scale: [1.08, 1, 1.08],
            opacity: [0.12, 0.28, 0.12],
            x: ["10%", "-10%", "10%"],
          }}
          transition={{
            duration: 18,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute top-[10%] -right-[10%] w-[50vw] h-[50vw] rounded-full bg-violet-600/08 blur-[160px]"
        />

        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.08, 0.18, 0.08],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute bottom-[-10%] left-[25%] w-[45vw] h-[45vw] rounded-full bg-cyan-500/05 blur-[150px]"
        />

        {showRadialGradient && (
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#030508_80%)]" />
        )}
      </div>

      <div className="relative z-10 w-full">{children}</div>
    </div>
  );
}
