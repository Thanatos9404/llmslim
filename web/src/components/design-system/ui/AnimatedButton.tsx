"use client";

import React from "react";
import { motion, HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

export interface AnimatedButtonProps extends HTMLMotionProps<"button"> {
  variant?: "quantum" | "glass" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: React.ReactNode;
  iconPosition?: "left" | "right";
  children: React.ReactNode;
}

export function AnimatedButton({
  variant = "quantum",
  size = "md",
  icon,
  iconPosition = "left",
  children,
  className,
  ...props
}: AnimatedButtonProps) {
  const sizeStyles = {
    sm: "px-3.5 py-1.5 text-xs rounded-lg gap-1.5 font-mono tracking-wide",
    md: "px-5 py-2.5 text-sm rounded-xl gap-2 font-medium",
    lg: "px-7 py-3.5 text-base rounded-2xl gap-2.5 font-semibold",
  };

  const variantStyles = {
    quantum:
      "relative overflow-hidden bg-gradient-to-r from-[#00F59B] via-[#00E5FF] to-[#00F59B] bg-[length:200%_100%] text-[#030508] font-bold shadow-[0_0_25px_rgba(0,245,155,0.35)] hover:shadow-[0_0_35px_rgba(0,245,155,0.5)] transition-all duration-300",
    glass:
      "bg-white/[0.06] hover:bg-white/[0.12] text-slate-100 border border-white/10 hover:border-white/25 backdrop-blur-md shadow-lg",
    outline:
      "bg-transparent hover:bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:border-emerald-400 shadow-[0_0_15px_rgba(0,245,155,0.15)]",
    ghost:
      "bg-transparent hover:bg-white/5 text-slate-300 hover:text-white border border-transparent",
  };

  return (
    <motion.button
      whileHover={{ scale: 1.025 }}
      whileTap={{ scale: 0.975 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "inline-flex items-center justify-center transition-colors cursor-pointer select-none",
        sizeStyles[size],
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {/* Beam Shimmer Overlay for Quantum Variant */}
      {variant === "quantum" && (
        <motion.span
          animate={{ x: ["-100%", "200%"] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-white/40 to-transparent skew-x-12 pointer-events-none"
        />
      )}

      {icon && iconPosition === "left" && <span className="shrink-0">{icon}</span>}
      <span className="relative z-10">{children}</span>
      {icon && iconPosition === "right" && <span className="shrink-0">{icon}</span>}
    </motion.button>
  );
}
