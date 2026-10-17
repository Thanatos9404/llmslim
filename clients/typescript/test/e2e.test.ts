/**
 * The client against a real `llmslim serve`. Runs when LLMSLIM_E2E_PYTHON names a Python that can import llmslim
 * with the server extra (CI sets it); skipped otherwise.
 */
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { memoryTools } from "../src/ai-sdk.js";
import { LLMSlim, LLMSlimError } from "../src/index.js";

const python = process.env.LLMSLIM_E2E_PYTHON;
const key = "e2e-key-".padEnd(40, "x");

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
});
