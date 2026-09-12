# Live Studio deployment requirements

`/api/compress` is a Vercel Python Function in `web/api/compress.py`.
Production installs `llmslim==0.5.0` from PyPI via `web/requirements.txt`.
Publish and verify that package before deploying the website. Local development
can import the sibling repository package; no duplicated compression implementation
is maintained in the web project.

The function is deliberately same-origin and adds no CORS wildcard. It accepts
only public, offline extractive compression; rewrite and hybrid require a
caller-supplied provider and are unavailable in the public Studio.

## Local end-to-end verification

Vercel's local Python runtime serves the function independently of this
monorepo's Next route proxy. For a local end-to-end Studio check only, run the
Vercel function on port 3001, then start Next with
`LLMSLIM_STUDIO_LOCAL_API_ORIGIN=http://127.0.0.1:3001` and
`LLMSLIM_STUDIO_E2E=1`. The development-only rewrite keeps the browser request
at `/api/compress`, while the alternate build directory avoids a collision with
an already-running local Next server. Neither variable is set in production,
where Vercel serves the Python Function directly on the same origin.

## Public-compute safeguards

- 80 KB JSON body cap; 48,000 character and 12,000 actual-token input caps.
- Validated `target_ratio` (0.10â€“0.90), `ContextRole`, extractive-only
  strategy, and optional `max_chunk_tokens` (32â€“4,000).
- Vercel's default ten-second function limit and an eight-second browser request timeout.
- No provider credentials, arbitrary code, imports, filesystem paths, regexes,
  or hidden request parameters are accepted.
- Per-instance in-memory limit: 30 requests per client key per minute, matching the
  production Vercel WAF policy.

The in-memory guard is intentionally lightweight and cannot coordinate across
serverless instances. Before production exposure, configure a Vercel WAF/rate
limit rule for `/api/compress` if the project plan supports it; that is the
remaining deployment-layer abuse-control requirement.
