# Tool relevance and selective exposure

`rank_tools()` is an offline deterministic TF-IDF/cosine baseline over existing
tool name, namespace, title, description, property names, and property
descriptions. It requires no API key, model download, or hidden reasoning. Each
rank includes its numeric score and observed lexical overlap.

`select_tools()` and `plan_tool_context()` are **experimental**. They never
mutate the authoritative executor schema. Conservative mode exposes the entire
catalog for blank/weak signals, small catalogs, and close top scores. A no-tool
result requires a clear informational query and no meaningful non-stopword
overlap with any available capability; this prevents question phrasing such as
"What is the weather?" from suppressing a weather tool.

`ToolContextPlan` includes the exact existing compact index fields and
deep-copied full schemas for selected IDs. No summary is generated. The
experimental `LazyToolRegistry` serves complete copied raw schemas by stable
identity and fingerprint; it is not a protocol middleware or executor.

The go/no-go thresholds are declared before benchmark execution: Recall@5 at
least 0.95 and no-tool accuracy 1.0 on the repository-owned relevance fixture.
The benchmark report states whether the current curated corpus meets them; it
does not establish production task success.
