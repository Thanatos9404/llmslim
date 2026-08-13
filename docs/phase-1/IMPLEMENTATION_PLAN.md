# LLMSlim v0.3.1 — Phase 1 Security Hardening & Core Correctness Implementation Plan

**Target Version:** `v0.3.1`  
**Theme:** Security Hardening + Core Correctness + Benchmark Infrastructure  
**Authoritative Specification:** `docs/phase-0/FINAL_BASELINE.md`  
**Date:** 2026-08-11 (Revised)  
**Status:** APPROVED IMPLEMENTATION PLAN (revised after review)

---

## 0. Revision Notes (what changed in this revision and why)

This plan was revised before implementation to correct several inaccuracies and
weak security assumptions found during review. The substantive changes:

1. **Dropped the "100% backward compatibility" claim.** Two behavioral changes are
   introduced deliberately (see §8): `compress_documents()` now defaults to RAG
   provenance, and `compress_chat_messages()` now propagates per-message role
   provenance. These are documented as intentional and covered by regression tests.
2. **Reframed the security model around trust boundaries, not keyword capping.**
   Provenance is threaded through the pipeline as first-class metadata. The
   security boundary is "who authored the text" (trusted caller vs. untrusted
   external content), not "does the wording look imperative." (§3)
3. **Closed the `preserve_patterns` bypass.** `preserve_patterns` are
   developer-authored, but they match attacker-controlled content. In untrusted
   roles (RAG/TOOL) they no longer grant the hard-locked Priority 4 tier. (§3, §5.1)
4. **Fixed the chat-role mapping.** Explicit handling for `system`, `developer`,
   `user`, `assistant`, `tool`. No silent collapse of `assistant -> USER`. (§4, §5.6)
5. **Documented the trust model for `mode="system"` / caller-asserted roles.**
   LLMSlim cannot authenticate provenance; it trusts the caller's label. (§3.3)
6. **Replaced template "sanitization" with a structurally safe nonce fence** that
   preserves user content byte-for-byte. Round-trip tests added. (§5.5)
7. **Removed the "~95% coverage" prediction.** Only measured coverage is reported. (§9)
8. **Fixed the benchmark acceptance count** to the real baseline (389) plus the
   new tests actually added. (§10, §12)
9. **Corrected the `benchmark.py` fix.** `-o addopts=` *does* override the
   configured `addopts` (verified). The runner is changed to report the real
   pytest result via a collector plugin instead of hardcoding counts. (§5.7)
10. **Expanded the mixed-context security test matrix.** (§6, §7)
11. **`ContextRole` export is a deliberate, documented public API addition;** string
    values remain fully supported so existing callers are unaffected. (§4)
12. **Clarified `token_counter_used`** as the process-level active tokenizer
    resolved at result-construction time, with documented limitations. (§5.4)
13. **Added an explicit security-limitation statement** (§13): this mitigates
    LLMSlim's compression-induced instruction elevation; it is not complete
    prompt-injection prevention. Defense in depth still required.

---

## 1. Executive Summary

This document specifies the implementation plan for **LLMSlim v0.3.1**. Following
the approved engineering baseline in `FINAL_BASELINE.md`, Phase 1 resolves the
verified P0 blockers and P1 defects across security, algorithmic correctness, and
benchmark infrastructure.

### Primary Objectives
1. **P0-1 — Provenance-Aware Priority Locking:** Introduce a structured
   `ContextRole` provenance boundary that survives the pipeline. Untrusted RAG
   passages and tool outputs can no longer reach the hard-locked Priority Tier 4
   through imperative keywords, safety patterns, *or* `preserve_patterns`.
2. **P0-2 — Inline Code Span Protection:** Prevent `split_sentences()` from
   splitting inside inline backtick code spans (`` `foo.bar()` ``).
3. **P0-3 — Benchmark Runner Repair:** Make `benchmarks/benchmark.py` report the
   real pytest pass/fail counts instead of hardcoded fallbacks.
4. **P1-1 — Template Breakout Protection:** Prevent `---END TEXT---` fence
   breakout using a structurally safe nonce fence that preserves content exactly.
5. **P1-2 — CJK Sentence Splitting:** Support `。`, `！`, `？` boundaries.
6. **P1-3 — Dead Code Removal:** Remove the uncalled `_knapsack_select()`,
   `_select_for_chunk()`, and `_greedy_select()` static methods in `core.py`.
7. **P1-4 — Token Counter Transparency:** Add `token_counter_used` to
   `CompressionResult` and warn once when falling back to the char heuristic.

Backward compatibility is preserved for the default `compress()` API surface;
the two intentional behavioral changes in the pipeline helpers are documented in §8.

---

## 2. Exact Current-Code Findings (verified against repo)

### `llmslim/ranking.py`
- `_CRITICAL_PATTERNS` / `_SAFETY_CRITICAL_PATTERNS` / `_HIGH_PRIORITY_PATTERNS`
  match imperative terms (`must`, `never`, `always`, `you are`, `WARNING:`, `System:`).
- `get_sentence_priority(sentence, preserve_res)` (lines ~163–175) evaluates a
  sentence with no knowledge of its source role. `preserve_res` match → Priority 4;
  `_SAFETY_CRITICAL_RE` → Priority 4; `_HIGH_PRIORITY_RE` → Priority 3.
- `_is_must_keep(sentence, preserve_res)` (lines ~320–325) returns `True` for any
  code span, any `_CRITICAL_RE` match, or any `preserve_res` match.
- `score_chunk_sentences(...)` (lines ~348–421) takes no provenance parameter.

### `llmslim/core.py`
- `_compress_extractive` Pass 1 (line ~509) force-keeps `priority >= 3` regardless
  of budget.
- `_select_for_chunk()` / `_knapsack_select()` / `_greedy_select()` (lines ~706–839)
  are dead code — never called by `_compress_extractive()` (which uses an inline
  greedy sort). Confirmed by grep: only references are in `tests/test_core.py`.

### `llmslim/tokenization.py`
- `_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)` protects fenced
  blocks only; inline backtick spans are unprotected.
- `_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")` handles only
  Western punctuation + trailing whitespace + uppercase/digit; no CJK support and
  fails when there is no trailing space.

### `llmslim/tokens.py`
- `count_tokens()` silently falls back to `max(1, round(len(text)/4))` when
  `tiktoken` is unavailable — no warning, no telemetry.

### `llmslim/rewrite/templates.py`
- `format_user_prompt()` interpolates `{text}` between literal `---BEGIN TEXT---`
  / `---END TEXT---` fences. Literal `---END TEXT---` in user text breaks out.

### `llmslim/pipelines.py`
- `compress_chat_messages` calls `compress(content)` without passing the role.
- `compress_documents` calls `compress(doc, query=query)` without RAG provenance.

### `benchmarks/benchmark.py`
- `run_unit_tests()` calls `pytest.main(["-q", "tests"])` and returns hardcoded
  `(159, 0)` on success or `(154, 5)` on failure. Because the programmatic run
  inherits the configured `addopts` (`--cov-fail-under=90`) but coverage only sees
  the tests actually imported in-process, the coverage gate fails and the runner
  emits the false 5-failure result.

**Verified invocation fact (correcting the previous plan):** running
`pytest.main(["-q", "tests", "-o", "addopts="])` **does** override the configured
`addopts` and yields `389 passed`, exit code `0`. `-o addopts=` is therefore an
override, not a no-op. The chosen fix (§5.7) clears the coverage args for the
in-process run *and* reports the real counts via a collector plugin.

---

## 3. Security Architecture (Provenance / Trust Boundary)

### 3.1 Trust model
Sentences are classified by **provenance**, i.e. who authored them, not by whether
their wording looks like an instruction:

| Role | Trust | Priority 4 hard-lock from wording? | Rationale |
|------|-------|-----------------------------------|-----------|
| `SYSTEM` | Trusted | Yes | Developer-authored system prompt |
| `DEVELOPER` | Trusted | Yes | Developer-authored directive (OpenAI "developer" role) |
| `USER` | Semi-trusted | No (max Tier 3) | End-user's own turn; their imperatives are their own, but not safety-critical guardrails |
| `ASSISTANT` | Untrusted-ish | No (max Tier 2) | Prior model output; may echo injected content |
| `TOOL` | Untrusted | No (max Tier 2) | External tool/function output |
| `RAG` | Untrusted | No (max Tier 2) | Retrieved third-party document |
| `GENERAL` | Default | Yes (legacy behavior) | Unlabeled text; preserves v0.3.0 behavior |

The security boundary is between **trusted** (SYSTEM/DEVELOPER) and **untrusted**
(RAG/TOOL/ASSISTANT) content. Untrusted content competes on relevance score and can
still be retained, but it cannot *hijack* the hard-locked tier that bypasses the
token budget.

### 3.2 Provenance is metadata that survives the pipeline
`context_role` is threaded end-to-end:

```
compress(..., context_role) 
  -> ContextCompressor.compress(..., context_role)
     -> _compress_extractive(..., context_role)
        -> score_chunk_sentences(..., context_role)
           -> get_sentence_priority(..., context_role)
           -> _is_must_keep(..., context_role)
```

The role is resolved once (§5.2) and passed as an explicit argument at every layer,
so provenance is never re-inferred from the sentence text itself.

### 3.3 What "trusted" means (and its limit)
LLMSlim trusts the **role label supplied by the caller**. It cannot independently
authenticate that text marked `system` truly originated from the developer. If a
caller places attacker-controlled text into a `system`/`developer` slot (or calls
`compress(untrusted_text, mode="system")`), LLMSlim will treat it as trusted — this
is a property of the caller's data flow, not something LLMSlim can detect. This
trust boundary is documented in code and covered by a test that asserts the
documented behavior (untrusted text explicitly marked `system` *is* trusted, by
design, and callers must not do this).

### 3.4 OWASP alignment
OWASP LLM01 (Prompt Injection) recommends **identifying and segregating external
content** and enforcing **trust boundaries** between instructions and untrusted
data — not merely down-weighting imperative wording. This design implements a
provenance boundary consistent with that guidance. See §13 for the explicit
limitation statement.

---

## 4. API Changes & Public Signatures

All new parameters have backward-compatible defaults. `context_role` accepts either
a `ContextRole` enum or a plain string (`"system"`, `"rag"`, ...), so string usage
requires no new imports.

### `ContextRole` (new enum, `llmslim/core.py`)
```python
class ContextRole(str, Enum):
    SYSTEM = "system"        # trusted developer/system prompt
    DEVELOPER = "developer"  # trusted developer directive
    USER = "user"            # end-user's own input turn
    ASSISTANT = "assistant"  # prior model output (not authoritative)
    TOOL = "tool"            # untrusted tool/function output
    RAG = "rag"              # untrusted retrieved document
    GENERAL = "general"      # default; legacy v0.3.0 behavior
```

**Public API decision (deliberate):** `ContextRole` is exported from the top-level
`llmslim` package and added to `__all__`, because callers need a discoverable,
documented vocabulary for the new `context_role` parameter. This is the only new
name added to the public surface. Existing callers are unaffected because:
- every new parameter is optional with a safe default, and
- string values are accepted everywhere a `ContextRole` is accepted.

### `ContextCompressor.__init__(..., context_role: Union[ContextRole, str] = ContextRole.GENERAL)`
### `ContextCompressor.compress(..., context_role: Optional[Union[ContextRole, str]] = None)`
### module-level `compress(..., context_role: Optional[Union[ContextRole, str]] = None, **kwargs)`
### `CompressionResult.token_counter_used: str = "tiktoken"` (`"tiktoken"` | `"heuristic"`)

### Pipeline helpers
```python
def compress_documents(documents, query=None, target_ratio=0.5,
                       context_role: Union[ContextRole, str] = ContextRole.RAG, **kwargs): ...

def compress_chat_messages(messages, target_ratio=0.5,
                           compressible_roles=DEFAULT_COMPRESSIBLE_ROLES,
                           min_tokens=60, **kwargs): ...
# Internally maps each message's role -> ContextRole (see §5.6) and passes it to compress().
```

---

## 5. File-by-File Change Plan

### 5.1 `llmslim/ranking.py`
- Add `context_role: str = "general"` to `get_sentence_priority()`,
  `_is_must_keep()`, and `score_chunk_sentences()`.
- Normalize with `str(context_role).lower()`.
- Define `_TRUSTED_ROLES = {"system", "developer", "general"}` and
  `_SEMI_TRUSTED_ROLES = {"user"}`. Everything else (`rag`, `tool`, `assistant`) is
  untrusted.
- **`get_sentence_priority`:**
  - Trusted roles: unchanged legacy behavior (preserve_patterns → 4,
    safety-critical → 4, high-priority → 3, ...).
  - `USER`: imperative/role language may reach **Tier 3** but not the
    safety-critical **Tier 4** (which is reserved for developer/system guardrails).
    `preserve_patterns` still grant Tier 4 for USER because those patterns are
    developer-authored and the user turn is the caller's own first-party data.
  - Untrusted roles (`rag`/`tool`/`assistant`): **hard cap at Tier 2.**
    `_CRITICAL_RE`, `_SAFETY_CRITICAL_RE`, `_HIGH_PRIORITY_RE`, **and**
    `preserve_patterns` do **not** elevate beyond Tier 2. This closes the
    `preserve_patterns` bypass (a developer pattern such as `.*MUST.*` matching
    attacker RAG text cannot force retention).
- **`_is_must_keep`:**
  - Trusted/`USER`: legacy behavior (code span, `_CRITICAL_RE`, or preserve match → True).
  - Untrusted roles: always `False`. Untrusted content never becomes `must_keep`,
    so it can never bypass the budget. (Code spans in RAG are still protected from
    *tokenization* corruption via §5.3; that is independent of must_keep.)
- **Rationale:** provenance boundary enforced at the single choke point where
  priority and must_keep are decided. Default `"general"` keeps all existing tests
  passing unchanged.

### 5.2 `llmslim/core.py`
1. Define and export `ContextRole`.
2. Accept `context_role` in `__init__` and `compress()`.
3. Resolve effective role once, with this precedence:
   1. explicit `context_role` argument (string or enum),
   2. else instance `self.context_role` if not `GENERAL`,
   3. else infer from `mode` (`"rag"` → RAG, `"system"` → SYSTEM),
   4. else `GENERAL`.
4. Pass the resolved role to `score_chunk_sentences()`.
5. Add `token_counter_used` to `CompressionResult` and populate it from
   `get_active_token_counter_name()` at result construction (§5.4). Applies to the
   extractive, passthrough, structured, and rewrite result paths.
6. **Delete** `_select_for_chunk()`, `_knapsack_select()`, `_greedy_select()` and
   the `_DP_TABLE_LIMIT` constant.

### 5.3 `llmslim/tokenization.py`
1. Add inline code protection. Extend code protection so both fenced blocks and
   inline spans are replaced with placeholders before splitting and restored after:
   - fenced: existing `` ```...``` `` (DOTALL),
   - inline: `` `[^`\n]+` ``.
   Use distinct placeholder namespaces (`\x00BLOCK{n}\x00`, `\x00INLINE{n}\x00`) so
   restoration is unambiguous. `_STRUCTURAL_LINE_RE` must also treat `\x00INLINE`
   like `\x00BLOCK` (kept intact).
2. Add CJK sentence boundaries. Split after `。`/`！`/`？` (no trailing space
   required) while preserving existing Western behavior. New regex splits on either
   `[.!?]` + whitespace + Western-start, **or** immediately after `[。！？]`.
   NLTK path (when punkt is present) is used first as today; the regex path is the
   fallback and the CJK-capable one. Because NLTK does not reliably split
   no-space CJK, we post-process NLTK output through the CJK splitter so CJK works
   regardless of whether punkt is installed.

### 5.4 `llmslim/tokens.py`
1. Add `get_active_token_counter_name() -> str` returning `"tiktoken"` when the
   encoder loaded, else `"heuristic"`.
2. Emit `logging.getLogger("llmslim").warning(...)` **once per process** on first
   heuristic fallback.
- **`token_counter_used` semantics (clarification):** the value reflects the
  process-level active tokenizer resolved at the moment the result is built. The
  encoder is a cached singleton, so in practice it is stable across a run. A rare
  per-call `encode()` failure that falls back for one specific string is not
  separately flagged; this limitation is documented in the code and report. We do
  not fabricate per-call telemetry we cannot accurately measure.

### 5.5 `llmslim/rewrite/templates.py` (structurally safe, content-preserving)
- **Do not mutate user content.** Instead of replacing delimiter text with
  zero-width characters, detect a potential fence collision (user text contains a
  `---BEGIN`/`---END`-style token) and, when detected, rewrite the *template's* own
  fence markers to carry a random per-call nonce, e.g.
  `---BEGIN TEXT «llmslim:9f3a2c»---` / `---END TEXT «llmslim:9f3a2c»---`.
- The user's literal `---END TEXT---` then cannot match the actual (nonce-tagged)
  terminator, so it cannot close the region. **User content is preserved
  byte-for-byte.**
- When no collision is present, output is unchanged from v0.3.0 (common case).
- Round-trip tests assert the original text is recoverable/verbatim and that a bare
  `---END TEXT---` no longer functions as the terminator.

### 5.6 `llmslim/pipelines.py`
- `compress_documents()` passes `context_role` (default `ContextRole.RAG`).
- `compress_chat_messages()` maps each message role explicitly (no silent collapse):
  - `system` → `SYSTEM`
  - `developer` → `DEVELOPER`
  - `user` → `USER`
  - `assistant` → `ASSISTANT`
  - `tool` → `TOOL`
  - unknown/other → `GENERAL`
  and passes the mapped role to `compress()` for each compressed turn. System
  prompts remain uncompressed by default (`DEFAULT_COMPRESSIBLE_ROLES` unchanged).

### 5.7 `benchmarks/benchmark.py`
- Replace the hardcoded return with a real result collector:
  - Register a small plugin capturing `pytest_runtest_logreport` outcomes (or read
    the `TestReport` via a session hook) to count passed/failed/errored tests.
  - Invoke `pytest.main(["-q", "tests", "-o", "addopts=", "--no-cov"], plugins=[collector])`
    so the in-process run does not inherit the coverage gate (which is enforced
    separately by the real `pytest` CI run, not weakened).
  - Return the collector's real `(passed, failed)`.
- Coverage enforcement in `pyproject.toml` is untouched; only the benchmark's
  in-process convenience run skips the coverage gate for accurate counting.

---

## 6. Test Plan

New tests live in `tests/test_security_rag.py` (provenance/security),
`tests/test_tokenization_phase1.py` (inline code + CJK), and additions to
`tests/test_templates.py` (fence), `tests/test_pipeline.py` (behavioral changes),
plus `tests/test_core.py` updates for dead-code removal and `token_counter_used`.

Mandatory coverage:
- RAG imperative sentence does **not** receive Priority 4 (and is not `must_keep`).
- Trusted `system` instruction retains Priority 4 / `must_keep`.
- Mixed: trusted system + untrusted RAG — system retained, RAG cannot evict it.
- Mixed: trusted system + untrusted tool output.
- Multiple RAG documents, each with injected directives.
- Multiple malicious RAG directives cannot consume the protected budget.
- Attacker-controlled `preserve_patterns` value cannot elevate RAG content.
- RAG content with **legitimate** imperative language competes on score (not hard-locked).
- Tool output containing fake `SYSTEM:` / `DEVELOPER:` markers is not elevated.
- `compress_documents()` default RAG provenance (behavioral change) — regression test.
- `compress_chat_messages()` role propagation (behavioral change) — regression test,
  including explicit `assistant` and `tool` handling.
- Inline code span periods do not split sentences (single/multiple spans,
  punctuation inside spans, fenced blocks, multiline, malformed backticks, normal prose).
- CJK splitting (`。`/`！`/`？`) for Chinese, Japanese, mixed EN/CJK, no-space CJK,
  punctuation adjacent to quotes/brackets — while `.`/`!`/`?` still work.
- Template fence breakout impossible; ordinary text unchanged; multiple occurrences;
  BEGIN/END-like text; round-trip preservation.
- `mode="system"` trust-boundary documentation test.
- Token fallback warning emitted; `token_counter_used` populated correctly.
- Benchmark runner reports accurate counts.

Run the full existing suite (389 tests) before and after.

---

## 7. Attack Matrix

| # | Vector | v0.3.0 | v0.3.1 target | Test |
|---|--------|--------|---------------|------|
| 1 | RAG `MUST` directive | Priority 4, force-kept | ≤ Tier 2, competes on score | `test_rag_injection_must_not_priority_4` |
| 2 | RAG `NEVER`/`SYSTEM:` markers | Priority 4 | ≤ Tier 2 | `test_rag_fake_markers_not_elevated` |
| 3 | RAG legitimate imperative fact | Priority 4 indiscriminate | scored, not hard-locked | `test_rag_legitimate_imperative_competes` |
| 4 | Trusted system `You MUST return JSON` | Priority 4 | Priority 4 (trusted) | `test_trusted_system_retains_priority_4` |
| 5 | System + RAG mixed | RAG evicts system | system retained, RAG pruned | `test_mixed_system_and_rag_isolation` |
| 6 | System + TOOL mixed | tool elevated | tool ≤ Tier 2 | `test_mixed_system_and_tool_isolation` |
| 7 | Multi-sentence RAG stuffing | consumes budget | evicted under budget | `test_multi_rag_directive_eviction` |
| 8 | Attacker-influenced `preserve_patterns` | Priority 4 | not elevated in RAG | `test_attacker_preserve_patterns_no_elevation` |
| 9 | Multiple RAG docs | each amplified | each capped | `test_multiple_rag_documents_capped` |
| 10 | Inline code period | split | single sentence | `test_inline_code_span_not_split` |
| 11 | CJK full stop | not split | split on `。` | `test_cjk_full_stop_splitting` |
| 12 | Template `---END TEXT---` | breakout | nonce fence, content verbatim | `test_rewrite_template_fence_breakout` |

---

## 8. Backward Compatibility & Intentional Behavioral Changes

### Preserved
- `compress(text, ...)` with no `context_role`/`mode` → `GENERAL` → identical to
  v0.3.0 (verified by `test_v02_regression.py` / `test_v03_regression.py`).
- All new parameters optional; no signatures reordered; `CompressionResult` gains
  one field (`token_counter_used`) with a default.

### Intentional behavioral changes (NOT "100% backward compatible")
1. **`compress_documents()` now defaults to `context_role=ContextRole.RAG`.**
   Effect: imperative sentences in retrieved documents are no longer force-kept via
   Priority 4. This changes which sentences may be selected for document inputs.
   This is a deliberate security fix. Covered by
   `test_compress_documents_default_rag_provenance`.
2. **`compress_chat_messages()` now propagates per-message role provenance.**
   Effect: `assistant`/`tool`/`user` turns are compressed under their own
   provenance rather than `GENERAL`, so imperative wording in those turns is no
   longer hard-locked. Covered by `test_chat_messages_role_propagation`.

Both changes are called out in `CHANGELOG.md`.

---

## 9. Coverage Strategy

- Keep `--cov-fail-under=90` in `pyproject.toml` (unchanged; not weakened).
- Dead-code removal reduces statement count; new code and tests add statements.
- **No numeric coverage prediction is made.** The report will state only the
  measured coverage after implementation.

---

## 10. Acceptance Criteria

1. All **389** existing tests pass (0 failures).
2. All new Phase 1 security/correctness tests pass.
3. Coverage ≥ 90% (measured; exact figure reported post-implementation).
4. `python benchmark.py` reports the real pass/fail counts (no false 5-failure).
5. RAG/TOOL/ASSISTANT content cannot reach Priority 4 from wording or
   `preserve_patterns`.
6. Trusted `system`/`developer` instructions retain Priority 4.
7. Inline code and CJK segmentation correct.
8. Template fence breakout prevented with content preserved verbatim.
9. Token fallback transparent (`token_counter_used` + one-time warning).
10. No changes to frozen files (`web/*`, `optimizers/*`, `cost.py`†, `pyproject.toml`).

† `llmslim/cost.py` already contains **pre-existing uncommitted user changes** in the
working tree (pricing table refresh). Those are the user's and are out of Phase 1
scope; Phase 1 will not touch `cost.py`. The final `git diff --name-only` review
distinguishes Phase 1 edits from these pre-existing user edits.

---

## 11. Rollback Risk & Mitigation

- **Risk:** sentence-splitting changes alter sentence counts for existing prompts.
  **Mitigation:** default `GENERAL` path unchanged; regression suite + determinism
  tests must stay green.
- **Risk:** provenance capping over-prunes legitimate RAG imperatives.
  **Mitigation:** untrusted content still competes on score/query relevance; only
  the *hard-lock* is removed.
- **Rollback:** all changes localized to the permitted Python files; revert via git.

---

## 12. Release Checklist

- [ ] `git diff --name-only` shows only permitted Phase 1 files (plus the pre-existing
      user edits noted in §10).
- [ ] `pytest tests` → **389** existing + newly added tests, 0 failures.
- [ ] `python benchmark.py` reports real counts, 0 false failures.
- [ ] `CHANGELOG.md` updated with security notes and the two behavioral changes.
- [ ] Do **not** bump version / tag / publish in this phase.

---

## 13. Security Limitation Statement

This change **mitigates LLMSlim's compression-induced instruction elevation** — the
specific defect where the compressor amplified untrusted RAG/tool content by
force-retaining imperative sentences at the expense of authentic context. It is
**not** a complete prompt-injection defense. Per OWASP LLM01, there is **no
foolproof prevention** for prompt injection; provenance-aware prioritization is one
layer of a **defense-in-depth** strategy. In particular:

- LLMSlim trusts caller-supplied role labels and cannot authenticate provenance (§3.3).
- Untrusted content may still be *retained* (it competes on relevance); it simply
  can no longer *hijack the protected budget*.
- Downstream systems must still apply their own input isolation, output filtering,
  privilege limitation, and human-in-the-loop controls.

---

**END OF IMPLEMENTATION PLAN (revised)**
