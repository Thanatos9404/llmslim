/**
 * LLMSlim client for TypeScript and JavaScript: long-term memory and context fitting for agents, from an
 * `llmslim serve` server. No model calls: messages are stored word for word and selected at read time.
 *
 * Works anywhere `fetch` does: Node 18+, Bun, Deno, edge runtimes. Call it from your backend; the API key gives
 * access to every user's memory.
 */

export type Role = "user" | "assistant" | "system" | "tool";

/** A message to store: a string is one user message. */
export type MessageInput =
  | string
  | {
      role: Role | "human" | "ai" | "model" | "developer" | "function";
      content: string | Array<{ type: string; text?: string }>;
      /** When it was said: an ISO 8601 time or epoch seconds. Defaults to the request's `timestamp`, then now. */
      timestamp?: string | number;
    };

/** Whose memory a call reads or writes. A missing id means "any" on reads. */
export interface Scope {
  userId?: string;
  agentId?: string;
  /** One session. Messages without one are grouped by calendar day. */
  runId?: string;
}

export interface MemoryItem {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
  updatedAt: string | null;
  userId: string | null;
  agentId: string | null;
  runId: string | null;
  metadata: Record<string, unknown>;
}

export interface RecalledTurn extends MemoryItem {
  /** Lexical overlap with the query, 0 to 1, for display and ordering. */
  score: number;
  /** True when only the turn's most relevant sentences were kept. */
  partial: boolean;
}

export interface MemoryContext {
  query: string;
  /** The selected turns under their session dates. Put it in your prompt as data, not instructions. */
  text: string;
  tokens: number;
  budget: number;
  historyTokens: number;
  sessionsTotal: number;
  sessionsKept: number;
  elapsedMs: number;
  turns: RecalledTurn[];
}

export interface MemoryPage {
  items: MemoryItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface FitResult {
  text: string;
  tokens: number;
  originalTokens: number;
}

export interface ServerInfo {
  name: string;
  version: string;
  budget: number;
  maxBudget: number;
}

export interface LLMSlimOptions {
  /** The server's URL. Defaults to `LLMSLIM_BASE_URL`, then `http://127.0.0.1:8080`. */
  baseUrl?: string;
  /** Sent as `Authorization: Bearer <key>`. Defaults to `LLMSLIM_API_KEY`. */
  apiKey?: string;
  /** Per-request timeout. Defaults to 30 seconds. */
  timeoutMs?: number;
  /** A `fetch` implementation, for tests or custom agents. Defaults to the global one. */
  fetch?: typeof fetch;
  /** Extra headers on every request. */
  headers?: Record<string, string>;
}

/** An error response from the server, or a failure to reach it (`status` 0). */
export class LLMSlimError extends Error {
  readonly status: number;
  readonly type: string;

  constructor(status: number, type: string, message: string) {
    super(message);
    this.name = "LLMSlimError";
    this.status = status;
    this.type = type;
  }
}

type Query = Record<string, string | number | undefined>;
type Wire = Record<string, unknown>;

function env(name: string): string | undefined {
  const value = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[name];
  return value || undefined;
}

function scopeToWire(scope: Scope): Record<string, string | undefined> {
  return { user_id: scope.userId, agent_id: scope.agentId, run_id: scope.runId };
}

function itemFromWire(item: Wire): MemoryItem {
  return {
    id: item.id as string,
    role: item.role as Role,
    content: item.content as string,
    createdAt: item.created_at as string,
    updatedAt: (item.updated_at as string | null) ?? null,
    userId: (item.user_id as string | null) ?? null,
    agentId: (item.agent_id as string | null) ?? null,
    runId: (item.run_id as string | null) ?? null,
    metadata: (item.metadata as Record<string, unknown>) ?? {},
  };
}

export class LLMSlim {
  readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly headers: Record<string, string>;

  constructor(options: LLMSlimOptions = {}) {
    let baseUrl = options.baseUrl ?? env("LLMSLIM_BASE_URL") ?? "http://127.0.0.1:8080";
    while (baseUrl.endsWith("/")) baseUrl = baseUrl.slice(0, -1);
    this.baseUrl = baseUrl;
    this.apiKey = options.apiKey ?? env("LLMSLIM_API_KEY");
    this.timeoutMs = options.timeoutMs ?? 30_000;
    const fetchImpl = options.fetch ?? globalThis.fetch;
    if (typeof fetchImpl !== "function") {
      throw new Error("LLMSlim needs fetch: use Node 18 or newer, or pass options.fetch");
    }
    this.fetchImpl = fetchImpl;
    this.headers = options.headers ?? {};
  }

  /** Store, list, read, correct, delete and search messages. */
  readonly memories = {
    /** Store messages word for word. Needs at least one scope id. */
    add: async (
      request: Scope & {
        messages: MessageInput | MessageInput[];
        timestamp?: string | number;
        metadata?: Record<string, unknown>;
      },
    ): Promise<MemoryItem[]> => {
      const body = await this.request("POST", "/v1/memories", {
        body: {
          messages: request.messages,
          timestamp: request.timestamp,
          metadata: request.metadata,
          ...scopeToWire(request),
        },
      });
      return (body.items as Wire[]).map(itemFromWire);
    },

    /** A scope's messages, oldest first, a page at a time. */
    list: async (
      request: Scope & { since?: string; until?: string; limit?: number; offset?: number },
    ): Promise<MemoryPage> => {
      const body = await this.request("GET", "/v1/memories", {
        query: {
          ...scopeToWire(request),
          since: request.since,
          until: request.until,
          limit: request.limit,
          offset: request.offset,
        },
      });
      return {
        items: (body.items as Wire[]).map(itemFromWire),
        total: body.total as number,
        offset: body.offset as number,
        limit: body.limit as number,
      };
    },

    /** One message, or `null` when no message has that id. */
    get: async (id: string): Promise<MemoryItem | null> => {
      try {
        return itemFromWire(await this.request("GET", `/v1/memories/${encodeURIComponent(id)}`));
      } catch (error) {
        if (error instanceof LLMSlimError && error.status === 404) return null;
        throw error;
      }
    },

    /** Correct a message's content or metadata. Returns `null` when no message has that id. */
    update: async (
      id: string,
      changes: { content?: string; metadata?: Record<string, unknown> },
    ): Promise<MemoryItem | null> => {
      try {
        return itemFromWire(
          await this.request("PATCH", `/v1/memories/${encodeURIComponent(id)}`, { body: changes }),
        );
      } catch (error) {
        if (error instanceof LLMSlimError && error.status === 404) return null;
        throw error;
      }
    },

    /** Delete one message. Returns whether it existed. */
    delete: async (id: string): Promise<boolean> => {
      try {
        await this.request("DELETE", `/v1/memories/${encodeURIComponent(id)}`);
        return true;
      } catch (error) {
        if (error instanceof LLMSlimError && error.status === 404) return false;
        throw error;
      }
    },

    /** Delete every message in a scope. Needs at least one scope id. Returns how many were deleted. */
    deleteAll: async (scope: Scope): Promise<number> => {
      if (!scope.userId && !scope.agentId && !scope.runId) {
        throw new LLMSlimError(400, "invalid_request", "name the scope to delete: userId, agentId or runId");
      }
      const body = await this.request("DELETE", "/v1/memories", { query: scopeToWire(scope) });
      return body.deleted as number;
    },

    /** The stored turns that answer `query`, whole and under their dates, within `budget` tokens. */
    search: async (
      request: Scope & {
        query: string;
        budget?: number;
        relevance?: "lexical" | "semantic";
        since?: string;
        until?: string;
      },
    ): Promise<MemoryContext> => {
      const body = await this.request("POST", "/v1/memories/search", {
        body: {
          query: request.query,
          budget: request.budget,
          relevance: request.relevance,
          since: request.since,
          until: request.until,
          ...scopeToWire(request),
        },
      });
      return {
        query: body.query as string,
        text: body.text as string,
        tokens: body.tokens as number,
        budget: body.budget as number,
        historyTokens: body.history_tokens as number,
        sessionsTotal: body.sessions_total as number,
        sessionsKept: body.sessions_kept as number,
        elapsedMs: body.elapsed_ms as number,
        turns: (body.turns as Wire[]).map((turn) => ({
          ...itemFromWire(turn),
          score: turn.score as number,
          partial: turn.partial as boolean,
        })),
      };
    },
  };

  /** Fit long text to a token budget. */
  readonly context = {
    /** Shrink `text` to about `budget` tokens (within 2%), keeping what answers `query`, in order. */
    fit: async (request: { text: string; budget?: number; query?: string }): Promise<FitResult> => {
      const body = await this.request("POST", "/v1/context/fit", { body: request });
      return {
        text: body.text as string,
        tokens: body.tokens as number,
        originalTokens: body.original_tokens as number,
      };
    },
  };

  /** The server's name, version and budgets. */
  async info(): Promise<ServerInfo> {
    const body = await this.request("GET", "/v1/info");
    return {
      name: body.name as string,
      version: body.version as string,
      budget: body.budget as number,
      maxBudget: body.max_budget as number,
    };
  }

  private async request(
    method: string,
    path: string,
    options: { query?: Query; body?: Record<string, unknown> } = {},
  ): Promise<Wire> {
    const url = new URL(this.baseUrl + path);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
    const headers: Record<string, string> = { accept: "application/json", ...this.headers };
    if (this.apiKey) headers.authorization = `Bearer ${this.apiKey}`;
    let payload: string | undefined;
    if (options.body !== undefined) {
      headers["content-type"] = "application/json";
      payload = JSON.stringify(options.body, (_key, value) => (value === undefined ? undefined : value));
    }
    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method,
        headers,
        body: payload,
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      throw new LLMSlimError(0, "unreachable", `could not reach LLMSlim at ${this.baseUrl}: ${reason}`);
    }
    const text = await response.text();
    let body: Wire = {};
    if (text) {
      try {
        body = JSON.parse(text) as Wire;
      } catch {
        throw new LLMSlimError(response.status, "invalid_response", `LLMSlim answered with non-JSON: ${text.slice(0, 200)}`);
      }
    }
    if (!response.ok) {
      const error = (body.error ?? {}) as { type?: string; message?: string };
      throw new LLMSlimError(response.status, error.type ?? "http_error", error.message ?? `HTTP ${response.status}`);
    }
    return body;
  }
}
