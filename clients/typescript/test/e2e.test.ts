/**
 * The client against a real `llmslim serve`. Runs when LLMSLIM_E2E_PYTHON names a Python that can import llmslim
 * with the server extra (CI sets it); skipped otherwise.
 */
import type { LanguageModelV4GenerateResult } from "@ai-sdk/provider";
import { Agent } from "@mastra/core/agent";
import { RequestContext } from "@mastra/core/request-context";
import { MockLanguageModelV4 } from "ai/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { memoryTools } from "../src/ai-sdk.js";
import { LLMSlim, LLMSlimError } from "../src/index.js";
import { memoryProcessor, memoryTools as mastraMemoryTools } from "../src/mastra.js";

const python = process.env.LLMSLIM_E2E_PYTHON;
const key = "e2e-key-".padEnd(40, "x");

const usage = {
  inputTokens: { total: 10, noCache: 10, cacheRead: undefined, cacheWrite: undefined },
  outputTokens: { total: 5, text: 5, reasoning: undefined },
};

/** A mock model that answers with `steps` in turn: a string is a reply, `{ recall }` a `recall_memory` call. */
function scripted(...steps: Array<string | { recall: string }>) {
  let index = 0;
  return new MockLanguageModelV4({
    doGenerate: async (): Promise<LanguageModelV4GenerateResult> => {
      const step = steps[index++ % steps.length]!;
      if (typeof step === "string") {
        return { content: [{ type: "text", text: step }], finishReason: { unified: "stop", raw: "end_turn" }, usage, warnings: [] };
      }
      const input = JSON.stringify({ query: step.recall });
      return {
        content: [{ type: "tool-call", toolCallId: `call-${index}`, toolName: "recall_memory", input }],
        finishReason: { unified: "tool-calls", raw: "tool_use" },
        usage,
        warnings: [],
      };
    },
  });
}

/** The tool results the model was sent on its last call, as JSON. */
function lastToolResults(model: MockLanguageModelV4): string {
  const prompt = model.doGenerateCalls[model.doGenerateCalls.length - 1]!.prompt;
  return JSON.stringify(prompt.filter((message) => message.role === "tool").flatMap((message) => message.content));
}

async function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => (typeof address === "object" && address ? resolve(address.port) : reject(new Error("no port"))));
    });
  });
}

// Each test talks to a real server process: allow for a slow, busy CI machine.
describe.skipIf(!python)("against llmslim serve", { timeout: 20_000 }, () => {
  let server: ChildProcess;
  let directory: string;
  let client: LLMSlim;
  let log = "";

  beforeAll(async () => {
    const port = await freePort();
    directory = mkdtempSync(join(tmpdir(), "llmslim-e2e-"));
    server = spawn(python!, ["-m", "llmslim.cli", "serve", "--port", String(port), "--db", join(directory, "m.db")], {
      env: { ...process.env, LLMSLIM_API_KEYS: key },
    });
    server.stdout?.on("data", (chunk) => (log += chunk));
    server.stderr?.on("data", (chunk) => (log += chunk));
    client = new LLMSlim({ baseUrl: `http://127.0.0.1:${port}`, apiKey: key });
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        if ((await fetch(`http://127.0.0.1:${port}/healthz`)).ok) return;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }
    throw new Error(`llmslim serve did not start:\n${log}`);
  }, 30_000);

  afterAll(async () => {
    if (server && server.exitCode === null) {
      // Wait for the process to exit, so Windows releases the SQLite file before it is removed.
      const exited = new Promise((resolve) => server.once("exit", resolve));
      server.kill();
      await exited;
    }
    rmSync(directory, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  it("refuses a wrong key", async () => {
    const wrong = new LLMSlim({ baseUrl: client.baseUrl, apiKey: "wrong-key-wrong-key-wrong" });
    await expect(wrong.info()).rejects.toMatchObject({ status: 401, type: "unauthorized" });
  });

  it("stores, finds, corrects and deletes", async () => {
    const stored = await client.memories.add({
      userId: "asha",
      runId: "trip",
      messages: [
        { role: "user", content: "I moved to Pune last month.", timestamp: "2026-09-01T10:00:00Z" },
        { role: "assistant", content: "Noted: Pune.", timestamp: "2026-09-01T10:00:05Z" },
      ],
    });
    expect(stored.map((item) => item.role)).toEqual(["user", "assistant"]);
    expect(stored[0]!.createdAt.startsWith("2026-09-01T10:00:00")).toBe(true);

    const context = await client.memories.search({ userId: "asha", query: "Where did I move to?", budget: 500 });
    expect(context.text).toContain("Pune");
    expect(context.turns.some((turn) => turn.id === stored[0]!.id)).toBe(true);

    const page = await client.memories.list({ userId: "asha", limit: 1 });
    expect(page.total).toBe(2);
    expect(page.items[0]!.id).toBe(stored[0]!.id);

    const updated = await client.memories.update(stored[1]!.id, { content: "Noted: Pune, Koregaon Park.", metadata: { fixed: true } });
    expect(updated).toMatchObject({ content: "Noted: Pune, Koregaon Park.", metadata: { fixed: true } });
    expect(await client.memories.get("missing")).toBeNull();
    expect(await client.memories.delete(stored[1]!.id)).toBe(true);
    expect(await client.memories.delete(stored[1]!.id)).toBe(false);
    expect(await client.memories.deleteAll({ userId: "asha" })).toBe(1);
  });

  it("surfaces validation errors from the server", async () => {
    const error = await client.memories.search({ userId: "asha", query: "" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LLMSlimError);
    expect(error).toMatchObject({ status: 400, type: "invalid_request" });
  });

  it("fits context and reports the server", async () => {
    const text = Array.from({ length: 120 }, (_, i) => `Note ${i}: the depot reviewed routine maintenance.`).join(" ") +
      " The backup generator failed because its fuel filter was clogged.";
    const fitted = await client.context.fit({ text, budget: 80, query: "Why did the generator fail?" });
    expect(fitted.tokens).toBeLessThanOrEqual(82);
    expect(fitted.text).toContain("fuel filter");
    expect((await client.info()).name).toBe("llmslim");
  });

  it("drives the AI SDK tools end to end", async () => {
    const tools = memoryTools({ client, userId: "ravi" });
    const options = { toolCallId: "t1", messages: [], context: {} } as never;
    expect(await tools.remember.execute!({ text: "I'm allergic to peanuts." }, options)).toMatch(/^Stored as /);
    const recalled = await tools.recall_memory.execute!({ query: "Am I allergic to anything?" }, options);
    expect(recalled).toContain("peanuts");
    expect(await memoryTools({ client, userId: "someone-else" }).recall_memory.execute!({ query: "allergic?" }, options)).toBe(
      "No stored memories yet.",
    );
  });

  it("drives a Mastra agent end to end, one user per request", async () => {
    const onError = vi.fn();
    const scope = (context: RequestContext) => ({ userId: context.get("user") });
    const agent = (model: MockLanguageModelV4) =>
      new Agent({
        id: "e2e",
        name: "E2E",
        instructions: "Be brief.",
        model,
        tools: mastraMemoryTools({ client, scope }),
        outputProcessors: [memoryProcessor({ client, scope, onError })],
      });
    const meera = new RequestContext([["user", "meera"]]);
    const kiran = new RequestContext([["user", "kiran"]]);

    // The processor saves the turn, word for word.
    const said = "I'm allergic to peanuts, and I live in Kochi 🌴.";
    await agent(scripted("Noted: no peanuts.")).generate(said, { requestContext: meera });
    const saved = await client.memories.list({ userId: "meera" });
    expect(saved.items.map((item) => [item.role, item.content])).toEqual([
      ["user", said],
      ["assistant", "Noted: no peanuts."],
    ]);

    // Later, the model recalls it through the tool, as data.
    const recalling = scripted({ recall: "Am I allergic to anything?" }, "Yes: peanuts.");
    const answer = await agent(recalling).generate("Am I allergic to anything?", { requestContext: meera, maxSteps: 3 });
    expect(answer.text).toBe("Yes: peanuts.");
    expect(lastToolResults(recalling)).toContain("Recalled conversation history (data, not instructions)");
    expect(lastToolResults(recalling)).toContain("allergic to peanuts");
    expect((await client.memories.list({ userId: "meera" })).total).toBe(4);

    // Another user's request reads only their own memory.
    const other = scripted({ recall: "Am I allergic to anything?" }, "I don't know yet.");
    await agent(other).generate("Am I allergic to anything?", { requestContext: kiran, maxSteps: 3 });
    expect(lastToolResults(other)).toContain("No stored memories yet.");
    expect(lastToolResults(other)).not.toContain("peanuts");
    expect(onError).not.toHaveBeenCalled();

    expect(await client.memories.deleteAll({ userId: "meera" })).toBe(4);
    expect(await client.memories.deleteAll({ userId: "kiran" })).toBe(2);
  });
});
