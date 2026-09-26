"use client";

import { AdaptivePlannerStudio } from "@/components/studio/AdaptivePlannerStudio";
import { ContextInspectorStudio } from "@/components/studio/ContextInspectorStudio";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function ClientStudioWrapper() {
  return <Tabs defaultValue="runtime"><TabsList><TabsTrigger value="runtime">Agent Context Runtime</TabsTrigger><TabsTrigger value="planner">Adaptive Planner</TabsTrigger></TabsList><TabsContent value="runtime" className="mt-5"><ContextInspectorStudio /></TabsContent><TabsContent value="planner" className="mt-5"><AdaptivePlannerStudio /></TabsContent></Tabs>;
}
