"use client";

import React, { useState } from "react";
import {
  StudioHeader,
  STUDIO_MODELS,
  StudioModel,
} from "./StudioHeader";
import {
  StudioPromptEditor,
  SAMPLE_PROMPT_SINGLE,
  SAMPLE_PROMPT_CHAT,
  SAMPLE_PROMPT_RAG,
} from "./StudioPromptEditor";
import { StudioVisualization } from "./StudioVisualization";
import { StudioResultsPanel } from "./StudioResultsPanel";
import { Card } from "@/components/design-system";

export function LLMSlimStudio() {
  const [activeMode, setActiveMode] = useState<"prompt" | "chat" | "rag">("prompt");
  const [selectedModel, setSelectedModel] = useState<StudioModel>(STUDIO_MODELS[0]);
  const [targetRatio, setTargetRatio] = useState<number>(0.5);

  const [editorText, setEditorText] = useState<string>(SAMPLE_PROMPT_SINGLE);
  const [activePreset, setActivePreset] = useState<"single" | "chat" | "rag">("single");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Load Preset with active state tracking
  const handleLoadPreset = (presetKey: "single" | "chat" | "rag") => {
    setActivePreset(presetKey);
    if (presetKey === "single") {
      setActiveMode("prompt");
      setEditorText(SAMPLE_PROMPT_SINGLE);
    } else if (presetKey === "chat") {
      setActiveMode("chat");
      setEditorText(SAMPLE_PROMPT_CHAT);
    } else if (presetKey === "rag") {
      setActiveMode("rag");
      setEditorText(SAMPLE_PROMPT_RAG);
    }
  };

  // Simulate compression run animation
  const handleCompress = () => {
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
    }, 600);
  };

  const handleReset = () => {
    handleLoadPreset(activePreset);
  };

  // Simple token estimator
  const tokenCount = Math.max(10, Math.round(editorText.length / 4.2));

  return (
    <Card
      glowColor="emerald"
      className="p-0 overflow-hidden border-emerald-500/30 shadow-[0_0_50px_rgba(0,245,155,0.12)] border-specular-emerald rounded-3xl"
    >
      {/* Studio Header Bar */}
      <StudioHeader
        activeMode={activeMode}
        setActiveMode={(m) => {
          setActiveMode(m);
          handleLoadPreset(m === "chat" ? "chat" : m === "rag" ? "rag" : "single");
        }}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        targetRatio={targetRatio}
        setTargetRatio={setTargetRatio}
        isProcessing={isProcessing}
        onCompress={handleCompress}
        onReset={handleReset}
      />

      {/* True IDE Grid Layout across Viewports */}
      <div className="grid grid-cols-1 md:grid-cols-12 items-stretch min-h-[600px] divide-y md:divide-y-0 md:divide-x divide-white/10">
        {/* Panel 1: Monaco Prompt Editor (Desktop: 5 cols, Tablet: Full 12 cols) */}
        <div className="col-span-12 lg:col-span-5 flex flex-col min-h-[450px] lg:min-h-[600px]">
          <StudioPromptEditor
            value={editorText}
            onChange={setEditorText}
            mode={activeMode}
            onLoadPreset={handleLoadPreset}
            tokenCount={tokenCount}
            activePreset={activePreset}
          />
        </div>

        {/* Panel 2: Compression Visualization Centerpiece (Desktop: 4 cols, Tablet: 6 cols) */}
        <div className="col-span-12 md:col-span-6 lg:col-span-4 flex flex-col min-h-[450px] lg:min-h-[600px]">
          <StudioVisualization
            originalText={editorText}
            targetRatio={targetRatio}
            isProcessing={isProcessing}
          />
        </div>

        {/* Panel 3: Structured Results & ROI Exporter (Desktop: 3 cols, Tablet: 6 cols) */}
        <div className="col-span-12 md:col-span-6 lg:col-span-3 flex flex-col min-h-[450px] lg:min-h-[600px]">
          <StudioResultsPanel
            originalTokens={tokenCount}
            targetRatio={targetRatio}
            selectedModel={selectedModel}
            mode={activeMode}
          />
        </div>
      </div>
    </Card>
  );
}
