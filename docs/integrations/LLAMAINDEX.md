# LlamaIndex

`LLMSlimPostprocessor` is a LlamaIndex `BaseNodePostprocessor`. Use it where you
would use `LongLLMLinguaPostprocessor`: in a query engine's
`node_postprocessors`, or on its own with `postprocess_nodes()`. It runs locally
with no model and no API call.

```bash
pip install "llmslim[llamaindex]"   # llama-index-core; Python 3.10+; needs llmslim 0.8.1 or newer
```

The extra needs Python 3.10 or newer: llama-index-core dropped Python 3.9 in
0.14.17, and its last 3.9 release does not import on 3.9 (its `banks`
dependency uses 3.10 syntax).

## Example

```python
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.llms import MockLLM

from llmslim.integrations.llama_index import LLMSlimPostprocessor

documents = [
    Document(
        text="Standard shipping takes three to seven business days within the country. "
        "Express shipping arrives in one or two business days and costs fifteen dollars. "
        "We ship to forty countries, and international orders clear customs in about a week. "
        "Tracking numbers are emailed as soon as the parcel leaves the warehouse.",
        metadata={"source": "shipping.md"},
    ),
    Document(
        text="You can return any item within 30 days of delivery for a full refund. "
        "Refunds go back to the original payment method within five business days. "
        "Items must be unused and in their original packaging. "
        "Gift cards and final-sale items cannot be returned.",
        metadata={"source": "refunds.md"},
    ),
    Document(
        text="The company was founded in 2015 by two engineers in Pune. "
        "Our team of eighty people works across design, engineering and support. "
        "The office has a rooftop garden and a small library of design books. "
        "Every Friday afternoon the team hosts an open demo for customers.",
        metadata={"source": "about.md"},
    ),
]

# MockEmbedding and MockLLM keep the example offline; use your own models.
index = VectorStoreIndex.from_documents(documents, embed_model=MockEmbedding(embed_dim=8))
query_engine = index.as_query_engine(
    llm=MockLLM(),
    similarity_top_k=3,
    node_postprocessors=[LLMSlimPostprocessor(target_ratio=0.25)],
)

response = query_engine.query("How many days do I have to return an item for a refund?")
for item in response.source_nodes:
    print(round(item.score, 3), item.node.metadata)
    print(item.node.get_content())
```

Output (Python 3.12, llama-index-core 0.14.25, token counts from tiktoken):

```text
1.0 {'source': 'refunds.md', 'llmslim_original_tokens': 50, 'llmslim_compressed_tokens': 40}
You can return any item within 30 days of delivery for a full refund. Refunds go back to the original payment method within five business days. Items must be unused and in their original packaging.
```

The three retrieved nodes share one budget of 25% of their 158 tokens (40
tokens). The shipping and company nodes do not answer the question and are
dropped; the refund node keeps the answer and loses its sentence about gift
cards. The score is the retriever's (the mock embedding scores every node 1.0).

## What it does

`_postprocess_nodes(nodes, query_bundle)` calls `llmslim.compress_documents` on
the nodes' text (without metadata):

- With a query, the nodes share one budget (`target_ratio` of their combined
  tokens) and it goes where the query points: the most relevant nodes stay
  whole and irrelevant ones are dropped.
- Without a query, each node is compressed to `target_ratio` on its own.
- Kept nodes keep their order, score, `node_id` and metadata. Nodes that are
  empty or compress to nothing are dropped. The input nodes are not modified.
- The token counts added to the metadata are listed in
  `excluded_llm_metadata_keys` and `excluded_embed_metadata_keys`, so they never
  reach the LLM prompt or the embedder.

## Options

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `target_ratio` | `0.25` | Fraction of tokens to keep. |
| `relevance` | `"lexical"` | `"lexical"` (BM25, no model), `"semantic"` (cross-encoder, needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `selection` | `"auto"` | `"proportional"` gives each node its own share, as in 0.7. |
| `context_role` | `"rag"` | Retrieved text is untrusted: imperative wording in it is never force-kept. |
| `record_token_counts` | `True` | Adds `llmslim_original_tokens` and `llmslim_compressed_tokens` to the metadata. |
| `additional_compress_kwargs` | `{}` | Other `llmslim.compress_documents` arguments, for example `mode`. |
