import React from "react";
import { Info, AlertTriangle, Lightbulb, ShieldAlert } from "lucide-react";
import { DocCallout as DocCalloutType } from "@/data/docs";
import { cn } from "@/lib/utils";

export function DocCallout({ callout }: { callout: DocCalloutType }) {
  const configs = {
    note: {
      icon: Info,
      border: "border-cyan-500/30",
      bg: "bg-cyan-500/10",
      text: "text-cyan-300",
      titleColor: "text-cyan-400",
      defaultTitle: "Note",
    },
    tip: {
      icon: Lightbulb,
      border: "border-emerald-500/30",
      bg: "bg-emerald-500/10",
      text: "text-emerald-300",
      titleColor: "text-emerald-400",
      defaultTitle: "Pro Tip",
    },
    warning: {
      icon: AlertTriangle,
      border: "border-amber-500/30",
      bg: "bg-amber-500/10",
      text: "text-amber-300",
      titleColor: "text-amber-400",
      defaultTitle: "Warning",
    },
    important: {
      icon: ShieldAlert,
      border: "border-violet-500/30",
      bg: "bg-violet-500/10",
      text: "text-violet-300",
      titleColor: "text-violet-400",
      defaultTitle: "Important Requirement",
    },
  };

  const cfg = configs[callout.type] || configs.note;
  const Icon = cfg.icon;

  return (
    <div className={cn("my-6 p-4.5 rounded-2xl border backdrop-blur-xl font-sans text-sm leading-relaxed space-y-2", cfg.bg, cfg.border)}>
      <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider">
        <Icon className={cn("w-4 h-4 shrink-0", cfg.titleColor)} />
        <span className={cfg.titleColor}>{callout.title || cfg.defaultTitle}</span>
      </div>
      <p className={cn("pl-6 font-normal", cfg.text)}>{callout.content}</p>
    </div>
  );
}
