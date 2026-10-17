# LangChain

`LLMSlimCompressor` is a LangChain `BaseDocumentCompressor`. Use it where you
would use `LLMLinguaCompressor`: as the `base_compressor` of a
`ContextualCompressionRetriever`, or as one step of a
`DocumentCompressorPipeline`. It runs locally with no model and no API call.

```bash
pip install "llmslim[langchain]"   # langchain-core; needs llmslim 0.8.1 or newer
pip install langchain-classic      # for ContextualCompressionRetriever (LangChain 1.x)
```

`ContextualCompressionRetriever` lives in
`langchain_classic.retrievers.contextual_compression` in LangChain 1.x and in
`langchain.retrievers.contextual_compression` in LangChain 0.3.

## Example

```python
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from llmslim.integrations.langchain import LLMSlimCompressor

docs = [
    Document(
        page_content="Standard shipping takes three to seven business days within the country. "
        "Express shipping arrives in one or two business days and costs fifteen dollars. "
        "We ship to forty countries, and international orders clear customs in about a week. "
        "Tracking numbers are emailed as soon as the parcel leaves the warehouse.",
        metadata={"source": "shipping.md"},
    ),
    Document(
        page_content="You can return any item within 30 days of delivery for a full refund. "
        "Refunds go back to the original payment method within five business days. "
        "Items must be unused and in their original packaging. "
        "Gift cards and final-sale items cannot be returned.",
        metadata={"source": "refunds.md"},
    ),
    Document(
        page_content="The company was founded in 2015 by two engineers in Pune. "
        "Our team of eighty people works across design, engineering and support. "
        "The office has a rooftop garden and a small library of design books. "
        "Every Friday afternoon the team hosts an open demo for customers.",
        metadata={"source": "about.md"},
    ),
]

# Any retriever works here. The fake embedding keeps the example offline.
vectorstore = InMemoryVectorStore.from_documents(docs, DeterministicFakeEmbedding(size=256))
retriever = ContextualCompressionRetriever(
    base_compressor=LLMSlimCompressor(target_ratio=0.25),
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
)

for doc in retriever.invoke("How many days do I have to return an item for a refund?"):
    print(doc.metadata)
    print(doc.page_content)
```

Output (Python 3.12, langchain-core 1.6.9, langchain-classic 1.0.8, token
counts from tiktoken):

```text
{'source': 'refunds.md', 'llmslim_original_tokens': 50, 'llmslim_compressed_tokens': 40}
You can return any item within 30 days of delivery for a full refund. Refunds go back to the original payment method within five business days. Items must be unused and in their original packaging.
```

The three documents share one budget of 25% of their 158 tokens (40 tokens).
The shipping and company pages do not answer the question and are dropped; the
refund page keeps the answer and loses its sentence about gift cards.

## What it does

`compress_documents(documents, query)` calls `llmslim.compress_documents` on the
documents' `page_content`:

- With a query, the documents share one budget (`target_ratio` of their
  combined tokens) and it goes where the query points: the most relevant
  documents stay whole and irrelevant ones are dropped.
- Without a query (an empty string), each document is compressed to
  `target_ratio` on its own.
- Kept documents keep their order, `id` and metadata. Documents that are empty
  or compress to nothing are dropped. The input documents are not modified.

## Options

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `target_ratio` | `0.25` | Fraction of tokens to keep. |
| `relevance` | `"lexical"` | `"lexical"` (BM25, no model), `"semantic"` (cross-encoder, needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `selection` | `"auto"` | `"proportional"` gives each document its own share, as in 0.7. |
| `context_role` | `"rag"` | Retrieved text is untrusted: imperative wording in it is never force-kept. |
| `record_token_counts` | `True` | Adds `llmslim_original_tokens` and `llmslim_compressed_tokens` to the metadata. |
| `additional_compress_kwargs` | `{}` | Other `llmslim.compress_documents` arguments, for example `mode`. |

## Agents: shorten long tool output (LangChain 1.x)

`LLMSlimToolOutputMiddleware` is middleware for `create_agent`, in llmslim 0.11.0 or newer. It needs `pip install "llmslim[langchain-agents]"`
(Python 3.10+).

How it works:
- It shortens a long tool result once, the first time the model is about to see it.
- It writes the shorter text back into the agent's state under the same message id, so every later model call sends
  exactly those bytes.
- It keeps errors, failures and tracebacks first, then the lines most related to the call. Runs of similar lines
  collapse into one line and a count, and a note tells the model the output was shortened. No model is called.

```python
from langchain.agents import create_agent
from llmslim.integrations.langchain_agents import LLMSlimToolOutputMiddleware

agent = create_agent(
    "anthropic:claude-haiku-5-5",
    tools=[run_tests, search_logs, read_file],
    middleware=[LLMSlimToolOutputMiddleware(never={"read_file"})],  # keep file contents exact
)
```

**Why it beats clearing old results.** LangChain's `ContextEditingMiddleware` replaces old tool results with
`[cleared]`. That throws away the content, and it changes the prompt prefix each time it clears, so the provider's
prompt cache misses. Here nothing the model has already seen ever changes:
- caches keep hitting;
- Claude's thinking stays valid. Thinking is bound to everything before it, and editing earlier turns gets the
  request rejected.

**Measured** with Claude Haiku 5.5, adaptive thinking and `langchain-anthropic` 1.7.6:
- A 7,545-token pytest log reached the model as 160 tokens.
- The answer named the failing test and its assertion.
- A second turn on the same thread, with thinking in the history, answered correctly with no error.

| Option | Default | Meaning |
|---|---|---|
| `min_tokens` | 1500 | Leave results at or below this many tokens alone. |
| `keep_ratio` | 0.35 | Fraction of a long result's tokens to keep. |
| `min_keep` | 1000 | Never shorten a result below this many tokens. |
| `only` | every tool | Shorten only these tools' results. |
| `never` | none | Never shorten these tools' results, e.g. ones that return file contents to edit. |
| `compress_json` | `False` | Also shorten JSON results (llmslim 0.11.1 or newer; before that, JSON was always shortened). Off by default: in our Claude Code benchmark, an agent given a shortened JSON list spent extra turns fetching the fields that were cut. |

**Never touched:**
- JSON results, unless `compress_json=True`;
- results the model has already seen;
- results with images or files;
- results at or below `min_tokens`.

Each shortened message records `tokens_before` and `tokens_after` in `response_metadata["llmslim"]`.

