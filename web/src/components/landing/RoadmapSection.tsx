"use client";

import React from "react";
import { Timeline } from "@/components/design-system";

export function RoadmapSection() {
  return (
    <section className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-violet-400">
          Future Architecture Pipeline
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Product Engineering <span className="text-gradient-violet">Roadmap</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          From current production governance engines to native ONNX acceleration and browser-edge Web Assembly releases.
        </p>
      </div>

      <Timeline />
    </section>
  );
}
