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
