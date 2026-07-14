"use client";

import React from "react";
import { BentoCard, BentoCardProps } from "./Card";
import { Sparkles } from "lucide-react";

export interface FeatureCardProps extends BentoCardProps {
  description?: string;
}

export function FeatureCard({
  title,
  subtitle,
  badge,
  icon = <Sparkles className="w-5 h-5 text-emerald-400" />,
  children,
  className,
  ...props
}: FeatureCardProps) {
  return (
    <BentoCard
      title={title}
      subtitle={subtitle}
      badge={badge}
      icon={icon}
      className={className}
      {...props}
    >
      {children}
    </BentoCard>
  );
}
