# Studio deployment

The Studio is a Next.js page with same-origin Vercel Python Functions in `web/api`.

- `/api/studio` serves the Studio page. It compresses the submitted text around a question with
  `llmslim.compress(..., query=...)`, cuts the same text to the same token count for comparison, and
  returns which parts of the original were kept. It calls no model provider and needs no secrets.
- `/api/compress`, `/api/plan` and `/api/context` remain available for scripted use.

Production installs the released package from PyPI through `web/requirements.txt` (`llmslim==0.8.0`).
Release that version to PyPI before deploying a site that pins it.

## Local development

Run a function locally from a checkout whose `llmslim` package is the version you want to test, then point
the dev server at it:

```bash
python -c "import importlib.util as u, http.server as h; s=u.spec_from_file_location('studio', 'web/api/studio.py'); m=u.module_from_spec(s); s.loader.exec_module(m); h.ThreadingHTTPServer(('127.0.0.1', 8799), m.handler).serve_forever()"
LLMSLIM_STUDIO_LOCAL_API_ORIGIN=http://127.0.0.1:8799 npm --prefix web run dev
```

`next.config.ts` forwards `/api/studio`, `/api/compress`, `/api/plan` and `/api/context` to that origin only when
`LLMSLIM_STUDIO_LOCAL_API_ORIGIN` is set.

## Limits

Each function bounds the request body, text length and token count, and applies a best-effort per-instance rate
limit. Add platform-level rate limiting for public traffic. Nothing submitted is stored or logged.
