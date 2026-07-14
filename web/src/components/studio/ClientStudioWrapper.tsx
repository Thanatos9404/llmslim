"use client";

import React from "react";
import dynamic from "next/dynamic";
import { StudioSkeleton } from "@/components/studio/StudioSkeleton";

const DynamicLLMSlimStudio = dynamic(
  () => import("@/components/studio/LLMSlimStudio").then((mod) => mod.LLMSlimStudio),
  {
    ssr: false,
    loading: () => <StudioSkeleton />,
  }
);

export function ClientStudioWrapper() {
  return <DynamicLLMSlimStudio />;
}
