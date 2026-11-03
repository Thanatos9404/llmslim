# Product logos

Logos of products the site names, self-hosted so the Content Security Policy stays `'self'`. They are used
nominatively: to identify a product where a page names it (a comparison, an integration guide, a table row). No
endorsement, sponsorship or partnership is implied, and every trademark stays its owner's.

All files were downloaded on 3 November 2026 into a fresh scratch directory, checked as untrusted SVG (no scripts,
event handlers, `foreignObject`, external references, entities or CSS imports; none had any) and copied byte for
byte, except where a row says otherwise. Colours are applied in CSS (`src/components/brand/product-logos.ts`).

## Simple Icons 16.36.0

Icon data under CC0 1.0 (https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md); the marks remain
trademarks of their owners, and Simple Icons asks users to follow each brand's guidelines. Downloaded from
`https://cdn.jsdelivr.net/npm/simple-icons@16.36.0/icons/<slug>.svg`. Single-colour marks, drawn as CSS masks.

| File | Product | Simple Icons slug | Simple Icons' own source |
|---|---|---|---|
| `anthropic.svg` | Anthropic | `anthropic` | https://www.anthropic.com |
| `claude.svg` | Claude | `claude` | https://claude.ai |
| `claude-code.svg` | Claude Code | `claudecode` | https://code.claude.com |
| `cursor.svg` | Cursor | `cursor` | https://cursor.com/brand |
| `google-gemini.svg` | Google Gemini | `googlegemini` | https://gemini.google.com |
| `haystack.svg` | Haystack (deepset) | `haystack` | https://github.com/simple-icons/simple-icons/issues/12288#issuecomment-2567870921 |
| `langchain.svg` | LangChain | `langchain` | https://www.langchain.com/langchain |
| `mcp.svg` | Model Context Protocol | `modelcontextprotocol` | https://github.com/modelcontextprotocol/docs/blob/573dc60c2e7aab2605b29d0bf27194aa7b02e4fb/logo/light.svg |
| `mongodb.svg` | MongoDB | `mongodb` | https://www.mongodb.com/pressroom |
| `neo4j.svg` | Neo4j | `neo4j` | https://neo4j.com/brand/#logo |
| `postgresql.svg` | PostgreSQL | `postgresql` | https://wiki.postgresql.org/wiki/Logo (trademark policy: https://www.postgresql.org/about/policies/trademarks/) |
| `pydantic.svg` | Pydantic (for Pydantic AI, whose docs use the same mark) | `pydantic` | https://github.com/pydantic/pydantic/blob/94c748001a32992a587694b999fb1f3d2f1fc1fe/docs/logo-white.svg |
| `python.svg` | Python | `python` | https://www.python.org/community/logos/ (downloaded on 3 November 2026, for /pricing and /docs) |
| `qwen.svg` | Qwen | `qwen` | https://qwen.ai |
| `razorpay.svg` | Razorpay | `razorpay` | https://razorpay.com/newsroom/brand-assets/ (downloaded on 3 November 2026, for /pricing) |
| `sqlite.svg` | SQLite | `sqlite` | https://github.com/sqlite/sqlite/blob/43e862723ec680542ca6f608f9963c0993dd7324/art/sqlite370.eps |
| `typescript.svg` | TypeScript | `typescript` | https://www.typescriptlang.org/branding (downloaded on 3 November 2026, for /docs) |
| `vercel.svg` | Vercel (for the Vercel AI SDK) | `vercel` | https://vercel.com/geist/brands |
| `zoho.svg` | Zoho | `zoho` | https://www.zoho.com/branding |

## The companies' own files

| File | Product | Source | Terms |
|---|---|---|---|
| `mem0-wordmark-light.svg`, `mem0-wordmark-dark.svg`, `mem0-icon.svg` | Mem0 | `docs/logo/light.svg`, `docs/logo/dark.svg` and `docs/logo/favicon.svg` in Mem0's own repository, the logo of its documentation site (https://github.com/mem0ai/mem0/tree/main/docs/logo, referenced from `docs/docs.json`) | Mem0's trademark; the repository is Apache-2.0. Used to name Mem0 on /compare/mem0. |
| `zep-lockup.svg` | Zep | https://www.getzep.com/zep-logo-lockup-daisy-bush-rgb.svg, the logo in the Organization data of https://www.getzep.com/ (identical artwork to https://www.getzep.com/zep-wordmark.svg, in #4226AA) | Zep's trademark. One colour, so it is a mask: Zep's purple on light backgrounds, the ink colour on dark ones (no light variant is published). |
| `zep-icon.svg` | Zep | `assets/zep-logo-icon-gradient-rgb.svg` in Zep's own repository (https://github.com/getzep/zep/tree/main/assets) | Zep's trademark. |
| `llamaindex-icon.svg` | LlamaIndex | https://www.llamaindex.ai/brand/llamaindex-logo.svg, from LlamaIndex's brand page (https://llamaindex.ai/brand) | LlamaIndex's trademark; the brand page asks for the logomark where space is tight. |
| `llmlingua.webp` | LLMLingua (Microsoft Research) | `images/LLMLingua_logo.png` (1024 x 1024 PNG) in https://github.com/microsoft/LLMLingua, the logo in the project README | Microsoft's; the repository is MIT. Resized to 96 x 96 (it is shown at 16 to 28px) and saved as WebP (quality 86); otherwise unchanged. |
| `gptme-mono.svg` | gptme | `media/icon-mono.svg` in https://github.com/gptme/gptme (its media README describes it as the single-colour icon for themed contexts) | gptme's; the repository is MIT. |
| `mastra.svg` | Mastra | The single path of `LogoWithoutText` in Mastra's own UI code, `packages/playground-ui/src/ds/components/Logo/MastraLogo.tsx` in https://github.com/mastra-ai/mastra at commit 7707dd7fe9cdd24f693ceed7b9732e00365ea574. Mastra publishes no brand kit. | Mastra's trademark. The path data is unchanged; it was wrapped in a standalone `<svg>` with the same `viewBox` (`0 0 34 21`). |

## Reused from elsewhere in `public/`

| File | Product | Recorded source |
|---|---|---|
| `/openai-symbol.svg` | OpenAI | From `@lobehub/icons` (MIT, licence text in the file), added on 21 September 2026. Simple Icons no longer carries OpenAI, and https://openai.com/brand returned 403 to a script. |
| `/sarvam-symbol.svg` | Sarvam | Sarvam's brand website (see `web/DESIGN_NOTES.md`). |
| `/startups/exa-blue.svg`, `/startups/exa-white.svg` | Exa | Exa's brand kit, https://exa.ai/brand (see `web/DESIGN_NOTES.md`). |

## No logo file

- **Hermes Agent** (Nous Research): its repository's icons (`assets/icon-master.svg`, 116 KB) are too heavy for a 26 px
  tile, and no small official mark was found. The integrations list keeps the existing `IntegrationIcon` fallback
  (the `@lobehub/icons` component).
- **Graphiti** (Zep's open-source framework) and **Microsoft** are named as text only. Zep rows use Zep's logo because
  the system is labelled "Zep (Graphiti on Neo4j)".
