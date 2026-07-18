"use client";

import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface CardProps {
  children?: React.ReactNode;
  className?: string;
  glowColor?: "emerald" | "cyan" | "violet";
  spotlight?: boolean;
}

export function Card({
  children,
  className,
  glowColor = "emerald",
  spotlight = true,
}: CardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current || !spotlight) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const glowColorMap = {
    emerald: "rgba(0, 245, 155, 0.09)",
    cyan: "rgba(0, 229, 255, 0.09)",
    violet: "rgba(168, 85, 247, 0.09)",
  };

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 350, damping: 25 }}
      className={cn(
        "relative rounded-2xl bg-[#0D121C]/80 border border-white/[0.06] backdrop-blur-xl p-6 overflow-hidden shadow-2xl",
        "before:absolute before:inset-x-0 before:top-0 before:h-[1px] before:bg-gradient-to-r before:from-transparent before:via-white/15 before:to-transparent",
        className
      )}
    >
      {spotlight && isHovered && (
        <div
          className="pointer-events-none absolute -inset-px opacity-100 transition-opacity duration-300"
          style={{
            background: `radial-gradient(350px circle at ${mousePosition.x}px ${mousePosition.y}px, ${glowColorMap[glowColor]}, transparent 70%)`,
          }}
        />
      )}

      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

export interface BentoCardProps extends CardProps {
  title?: string;
  subtitle?: string;
  badge?: string;
  icon?: React.ReactNode;
  spanCol?: string;
}

export function BentoCard({
  title,
  subtitle,
  badge,
  icon,
  children,
  className,
  spanCol = "col-span-1",
  ...props
}: BentoCardProps) {
  return (
    <Card className={cn(spanCol, "flex flex-col justify-between group", className)} {...props}>
      <div>
        <div className="flex items-center justify-between gap-3 mb-4">
          {icon && (
            <div className="p-2.5 rounded-xl bg-white/[0.05] border border-white/10 text-emerald-400 group-hover:scale-105 group-hover:border-emerald-500/30 transition-all duration-300">
              {icon}
            </div>
          )}
          {badge && (
            <span className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-widest rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {badge}
            </span>
          )}
        </div>

        {title && <h3 className="text-xl font-bold tracking-tight text-white mb-2">{title}</h3>}
        {subtitle && <p className="text-sm text-slate-400 leading-relaxed mb-4">{subtitle}</p>}
      </div>

      {children && <div className="mt-4">{children}</div>}
    </Card>
  );
}
