import { describe, expect, it } from "vitest";
import { LLMSlim, LLMSlimError } from "../src/index.js";

type Call = { url: URL; init: RequestInit };

function fakeFetch(responses: Array<{ status?: number; body?: unknown; raw?: string }>) {
  const calls: Call[] = [];
  const fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: new URL(String(input)), init: init ?? {} });
    const next = responses.shift() ?? { status: 200, body: {} };
    const text = next.raw ?? JSON.stringify(next.body ?? {});
    return new Response(text, { status: next.status ?? 200, headers: { "content-type": "application/json" } });
  }) as typeof globalThis.fetch;
  return { fetch, calls };
}

const item = {
  id: "abc",
  role: "user",
  content: "I moved to Pune.",
  created_at: "2026-10-01T09:00:00+00:00",
  updated_at: null,
  user_id: "asha",
  agent_id: null,
  run_id: null,
  metadata: {},
};

describe("LLMSlim client", () => {
  it("stores messages with snake_case scope, the key and JSON", async () => {
    const { fetch, calls } = fakeFetch([{ status: 201, body: { items: [item] } }]);
    const client = new LLMSlim({ baseUrl: "http://memory:8080/", apiKey: "k".repeat(32), fetch });
    const items = await client.memories.add({ userId: "asha", messages: "I moved to Pune." });
    expect(items).toEqual([
      {
        id: "abc",
        role: "user",
        content: "I moved to Pune.",
        createdAt: "2026-10-01T09:00:00+00:00",
        updatedAt: null,
        userId: "asha",
        agentId: null,
        runId: null,
        metadata: {},
      },
    ]);
    const [call] = calls;
    expect(call!.url.toString()).toBe("http://memory:8080/v1/memories");
    expect(call!.init.method).toBe("POST");
    const headers = call!.init.headers as Record<string, string>;
    expect(headers.authorization).toBe(`Bearer ${"k".repeat(32)}`);
    expect(headers["content-type"]).toBe("application/json");
    expect(JSON.parse(call!.init.body as string)).toEqual({ messages: "I moved to Pune.", user_id: "asha" });
  });

  it("searches and maps the context to camelCase", async () => {
    const { fetch, calls } = fakeFetch([
      {
        body: {
          query: "Where did I move to?",
          text: "[2026-10-01 (Thu) 09:00] user: I moved to Pune.",
          tokens: 14,
          budget: 1500,
          history_tokens: 14,
          sessions_total: 1,
          sessions_kept: 1,
          elapsed_ms: 1.5,
          turns: [{ ...item, score: 0.5, partial: false }],
        },
      },
    ]);
    const context = await new LLMSlim({ fetch }).memories.search({
      userId: "asha",
      query: "Where did I move to?",
      budget: 1500,
    });
    expect(context.historyTokens).toBe(14);
    expect(context.sessionsKept).toBe(1);
    expect(context.turns[0]).toMatchObject({ id: "abc", userId: "asha", score: 0.5, partial: false });
    expect(context).not.toHaveProperty("explanation");
    expect(JSON.parse(calls[0]!.init.body as string)).toEqual({
      query: "Where did I move to?",
      budget: 1500,
      user_id: "asha",
    });
  });

  it("maps the sections shown above the turns as it maps the turns", async () => {
    const request = { ...item, id: "req", content: "From now on, answer in British English.", metadata: { source: "chat" } };
    const preference = { ...item, id: "pref", content: "I prefer aisle seats on long flights." };
    const { fetch } = fakeFetch([
      {
        body: {
          query: "What seat should I book?",
          text: "Preferences the user stated earlier:\n- [2026-10-03 (Sat) 09:00] I prefer aisle seats on long flights.",
          tokens: 30,
          budget: 120,
          history_tokens: 323,
          sessions_total: 6,
          sessions_kept: 1,
          elapsed_ms: 1.0,
          turns: [],
          requests: [{ ...request, score: 0.0, partial: false }],
          preferences: [{ ...preference, score: 0.25, partial: true }],
          conflicts: [],
        },
      },
      // A body without the sections (the server always sends them): each reads as empty, not undefined.
      { body: { query: "q", text: "", tokens: 0, budget: 10, history_tokens: 0, sessions_total: 0, sessions_kept: 0, elapsed_ms: 0, turns: [] } },
    ]);
    const client = new LLMSlim({ fetch });
    const context = await client.memories.search({ userId: "asha", query: "What seat should I book?", budget: 120 });
    expect(context.requests).toEqual([
      {
        id: "req",
        role: "user",
        content: "From now on, answer in British English.",
        createdAt: "2026-10-01T09:00:00+00:00",
        updatedAt: null,
        userId: "asha",
        agentId: null,
        runId: null,
        metadata: { source: "chat" },
        score: 0.0,
        partial: false,
      },
    ]);
    expect(context.preferences).toEqual([
      { ...context.requests[0], id: "pref", content: preference.content, metadata: {}, score: 0.25, partial: true },
    ]);
    expect(context.conflicts).toEqual([]);
    const bare = await client.memories.search({ userId: "asha", query: "q", budget: 10 });
    expect([bare.requests, bare.preferences, bare.conflicts]).toEqual([[], [], []]);
  });

  it("asks for an explanation and maps every field of it to camelCase", async () => {
    const kept = { turn_id: "abc", pool: "user", kind: "turn", part: 0, rank: 1, score: 0.42, tokens: 9, status: "kept", reason: null, side: null };
    const weighed = { ...kept, pool: "conflicts", kind: "statement", rank: null, score: null, status: "dropped", reason: "no_disagreement", side: "denies" };
    const turn = { id: "abc", role: "user", created_at: "2026-10-20T09:00:00+00:00", session: 0, pool: "user", status: "kept", reason: null, tokens: 30, share: 0.5 };
    const outside = { ...turn, id: "old", created_at: "2026-10-01T09:00:00+00:00", session: null, pool: null, status: "dropped", reason: "outside_window", tokens: 0, share: 0.0 };
    const { fetch, calls } = fakeFetch([
      {
        body: {
          query: "Where did I move to?",
          text: "[2026-10-20 (Tue) 09:00] user: I moved to Pune.",
          tokens: 47,
          budget: 60,
          history_tokens: 88,
          sessions_total: 1,
          sessions_kept: 1,
          elapsed_ms: 2.5,
          turns: [{ ...item, score: 0.5, partial: false }],
          requests: [],
          preferences: [],
          conflicts: [],
          explanation: {
            mode: "turns",
            route: "lookup",
            budget: 60,
            tokens: 47,
            history_tokens: 88,
            room: 60,
            user_room: 33,
            user_turn_cap: 30,
            clipped: false,
            unattributed_tokens: 0,
            turns: [
              { ...outside, candidates: [] },
              { ...turn, candidates: [kept] },
            ],
            sections: [
              { name: "requests", shown: false, reason: "route", cap: 0, tokens: 0, share: 0.0, candidates: [] },
              { name: "conflicts", shown: false, reason: "no_disagreement", cap: 12, tokens: 0, share: 0.0, candidates: [weighed] },
            ],
          },
        },
      },
    ]);
    const context = await new LLMSlim({ fetch }).memories.search({
      userId: "asha",
      query: "Where did I move to?",
      budget: 60,
      since: "2026-10-10",
      explain: true,
    });
    expect(JSON.parse(calls[0]!.init.body as string)).toEqual({
      query: "Where did I move to?",
      budget: 60,
      since: "2026-10-10",
      explain: true,
      user_id: "asha",
    });
    const keptCandidate = { turnId: "abc", pool: "user", kind: "turn", part: 0, rank: 1, score: 0.42, tokens: 9, status: "kept", reason: null, side: null };
    const keptTurn = { id: "abc", role: "user", createdAt: "2026-10-20T09:00:00+00:00", session: 0, pool: "user", status: "kept", reason: null, tokens: 30, share: 0.5 };
    expect(context.explanation).toEqual({
      mode: "turns",
      route: "lookup",
      budget: 60,
      tokens: 47,
      historyTokens: 88,
      room: 60,
      userRoom: 33,
      userTurnCap: 30,
      clipped: false,
      unattributedTokens: 0,
      turns: [
        { ...keptTurn, id: "old", createdAt: "2026-10-01T09:00:00+00:00", session: null, pool: null, status: "dropped", reason: "outside_window", tokens: 0, share: 0, candidates: [] },
        { ...keptTurn, candidates: [keptCandidate] },
      ],
      sections: [
        { name: "requests", shown: false, reason: "route", cap: 0, tokens: 0, share: 0, candidates: [] },
        {
          name: "conflicts",
          shown: false,
          reason: "no_disagreement",
          cap: 12,
          tokens: 0,
          share: 0,
          candidates: [{ ...keptCandidate, pool: "conflicts", kind: "statement", rank: null, score: null, status: "dropped", reason: "no_disagreement", side: "denies" }],
        },
      ],
    });
  });

  it("lists with query parameters and pages", async () => {
    const { fetch, calls } = fakeFetch([{ body: { items: [item], total: 3, offset: 2, limit: 1 } }]);
    const page = await new LLMSlim({ fetch }).memories.list({ userId: "asha", limit: 1, offset: 2 });
    expect(page.total).toBe(3);
    expect(calls[0]!.url.search).toBe("?user_id=asha&limit=1&offset=2");
  });

  it("returns null or false for a missing id, and throws other errors", async () => {
    const missing = { status: 404, body: { error: { type: "not_found", message: "no stored message has that id" } } };
    const { fetch } = fakeFetch([missing, missing, missing, { status: 500, raw: "{}" }]);
    const client = new LLMSlim({ fetch });
    expect(await client.memories.get("x")).toBeNull();
    expect(await client.memories.update("x", { content: "y" })).toBeNull();
    expect(await client.memories.delete("x")).toBe(false);
    await expect(client.memories.get("x")).rejects.toMatchObject({ status: 500, type: "http_error" });
  });

  it("turns server errors into LLMSlimError with the server's type and message", async () => {
    const { fetch } = fakeFetch([{ status: 401, body: { error: { type: "unauthorized", message: "missing or invalid API key" } } }]);
    const error = await new LLMSlim({ fetch }).info().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LLMSlimError);
    expect(error).toMatchObject({ status: 401, type: "unauthorized", message: "missing or invalid API key" });
  });

  it("reports an unreachable server and a non-JSON answer clearly", async () => {
    const down = (async () => {
      throw new TypeError("fetch failed");
    }) as typeof globalThis.fetch;
    await expect(new LLMSlim({ fetch: down, baseUrl: "http://nowhere:1" }).info()).rejects.toMatchObject({
      status: 0,
      type: "unreachable",
    });
    const { fetch } = fakeFetch([{ status: 502, raw: "<html>Bad gateway</html>" }]);
    await expect(new LLMSlim({ fetch }).info()).rejects.toMatchObject({ status: 502, type: "invalid_response" });
  });

  it("refuses to delete everything by accident", async () => {
    const { fetch, calls } = fakeFetch([{ body: { deleted: 2 } }]);
    const client = new LLMSlim({ fetch });
    await expect(client.memories.deleteAll({})).rejects.toMatchObject({ status: 400 });
    expect(calls).toHaveLength(0);
    expect(await client.memories.deleteAll({ userId: "asha" })).toBe(2);
    expect(calls[0]!.url.search).toBe("?user_id=asha");
  });

  it("fits context and reads server info", async () => {
    const { fetch } = fakeFetch([
      { body: { text: "short", tokens: 1, original_tokens: 900 } },
      { body: { name: "llmslim", version: "0.9.0", budget: 2000, max_budget: 100000 } },
    ]);
    const client = new LLMSlim({ fetch });
    expect(await client.context.fit({ text: "long", budget: 100 })).toEqual({ text: "short", tokens: 1, originalTokens: 900 });
    expect(await client.info()).toEqual({ name: "llmslim", version: "0.9.0", budget: 2000, maxBudget: 100000 });
  });

  it("reads its defaults from the environment and escapes ids", async () => {
    process.env.LLMSLIM_BASE_URL = "http://from-env:9000";
    process.env.LLMSLIM_API_KEY = "e".repeat(20);
    try {
      const { fetch, calls } = fakeFetch([{ body: item }]);
      await new LLMSlim({ fetch }).memories.get("a/b");
      expect(calls[0]!.url.toString()).toBe("http://from-env:9000/v1/memories/a%2Fb");
      expect((calls[0]!.init.headers as Record<string, string>).authorization).toBe(`Bearer ${"e".repeat(20)}`);
    } finally {
      delete process.env.LLMSLIM_BASE_URL;
      delete process.env.LLMSLIM_API_KEY;
    }
  });
});
