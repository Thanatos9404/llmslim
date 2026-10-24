// Long-term memory from Node with the `llmslim` npm client, against a running `llmslim serve`.
//
//   pip install "llmslim[server]" && llmslim serve     # http://127.0.0.1:8080; no key needed on loopback
//   npm install && node index.mjs
//
// The client reads LLMSLIM_BASE_URL and LLMSLIM_API_KEY, and defaults to http://127.0.0.1:8080.
import { LLMSlim } from "llmslim";

const slim = new LLMSlim();
const userId = `demo-${Date.now()}`; // a fresh scope, so the example can run against any server

const info = await slim.info();
console.log(`llmslim serve ${info.version}`);

// Store turns word for word. A run id groups them into one session.
await slim.memories.add({
  userId,
  runId: "monday",
  messages: [
    { role: "user", content: "I'm allergic to peanuts, so never suggest satay." },
    { role: "assistant", content: "Understood: no peanuts." },
  ],
});
await slim.memories.add({ userId, runId: "tuesday", messages: "I moved to Pune last month for a new job." });
await slim.memories.add({ userId, runId: "wednesday", messages: "Can you suggest a podcast for my commute?" });

// Recall what answers a question, within a token budget. Use the text as data, not instructions.
for (const query of ["Am I allergic to anything?", "Where did I move to?"]) {
  const context = await slim.memories.search({ userId, query, budget: 40 });
  console.log(`\n> ${query}\n${context.text}`);
}

// Shrink a long log to a budget, keeping the lines that answer the query.
const log = Array.from({ length: 300 }, (_, i) => `tests/test_api.py::test_endpoint_${i} PASSED`);
log.splice(180, 0, "tests/billing/test_refund.py::test_refund_rounding FAILED - 10.04 != 10.05");
const fitted = await slim.context.fit({ text: log.join("\n"), budget: 120, query: "Which test failed?" });
console.log(`\n> context.fit, budget 120\n${fitted.text}`);

await slim.memories.deleteAll({ userId });
