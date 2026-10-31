/**
 * LLMSlim memory for Mastra agents (`@mastra/core` 1.x).
 *
 * - `memoryTools()` gives the agent `recall_memory` and `remember` tools.
 * - `memoryProcessor()` is an output processor that saves each user message and the agent's reply.
 *
 * Neither changes the prompt, and there is deliberately no input processor that adds recalled memory to it.
 * Recalled memory reaches the model as a tool result, which stays in the history like any other. Injecting memory
 * into the system prompt or next to the latest user message would change what earlier turns were sent with:
 * provider prompt caches stop hitting, and Claude models with preserved thinking reject the next request (HTTP 400)
 * or drop the reasoning.
 *
 * Whose memory is read and written comes from your code, never from the model: fixed ids, or a function of Mastra's
 * request context, so one agent can serve many users.
 */

import type { ProcessOutputResultArgs } from "@mastra/core/processors";
import { RequestContext } from "@mastra/core/request-context";
import { createTool } from "@mastra/core/tools";
import type { LLMSlim, Scope } from "./index.js";
import {
  RECALL_DESCRIPTION,
  REMEMBER_DESCRIPTION,
  hasScope,
  recall,
  recallInputSchema,
  remember,
  rememberInputSchema,
  textOf,
  warnSaveFailed,
} from "./shared.js";

/** Scope ids as a `scope` function may return them. Each must be a string, or left out. */
export type ScopeInput = { [K in keyof Scope]?: unknown };

/**
 * Resolves the scope for one request from Mastra's request context.
 *
 * Read ids your server sets, not ones a client can send. With Mastra's server, `MASTRA_RESOURCE_ID_KEY` is set from
 * the signed-in user (`auth.mapUserToResourceId`) and a client can't override it; other request context keys may
 * come from the request body.
 */
export type ScopeResolver = (requestContext: RequestContext<any>) => ScopeInput | Promise<ScopeInput>;

export interface MemoryOptions extends Scope {
  /** The client for your `llmslim serve` server. */
  client: LLMSlim;
  /**
   * Resolves the scope per request, instead of fixed `userId`, `agentId` and `runId` (pass one or the other).
   *
   * An id left out matches any on reads: `{ agentId: "support" }` reads every user's memory for that agent. When a
   * request has no user, return no ids (or throw): the tools then refuse and the processor saves nothing.
   *
   * @example
   * scope: (requestContext) => ({ userId: requestContext.get(MASTRA_RESOURCE_ID_KEY) })
   */
  scope?: ScopeResolver;
}

export interface MemoryToolsOptions extends MemoryOptions {
  /** Most tokens `recall_memory` returns. Defaults to the server's budget. */
  budget?: number;
}

export interface MemoryProcessorOptions extends MemoryOptions {
  /**
   * Called when saving fails, or when the request has no scope. The agent's answer is returned either way.
   * Defaults to `console.warn`. Errors it throws are ignored.
   */
  onError?: (error: unknown) => void;
}

const SCOPE_KEYS = ["userId", "agentId", "runId"] as const;

/** Checks ids and keeps only the scope keys. Absent means `undefined` or `null`; anything else must be a string. */
function checkScope(input: unknown, where: string): Scope {
  if (typeof input !== "object" || input === null) {
    throw new TypeError(`${where}: the scope must be an object with a userId, agentId or runId`);
  }
  const scope: Scope = { userId: undefined, agentId: undefined, runId: undefined };
  for (const key of SCOPE_KEYS) {
    const value = (input as Record<string, unknown>)[key];
    if (value === undefined || value === null) continue;
    if (typeof value !== "string") throw new TypeError(`${where}: ${key} must be a string, not ${typeof value}`);
    if (!value.trim()) throw new Error(`${where}: ${key} is empty`);
    scope[key] = value;
  }
  if (!hasScope(scope)) throw new Error(`${where} needs a userId, agentId or runId`);
  return scope;
}

/** Turns the options into a function from the request context to a checked scope. */
function scopeResolver(options: MemoryOptions, name: string): (requestContext: RequestContext | undefined) => Promise<Scope> {
  const { scope, userId, agentId, runId } = options;
  if (scope === undefined) {
    const fixed = checkScope({ userId, agentId, runId }, name);
    return async () => fixed;
  }
  if (typeof scope !== "function") throw new TypeError(`${name}: scope must be a function of the request context`);
  if (userId !== undefined || agentId !== undefined || runId !== undefined) {
    throw new Error(`${name} takes fixed ids or a scope function, not both`);
  }
  return async (requestContext) =>
    checkScope(await scope(requestContext ?? new RequestContext()), `${name}: the scope for this request`);
}

function stringInput(input: unknown, key: string): string {
  const value = typeof input === "object" && input !== null ? (input as Record<string, unknown>)[key] : undefined;
  if (typeof value !== "string") throw new TypeError(`${key} must be a string`);
  return value;
}

/**
 * `recall_memory` and `remember` tools. The scope comes from your code (fixed ids, or `scope` from the request
 * context), never from the model: their only inputs are `query` and `text`, and Mastra rejects any other field.
 *
 * @example
 * const agent = new Agent({
 *   id: "assistant",
 *   name: "Assistant",
 *   instructions: "...",
 *   model,
 *   tools: memoryTools({ client, scope: (ctx) => ({ userId: ctx.get(MASTRA_RESOURCE_ID_KEY) }) }),
 * });
 */
export function memoryTools(options: MemoryToolsOptions) {
  const { client, budget } = options;
  const resolve = scopeResolver(options, "memoryTools");

  return {
    recall_memory: createTool({
      id: "recall_memory",
      description: RECALL_DESCRIPTION,
      inputSchema: recallInputSchema(),
      execute: async (input, context) =>
        recall(client, await resolve(context?.requestContext), stringInput(input, "query"), budget),
    }),
    remember: createTool({
      id: "remember",
      description: REMEMBER_DESCRIPTION,
      inputSchema: rememberInputSchema(),
      execute: async (input, context) =>
        remember(client, await resolve(context?.requestContext), stringInput(input, "text")),
    }),
  };
}

type OutputMessage = ProcessOutputResultArgs["messages"][number];
type MessageList = ProcessOutputResultArgs["messageList"];

/** A run that a guardrail stopped, that was cancelled, that failed, or that is waiting on a tool approval. */
const UNFINISHED = new Set(["tripwire", "aborted", "error", "suspended"]);

function messageText(message: OutputMessage): string {
  const text = textOf(message.content?.parts ?? []);
  if (text || message.content?.parts?.length) return text;
  return typeof message.content?.content === "string" ? message.content.content : "";
}

/** The output processor `memoryProcessor()` returns. */
export interface MemoryProcessor {
  readonly id: "llmslim-memory";
  readonly name: string;
  processOutputResult(args: ProcessOutputResultArgs): Promise<MessageList>;
}

/**
 * An output processor that saves the latest user message and the agent's reply to LLMSlim, word for word, once
 * per `generate()` or `stream()`. It never changes the messages or the response.
 *
 * - The reply is the text of the run's assistant messages, as earlier output processors left it: with a multi-step
 *   tool run, the text of every step, as the user was shown it, without tool calls or results.
 * - Nothing is saved when a processor's tripwire stopped the run, when it was aborted or failed, or while it waits
 *   for a tool approval. A step a guardrail rejected and Mastra retried is not saved; the retried answer is.
 * - List it last: an output processor that trips or retries after it has run can't undo the save.
 * - A failed save is passed to `onError` (default `console.warn`); the response is returned either way.
 *
 * @example
 * new Agent({ ..., outputProcessors: [moderation, memoryProcessor({ client, userId })] });
 */
export function memoryProcessor(options: MemoryProcessorOptions): MemoryProcessor {
  const { client } = options;
  const resolve = scopeResolver(options, "memoryProcessor");
  const onError = options.onError ?? warnSaveFailed;

  function report(error: unknown): void {
    try {
      onError(error);
    } catch {
      // The response must not fail because the error handler did.
    }
  }

  return {
    id: "llmslim-memory",
    name: "LLMSlim memory",
    async processOutputResult({ messages, messageList, result, requestContext }) {
      // A step a guardrail rejected with `retry` keeps its tripwire in `steps`; only the run's outcome counts.
      if (result && (UNFINISHED.has(result.finishReason) || result.steps?.[result.steps.length - 1]?.tripwire)) {
        return messageList;
      }

      const turn: Array<{ role: "user" | "assistant"; content: string }> = [];
      // The newest user or assistant message in this call's input. Signals, such as a guardrail's retry feedback,
      // are Mastra's, not the user's.
      const last = messageList.get.input
        .db()
        .filter((message) => message.role === "user" || message.role === "assistant")
        .pop();
      if (last?.role === "user") {
        const text = messageText(last);
        if (text.trim()) turn.push({ role: "user", content: text });
      }
      const reply = messages
        .filter((message) => message.role === "assistant" && !message.content?.metadata?.completionResult)
        .map(messageText)
        .join("");
      if (reply.trim()) turn.push({ role: "assistant", content: reply });
      if (!turn.length) return messageList;

      try {
        await client.memories.add({ ...(await resolve(requestContext)), messages: turn });
      } catch (error) {
        report(error);
      }
      return messageList;
    },
  };
}
