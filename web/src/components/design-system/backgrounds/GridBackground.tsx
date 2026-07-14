"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface GridBackgroundProps {
  children?: React.ReactNode;
  className?: string;
  gridSize?: number;
  maskGradient?: boolean;
}

export function GridBackground({
  children,
  className,
  gridSize = 40,
  maskGradient = true,
}: GridBackgroundProps) {
  return (
    <div className={cn("relative w-full overflow-hidden bg-[#030508]", className)}>
      <div
        className="absolute inset-0 pointer-events-none opacity-25"
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.08) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.08) 1px, transparent 1px)
          `,
          backgroundSize: `${gridSize}px ${gridSize}px`,
        }}
      />

      {maskGradient && (
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,transparent_20%,#030508_85%)]" />
      )}

      <div className="relative z-10">{children}</div>
    </div>
  );
}
