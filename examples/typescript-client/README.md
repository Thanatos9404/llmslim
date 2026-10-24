# TypeScript client against `llmslim serve`

[`index.mjs`](index.mjs) uses the [`llmslim` npm package](https://www.npmjs.com/package/llmslim) (no dependencies;
Node 18+, Bun, Deno) to store messages, recall them within a token budget, and fit a long log into a budget, through
`llmslim serve`. The server is one Python process with one SQLite file and makes no model calls.

```bash
pip install "llmslim[server]"
llmslim serve                      # http://127.0.0.1:8080; no key needed on loopback

cd examples/typescript-client
npm install
node index.mjs
```

The client reads `LLMSLIM_BASE_URL` and `LLMSLIM_API_KEY` and defaults to `http://127.0.0.1:8080`. An API key gives
access to every user's memory, so call the server from your backend, never from a browser. The example writes to a
fresh user id and deletes it at the end.

Output (llmslim 0.11.1, npm llmslim 0.1.0; your dates will differ):

```text
llmslim serve 0.11.1

> Am I allergic to anything?
[2026-10-23 (Fri) 21:07]
user: I'm allergic to peanuts, so never suggest satay.

> Where did I move to?
[2026-10-23 (Fri) 21:07] user: I moved to Pune last month for a new job.

> context.fit, budget 120
tests/test_api.py::test_endpoint_0 PASSED
... [178 similar lines]
tests/test_api.py::test_endpoint_179 PASSED
tests/billing/test_refund.py::test_refund_rounding FAILED - 10.04 != 10.05
tests/test_api.py::test_endpoint_180 PASSED
... [118 similar lines]
tests/test_api.py::test_endpoint_299 PASSED
```

For TypeScript, the code is the same: the package ships its types. With the Vercel AI SDK, `llmslim/ai-sdk` adds
`recall_memory` and `remember` tools and a middleware that saves turns; see
[clients/typescript](../../clients/typescript/README.md). The HTTP API is in [docs/SERVER.md](../../docs/SERVER.md).

## Test

`npm test` starts `llmslim serve` on a free port with a temporary database, runs `index.mjs` against it and checks the
output. It starts the server with `python`, or with the interpreter in `LLMSLIM_PYTHON`, which needs
`pip install "llmslim[server]"`. CI runs it in the TypeScript client job.
