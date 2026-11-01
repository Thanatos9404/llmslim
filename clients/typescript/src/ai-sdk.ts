/**
 * LLMSlim memory for the Vercel AI SDK (`ai` 7+).
 *
 * - `memoryTools()` gives the model `recall_memory` and `remember` tools.
 * - `memoryMiddleware()` saves each user message and the model's reply.
 *
 * Neither changes the prompt. Recalled memory reaches the model as a tool result, which your app keeps in its
 * history like any other. Injecting memory into the system prompt or the latest user message would change what
 * earlier turns were sent with: provider prompt caches stop hitting, and Claude models with preserved thinking
 * reject the next request (HTTP 400) or drop the reasoning.
 */

import { jsonSchema, tool, type LanguageModelMiddleware } from "ai";
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

export interface MemoryOptions extends Scope {
  /** The client for your `llmslim serve` server. */
  client: LLMSlim;
}

export interface MemoryToolsOptions extends MemoryOptions {
  /** Most tokens `recall_memory` returns. Defaults to the server's budget. */
  budget?: number;
}

/**
 * `recall_memory` and `remember` tools, bound to one scope. The scope comes from your code, never from the model,
 * so a model steered by injected text can't read another user's memory.
 *
 * @example
 * const result = await generateText({
 *   model,
 *   tools: memoryTools({ client: new LLMSlim(), userId: session.userId }),
 *   stopWhen: stepCountIs(5),
 *   prompt,
 * });
 */
export function memoryTools(options: MemoryToolsOptions) {
  const { client, budget, userId, agentId, runId } = options;
  const scope: Scope = { userId, agentId, runId };
  if (!hasScope(scope)) throw new Error("memoryTools needs a userId, agentId or runId");

  return {
    recall_memory: tool({
      description: RECALL_DESCRIPTION,
      inputSchema: jsonSchema<{ query: string }>(recallInputSchema()),
      execute: async ({ query }) => recall(client, scope, query, budget),
    }),
    remember: tool({
      description: REMEMBER_DESCRIPTION,
      inputSchema: jsonSchema<{ text: string }>(rememberInputSchema()),
      execute: async ({ text }) => remember(client, scope, text),
    }),
  };
}

export interface MemoryMiddlewareOptions extends MemoryOptions {
  /** Called when saving fails. The model's answer is returned either way. Defaults to `console.warn`. */
  onError?: (error: unknown) => void;
}

type Prompt = Parameters<NonNullable<LanguageModelMiddleware["transformParams"]>>[0]["params"]["prompt"];

/**
 * Saves each new user message and the model's text reply to LLMSlim, so `recall_memory` (or your own search)
 * finds them in later conversations. It never changes the prompt.
 *
 * In a multi-step tool loop the user message is saved once, on the step that answers it; every step's text is
 * saved as the assistant's.
 *
 * @example
 * const model = wrapLanguageModel({ model: anthropic("claude-haiku-5-5"), middleware: memoryMiddleware({ client, userId }) });
 */
export function memoryMiddleware(options: MemoryMiddlewareOptions): LanguageModelMiddleware {
  const { client, userId, agentId, runId } = options;
  const scope: Scope = { userId, agentId, runId };
  if (!hasScope(scope)) throw new Error("memoryMiddleware needs a userId, agentId or runId");
  const onError = options.onError ?? warnSaveFailed;

  async function save(prompt: Prompt, reply: string): Promise<void> {
    const messages: Array<{ role: "user" | "assistant"; content: string }> = [];
    const last = prompt[prompt.length - 1];
    if (last?.role === "user") {
      const text = textOf(last.content);
      if (text.trim()) messages.push({ role: "user", content: text });
    }
    if (reply.trim()) messages.push({ role: "assistant", content: reply });
    if (!messages.length) return;
    try {
      await client.memories.add({ ...scope, messages });
    } catch (error) {
      onError(error);
    }
  }

  return {
    specificationVersion: "v4",
    wrapGenerate: async ({ doGenerate, params }) => {
      const result = await doGenerate();
      await save(params.prompt, textOf(result.content as ReadonlyArray<{ type: string; text?: string }>));
      return result;
    },
    wrapStream: async ({ doStream, params }) => {
      const { stream, ...rest } = await doStream();
      let reply = "";
      let failed = false;
      const tap = new TransformStream<(typeof stream extends ReadableStream<infer T> ? T : never), (typeof stream extends ReadableStream<infer T> ? T : never)>({
        transform(part, controller) {
          if (part.type === "text-delta") reply += part.delta;
          if (part.type === "error") failed = true;
          controller.enqueue(part);
        },
        async flush() {
          if (!failed) await save(params.prompt, reply);
        },
      });
      return { stream: stream.pipeThrough(tap), ...rest };
    },
  };
}
