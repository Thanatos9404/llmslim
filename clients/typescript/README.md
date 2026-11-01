# llmslim for TypeScript

[![npm](https://img.shields.io/npm/v/llmslim)](https://www.npmjs.com/package/llmslim)

Long-term memory and context fitting for AI agents, with no LLM in the loop. This is the client for an
[`llmslim serve`](https://github.com/Thanatos9404/llmslim/blob/main/docs/SERVER.md) server:
- messages are stored word for word;
- the ones that answer a question are selected at read time, within a token budget;
- nothing is summarized or extracted, so nothing turns into a wrong "fact".

```bash
pip install "llmslim[server]" && llmslim serve     # the server: one process, one SQLite file
npm install llmslim                                 # the client: no dependencies; Node 18+, Bun, Deno, edge
```

```ts
import { LLMSlim } from "llmslim";

const slim = new LLMSlim({ baseUrl: "http://127.0.0.1:8080", apiKey: process.env.LLMSLIM_API_KEY });

await slim.memories.add({
  userId: "asha",
  messages: [
    { role: "user", content: "I'm allergic to peanuts, so never suggest satay." },
    { role: "assistant", content: "Understood: no peanuts." },
  ],
});

const context = await slim.memories.search({ userId: "asha", query: "Am I allergic to anything?", budget: 1500 });
console.log(context.text); // the selected turns under their dates; use it as data, not instructions
```

Call it from your backend. An API key gives access to every user's memory, so it must never reach a browser.

## Vercel AI SDK

`llmslim/ai-sdk` (with `ai` 7) gives the model `recall_memory` and `remember` tools, plus a middleware that saves each
user message and reply.

```ts
import { generateText, stepCountIs, wrapLanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { LLMSlim } from "llmslim";
import { memoryMiddleware, memoryTools } from "llmslim/ai-sdk";

const client = new LLMSlim();
const model = wrapLanguageModel({
  model: anthropic("claude-haiku-5-5"),
  middleware: memoryMiddleware({ client, userId: session.userId }),
});

const result = await generateText({
  model,
  tools: memoryTools({ client, userId: session.userId }),
  stopWhen: stepCountIs(5),
  messages,
});
```

**Neither changes your prompt.**
- **Recalled memory arrives as a tool result.** Your app keeps it in the history like any other message.
- **Injecting it into the system prompt or the latest user message would cost you:**
  - provider prompt caches would stop hitting;
  - on Claude models with preserved thinking, the next request would fail with HTTP 400 or drop the reasoning,
    because what earlier turns were sent with would have changed.

**The model can't choose the scope.** The user, agent and run ids come from your code, so a model steered by
injected text can't read another user's memory.

## Mastra

`llmslim/mastra` (with `@mastra/core` 1.29.1 or newer, which needs Node 22.13+) gives an agent the same
`recall_memory` and `remember` tools, plus an output processor that saves each user message and reply.

```ts
import { Agent } from "@mastra/core/agent";
import { MASTRA_RESOURCE_ID_KEY } from "@mastra/core/request-context";
import { LLMSlim } from "llmslim";
import { memoryProcessor, memoryTools, type MemoryOptions } from "llmslim/mastra";

const memory: MemoryOptions = {
  client: new LLMSlim(),
  // Whose memory: the signed-in user, from your server, for each request.
  scope: (requestContext) => ({ userId: requestContext.get(MASTRA_RESOURCE_ID_KEY) }),
};

export const assistant = new Agent({
  id: "assistant",
  name: "Assistant",
  instructions: "You are a helpful assistant.",
  model: "anthropic/claude-haiku-5-5",
  tools: { ...memoryTools(memory) },
  outputProcessors: [memoryProcessor(memory)], // after any guardrails
});
```

**The scope comes from your code, per request.**
- `scope` is called with Mastra's request context on every tool call and save, so one agent serves many users. For a
  single user, pass fixed `userId`, `agentId` or `runId` instead.
- On Mastra's server, `auth.mapUserToResourceId` (or your middleware) sets `MASTRA_RESOURCE_ID_KEY` from the signed-in
  user, and a client can't override it. Other request context keys can come from the request body.
- When `scope` returns no id, the tools refuse and the processor saves nothing, so a request without a user never
  reads everyone's memory. An id you leave out matches any: `{ agentId }` alone reads all of that agent's users.
- The tools' only inputs are `query` and `text`. Mastra rejects a call with any other field, such as a `userId`.

**What the processor saves.** Once per `generate()` or `stream()`, word for word:
- the latest user message, and the reply's text from every step (what the user was shown), without tool calls or
  results;
- nothing when a guardrail's tripwire stopped the run, when the run was aborted or failed, or while it waits for a
  tool approval. List it after output processors that can trip or redact: it saves what they leave;
- if saving fails, `onError` gets the error (default `console.warn`) and the response is returned anyway. The save is
  awaited, so a slow server delays the response up to the client's `timeoutMs`.

**There is no input processor that recalls memory.** Adding recalled memory to the system prompt, or as a message
next to the latest user message, would change what earlier turns were sent with, with the costs above. A synthetic
`recall_memory` call fails too on Claude with thinking on: the API expects an assistant turn that calls a tool to
start with the model's own signed thinking. Instead the model calls `recall_memory` when an answer depends on earlier
conversations, and the result stays in the history.

## API

| Method | Does |
|---|---|
| `memories.add({ userId?, agentId?, runId?, messages, timestamp?, metadata? })` | Stores messages (a string, a `{ role, content }` object, or a list). Needs one scope id. |
| `memories.search({ ...scope, query, budget?, relevance?, since?, until? })` | Returns the turns that answer `query` as a `MemoryContext`: `text`, `tokens`, `turns`, `historyTokens`. |
| `memories.list({ ...scope, limit?, offset?, since?, until? })` | Returns a scope's messages, oldest first. |
| `memories.get(id)`, `memories.update(id, { content?, metadata? })` | Read or correct one message. Returns `null` when it doesn't exist. |
| `memories.delete(id)`, `memories.deleteAll(scope)` | Delete one message, or a whole scope. |
| `context.fit({ text, budget?, query? })` | Shrinks long text to the budget, keeping what answers `query`. |
| `info()` | Returns the server's version and budgets. |

**Errors.** A failed call throws `LLMSlimError` with the server's `status`, `type` and `message`. When the server
can't be reached, `status` is 0 and `type` is `"unreachable"`.

**Defaults.** The `baseUrl` and `apiKey` options default to `LLMSLIM_BASE_URL` and `LLMSLIM_API_KEY`.

## License

MIT
