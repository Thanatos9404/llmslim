"use client";

import React from "react";
import Link from "next/link";
import { AuroraBackground, NoiseOverlay, AnimatedButton, Card } from "@/components/design-system";
import { Home, Compass, Terminal, ShieldAlert } from "lucide-react";

export default function NotFound() {
  return (
    <AuroraBackground className="min-h-screen flex items-center justify-center p-4">
      <NoiseOverlay opacity={0.03} />

      <Card glowColor="violet" className="max-w-md w-full p-8 text-center space-y-6 relative z-10 border-violet-500/30">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/30 flex items-center justify-center text-violet-400">
          <ShieldAlert className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-mono uppercase tracking-widest text-violet-400">
            Error 404 // Signal Lost
          </span>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Context Chunk Not Found
          </h1>
          <p className="text-sm text-slate-400 leading-relaxed font-sans">
            The page or API endpoint you requested does not exist or has been pruned by the context engine.
          </p>
        </div>

        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/" className="w-full sm:w-auto">
            <AnimatedButton variant="quantum" size="md" icon={<Home className="w-4 h-4" />}>
              Return to LLMSlim Hub
            </AnimatedButton>
          </Link>
        </div>
      </Card>
    </AuroraBackground>
  );
}
