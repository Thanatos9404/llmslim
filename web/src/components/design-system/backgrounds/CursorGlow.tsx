"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface CursorGlowProps {
  className?: string;
  size?: number;
  color?: "emerald" | "cyan" | "violet";
}

export function CursorGlow({ className, size = 350, color = "emerald" }: CursorGlowProps) {
  const [mousePosition, setMousePosition] = useState({ x: -500, y: -500 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const colorMap = {
    emerald: "rgba(0, 245, 155, 0.12)",
    cyan: "rgba(0, 229, 255, 0.12)",
    violet: "rgba(168, 85, 247, 0.12)",
  };

  return (
    <motion.div
      className={cn("pointer-events-none fixed inset-0 z-30 transition-opacity duration-300", className)}
      animate={{
        x: mousePosition.x - size / 2,
        y: mousePosition.y - size / 2,
      }}
      transition={{ type: "spring", damping: 30, stiffness: 200, mass: 0.5 }}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${colorMap[color]} 0%, transparent 70%)`,
        filter: "blur(20px)",
      }}
    />
  );
}
