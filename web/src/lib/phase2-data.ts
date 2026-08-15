import { readFileSync } from "node:fs";
import { join } from "node:path";

export type SchemaComplexity = "SIMPLE" | "MEDIUM" | "COMPLEX";

export interface SchemaTaxCatalog {
  classification: "MEASURED";
  complexity: SchemaComplexity;
  tool_count: number;
  total_schema_tokens: number;
  mean_tokens_per_tool: number;
  token_counter_used: string;
  cumulative_schema_tokens: Record<string, { classification: "DERIVED"; tokens: number; assumption: string }>;
}

interface Phase2Results {
  dataset: {
    sample_count: number;
    categories: Record<string, number>;
    languages: Record<string, number>;
  };
  schema_tax: { catalog_count: number; tool_schema_count: number };
  security: "PASS";
  summary: {
    determinism_rate: number;
    failure_rate: number;
    structural_integrity: { applicable_count: number; valid_count: number; unavailable_count: number };
    micro: {
      instruction_retention: { mean: number; count: number };
      entity_retention: { mean: number; count: number };
      semantic_similarity: { mean: number; count: number };
      latency_ms: { median: number; p95: number };
    };
  };
  schema_tax_details: { catalogs: SchemaTaxCatalog[] };
}

let cachedTruth: Phase2Results | undefined;

export function getPhase2Truth(): Phase2Results {
  if (cachedTruth) return cachedTruth;
  const repositoryRoot = join(process.cwd(), "..");
  const summary = JSON.parse(readFileSync(join(repositoryRoot, "benchmarks", "results", "summary.json"), "utf8"));
  const latest = JSON.parse(readFileSync(join(repositoryRoot, "benchmarks", "results", "latest.json"), "utf8"));

  cachedTruth = {
    ...summary,
    schema_tax_details: { catalogs: latest.schema_tax.catalogs },
  } as Phase2Results;

  return cachedTruth;
}

export const phase2ReleaseGate = {
  testsPassed: 442,
  testsFailed: 0,
  branchCoverage: 92.94,
  coverageGate: 90,
  classifications: ["MEASURED", "DERIVED", "NOT_APPLICABLE"] as const,
};
