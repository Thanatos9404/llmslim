"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedGradientMeshProps {
  className?: string;
}

export function AnimatedGradientMesh({ className }: AnimatedGradientMeshProps) {
  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none opacity-40", className)}>
      <motion.div
        animate={{
          rotate: [0, 360],
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "linear",
        }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full bg-gradient-to-tr from-emerald-500/20 via-cyan-500/15 to-violet-600/20 blur-[130px]"
      />
    </div>
  );
}
