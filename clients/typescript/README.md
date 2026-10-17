# llmslim for TypeScript

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
