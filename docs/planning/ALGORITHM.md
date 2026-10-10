# Adaptive planning algorithm

## Objective

For every logical item `i`, choose exactly one safe candidate `j` to maximize
total utility under the available input-token budget:

```text
maximize  Σ utility(i, j)
subject to Σ token_cost(i, j) <= available_input_tokens
           one candidate selected per item
           required/trusted/tool-contract constraints hold
```

This is a deterministic multiple-choice knapsack problem, not a global
score-and-delete loop. The implementation maintains a Pareto frontier of cost
and utility states with stable tie-breaking. Costs are integer token estimates
and are never rounded down.

## Scoring

Scores combine documented signals: role/trust, required status, caller
priority, recency, lexical query relevance, content kind, instruction density
and entity density. Preset policies change the weights and allowed methods,
not the algorithm:

- `balanced`: general-purpose quality, safety and reduction.
- `quality_first`: retains more raw context and penalizes risk strongly.
- `cost_first`: permits more aggressive safe compression and dropping.
- `latency_first`: avoids provider rewrites and favors cheap local choices.

Caller-supplied priority is only a utility hint. It cannot override provenance
or make an unsafe candidate legal.

Instruction density counts as value only for caller-authored roles (system,
developer, user and general messages). Imperative wording in RAG documents, memories, tool
results or assistant turns never raises their value, because in untrusted
content it is at best neutral and at worst an indirect prompt-injection
payload. Such content keeps its fixed untrusted provenance either way.

### Superseded evidence

Retrieved evidence (RAG documents, memories, tool results) is treated as
superseded when its caller metadata contains any of:

- `superseded`: truthy (`True`, a non-zero number, or `"true"`/`"yes"`/`"1"`);
- `superseded_by`: any non-empty value, such as the replacing document ID;
- `valid_until`: an ISO-8601 timestamp or date at or before the current UTC
  time (naive values are read as UTC; unparseable values are ignored with a
  plan warning).

A superseded item's value is multiplied by `SUPERSEDED_VALUE_FACTOR` (0.05).
It is still kept when the budget allows, but it is the first optional
evidence to be dropped under budget pressure, and the plan carries a warning
naming it. `created_at` alone is not interpreted for documents: age is not the
same as being replaced. The v0.7 progressive planner (`ContextRuntime`) may
drop a superseded, non-required item regardless of its lexical relevance.

### Relevance guard

Item value has a relevance-independent baseline (provenance, kind, priority),
so a pure value-sum knapsack can prefer two small, weakly relevant documents
over one larger, clearly more relevant one. After the knapsack, the planner
applies one deterministic guard: let `top` be the droppable, non-superseded
evidence item with the highest relevance (first in input order on ties). If
the allocation drops `top` while keeping evidence of strictly lower relevance
or superseded evidence, `top` and that lower evidence are re-solved with `top`
required to keep a non-drop representation, and every other item keeps its
original choice. The constrained result is used only if it is feasible;
otherwise the original allocation stands. The kept item's decision reason
says that the relevance guard applied.

## Candidates and fallback

- `RAW`: exact caller content in a provenance boundary.
- `EXTRACTIVE_COMPRESSED`: deterministic existing LLMSlim compression,
  validated before selection.
- `REWRITE_COMPRESSED` and `HYBRID_COMPRESSED`: generated only when a provider
  is explicitly supplied and retained only after rewrite validation.
- `DROP`: generated only for non-required content allowed by policy. Tool
  schemas require explicit experimental selective-tool policy.

After allocation the planner validates final serialized size, required and
trusted content, stable order, structure, and tool fingerprints. It replaces a
failed transformed candidate with the safest fitting alternative. If mandatory
context itself exceeds the budget, the result is explicitly `INFEASIBLE`;
trusted instructions are never silently truncated. Callers can request a typed
`InfeasibleContextError`.

## Complexity and limitations

The Pareto-frontier dynamic program is exact over the retained frontier, but
frontier size grows with candidate costs. Candidate counts are deliberately
small and bounded. Default relevance is lexical and multilingual-token aware;
applications needing semantic retrieval should retrieve candidates upstream.
Estimated token counts depend on the active LLMSlim token counter and can
differ from provider billing.

The relevance guard protects only the single most relevant optional evidence
item. Below it, the knapsack still maximizes total value, so leftover budget
can be filled with weakly relevant documents (or be used to keep a compressed
rather than raw form of the protected item). Callers who need a relevance
floor should filter retrieved candidates upstream or use `ContextPolicy`
source rules.

LLMSlim does not detect prompt injection. It removes the value bonus that
imperative wording would otherwise give untrusted content and keeps such
content inside an untrusted provenance boundary, but an injection attempt that
is lexically relevant to the query can still be selected when the budget
allows. Lexical relevance is not penalized for imperative phrasing because
any such pattern list is easy to evade and would also penalize legitimate
procedural documents.
