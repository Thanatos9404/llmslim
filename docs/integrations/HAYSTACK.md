# Haystack

`LLMSlimDocumentCompressor` is a Haystack 2.x `@component` that also works with
Haystack 3. Put it between a retriever and the prompt builder: it takes
`documents` and an optional `query` and returns `{"documents": [...]}`. It runs
locally with no model and no API call.

```bash
pip install "llmslim[haystack]"   # haystack-ai; needs llmslim newer than 0.8.0
```

## Example

```python
from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from llmslim.integrations.haystack import LLMSlimDocumentCompressor

store = InMemoryDocumentStore()
store.write_documents(
    [
        Document(
            content="Standard shipping takes three to seven business days within the country. "
            "Express shipping arrives in one or two business days and costs fifteen dollars. "
            "We ship to forty countries, and international orders clear customs in about a week. "
            "Tracking numbers are emailed as soon as the parcel leaves the warehouse.",
            meta={"source": "shipping.md"},
        ),
        Document(
            content="You can return any item within 30 days of delivery for a full refund. "
            "Refunds go back to the original payment method within five business days. "
            "Items must be unused and in their original packaging. "
            "Gift cards and final-sale items cannot be returned.",
            meta={"source": "refunds.md"},
        ),
        Document(
            content="The company was founded in 2015 by two engineers in Pune. "
            "Our team of eighty people works across design, engineering and support. "
            "The office has a rooftop garden and a small library of design books. "
            "Every Friday afternoon the team hosts an open demo for customers.",
            meta={"source": "about.md"},
        ),
    ]
)

pipeline = Pipeline()
pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=store, top_k=3))
pipeline.add_component("compressor", LLMSlimDocumentCompressor(target_ratio=0.25))
pipeline.connect("retriever.documents", "compressor.documents")

query = "How many days do I have to return an item for a refund?"
result = pipeline.run({"retriever": {"query": query}, "compressor": {"query": query}})
for doc in result["compressor"]["documents"]:
    print(round(doc.score, 3), doc.meta)
    print(doc.content)
```

Output (Python 3.12, haystack-ai 3.3.0, token counts from tiktoken):

```text
5.838 {'source': 'refunds.md', 'llmslim_original_tokens': 50, 'llmslim_compressed_tokens': 40}
You can return any item within 30 days of delivery for a full refund. Refunds go back to the original payment method within five business days. Items must be unused and in their original packaging.
```

The three retrieved documents share one budget of 25% of their 158 tokens (40
tokens). The shipping and company pages do not answer the question and are
dropped; the refund page keeps the answer and loses its sentence about gift
cards. The score is the BM25 retriever's.

To compress before a prompt builder, connect
`"compressor.documents"` to `"prompt_builder.documents"`.

## What it does

`run(documents, query=None)` calls `llmslim.compress_documents` on the
documents' `content`:

- With a query, the documents share one budget (`target_ratio` of their
  combined tokens) and it goes where the query points: the most relevant
  documents stay whole and irrelevant ones are dropped.
- Without a query, each document is compressed to `target_ratio` on its own.
- Kept documents keep their order, `id`, `score` and `meta`. Documents without
  text, or that compress to nothing, are dropped. The input documents are not
  modified.

The component serializes with `pipeline.dumps()` unless `relevance` is a
callable. Haystack 3 loads classes only from allowlisted modules:
`Pipeline.loads(yaml_text, allowed_modules=["llmslim.integrations.haystack"])`.

## Options

| Argument | Default | Meaning |
| :--- | :--- | :--- |
| `target_ratio` | `0.25` | Fraction of tokens to keep. |
| `relevance` | `"lexical"` | `"lexical"` (BM25, no model), `"semantic"` (cross-encoder, needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `selection` | `"auto"` | `"proportional"` gives each document its own share, as in 0.7. |
| `context_role` | `"rag"` | Retrieved text is untrusted: imperative wording in it is never force-kept. |
| `record_token_counts` | `True` | Adds `llmslim_original_tokens` and `llmslim_compressed_tokens` to `meta`. |
| `additional_compress_kwargs` | `{}` | Other `llmslim.compress_documents` arguments, for example `mode`. |
