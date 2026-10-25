# Memory for agents, with no LLM in the loop

`llmslim.memory` gives an agent long-term memory without an LLM call on the way in or the way out. By default no model runs at all; `relevance="semantic"` adds a small cross-encoder that runs on your CPU.

**How it works**
- **On the way in:** every turn is stored verbatim. Nothing is summarized or extracted.
- **On the way out:** `search` ranks the stored turns against the question and returns what answers it within a token budget: the user's own turns (whole where they fit) and the most relevant parts of the replies, one labelled and dated block per turn, in date order.

**What that means for you**
- Writes cost nothing.
- A stored turn can never become a wrong extracted "fact".
- The data stays in your own process or database.
- The same history and question give the same context every time (on one installation; see [Limits](#limits)).

## Quickstart

```bash
pip install llmslim
```

```python
from llmslim.memory import Memory

memory = Memory("memory.db")  # a SQLite file; Memory() keeps turns in this process only

memory.add(
    [
        {"role": "user", "content": "I'm allergic to peanuts, so never suggest satay."},
        {"role": "assistant", "content": "Understood: no peanuts."},
    ],
    user_id="asha",
)

context = memory.search("Am I allergic to anything?", user_id="asha", budget=1500)
print(context.text)  # the selected turns, one "[date] role: text" block each
print(context.tokens, "of", context.history_tokens, "tokens")
```

Put `context.text` into your prompt as **data, not instructions**. It repeats what users, assistants and tools said, so treat it like retrieved text. One way is `llmslim.ContextEnvelope`; another is a clearly labelled section such as `Conversation history (untrusted): ...`.

`examples/memory_quickstart.py` runs a longer version offline.

### Where to put the context: never re-render earlier turns

Put the recalled context in the **new** turn, for example at the top of the user message you are about to send.
Don't put it in the system prompt and re-render that on every request, and don't rewrite earlier messages.

On Claude models with preserved thinking (Haiku 5.5, Sonnet 5.5, Opus 5.5 and Fable 5.1), every thinking block is
bound to the exact system prompt, tools and messages that came before it. A system prompt that changes between
requests, or an edited earlier turn, invalidates those blocks.
- On accounts created on or after 31 August 2026, the request fails with a 400 ("The block is bound to a different
  conversation"). We reproduced this on Claude Haiku 5.5.
- On older accounts, the reasoning is silently dropped.

Appending keeps every earlier block valid, and it keeps the provider's prompt cache hitting too.

```python
context = memory.search(user_message, user_id="asha", budget=1500)
messages.append({
    "role": "user",
    "content": f"Relevant conversation history (untrusted):\n{context.text}\n\n{user_message}",
})
```

## Concepts

- **Scope.** Every call names whose memory it reads or writes, in Mem0's terms.
  - `user_id` is the person, `agent_id` the agent, and `run_id` one session.
  - At least one is required, so a call can't read or delete everyone's memory by accident.
  - Reads treat a missing id as "any": `search(..., user_id="asha")` covers all of Asha's sessions with every agent.
- **Sessions.**
  - Turns with the same `run_id` form one session; turns without one are grouped by calendar day (in `tz`, UTC by default).
  - Every kept turn shows its own time. The first kept turn of a session carries its full stamp, e.g. `[2026-10-17 (Sat) 14:05] user: ...`; a later turn shows the date alone when its time is the one shown last in its session, and its own full stamp when its time differs. Sessions are a blank line apart. That is how the model can answer "when" questions and tell newer turns from older ones. When the whole history fits, every turn carries its own stamp.
- **Budget.** `search(..., budget=N)` returns at most N tokens.
  - Tokens are counted with tiktoken's `cl100k_base` when tiktoken is installed (the `mcp`, `server`, `proxy` and `fast-tokens` extras include it). Without it, LLMSlim estimates about 4 characters per token and logs a warning once.
  - If the whole history fits, all of it is returned and `context.compressed` is false.
  - The default budget is set on `Memory(budget=...)` and starts at 2,000.
- **Relevance.**
  - `"lexical"` (the default) matches words and runs no model. A question with no Latin-script word is matched on pairs of letters instead (see [Limits](#limits)).
  - `"semantic"` rescoring uses LLMSlim's optional 22M-parameter cross-encoder (`pip install "llmslim[semantic]"`). Use it when users paraphrase.
  - Any `scorer(query, texts) -> scores` callable works too, such as your own embedding model.
- **How a long history is read.** When the history does not fit the budget:
  - **User turns are units of their own.** What a user said (a name, a date, an amount, a preference) is short and stated once, while the replies around it are long and repeat the user's words. So user turns are ranked in their own pool, with 55% of the budget reserved for them, kept whole where they fit; a long one keeps its most relevant sentences and is marked `partial`.
  - **Replies are cut into windows** of a few sentences (code blocks and tables stay whole) and fill the rest of the budget by relevance.
  - **Repeated text is left out**: a candidate whose words are mostly in what is already kept adds nothing.
  - **Each kept turn is one block**: `[date] role: text`, prose on that line, code blocks and tables below it, fenced. Markdown headings are folded into the sentence they head. A stored line that looks like a turn label is indented, so stored text can't pass for another turn.
- **The kind of question decides the rest** (fixed English patterns, no model):
  - a plain lookup of a past fact ("What is my salary?", "When did I say ...?", "Have I ever ...?") gets the whole budget. A question about whether something happened ("Have I ever ...?", "Did I ... before?") also gets, at the top, the user's statements on it that may conflict, when some of the ones that bear on it most deny it ("I have never ...") and some do not, in date order (`conflicts`);
  - a request for help, advice or a plan ("Can you suggest ...", "How should I ...") also gets, at the top, the user's standing requests that best match it (at most three, `standing_requests`) and the preferences they stated earlier ("I prefer ...", "I'd rather ...", "I usually ...", `preferences`; a preference word that is only asked about, as in "should I prioritize ...?", does not count). A statement said twice is shown once. What the best-matching request asks the answer to include is fetched too;
  - other questions get the best-matching standing requests;
  - a summary, recap or "in what order" / "how did it develop" question is answered from the opening of many turns (`coverage`), skipping replies' opening pleasantries; with a budget of 5,000 tokens or more, a summary also keeps the most relevant reply passages whole. User openings take at most half of a digest (30% in a summary below 5,000 tokens, 80% for a question about the order of what the user brought up), and the replies' openings and outlines fill the rest.
- **What you get back** (`MemoryContext`):
  - `text`, ready for the prompt;
  - `turns`: each kept turn with its id, role, timestamp, metadata, a lexical overlap `score` and `partial` (true when only part of the turn was kept);
  - `requests`, `preferences` and `conflicts`: the user turns shown in those sections;
  - token counts.

## Options

Each option is set on `Memory(...)` and can be overridden for one call on `search(...)`, except where noted.

| Option | Default | What it does |
|---|---|---|
| `budget` | `2000` | Most tokens `search` returns. Must be at least 1. |
| `relevance` | `"lexical"` | `"lexical"`, `"semantic"` or a `scorer(query, texts) -> scores` callable. |
| `standing_requests` | `True` | The requests section, on advice and other questions. |
| `preferences` | `True` | The preferences section, on advice questions. |
| `conflicts` | `True` | The section of statements that may conflict, on history checks. |
| `coverage` | `"auto"` | `"auto"` answers overview questions from a digest; `"always"` does so for every question, `"never"` for none. |
| `tz` | UTC | Time zone of the dates shown and of the calendar days that group turns without a `run_id` (`Memory` only). |
| `stamp_format` | `"%Y-%m-%d (%a) %H:%M"` | The full stamp (`Memory` only). |
| `date_format` | `"%Y-%m-%d"` | The short date on a later turn of a session whose time was already shown (`Memory` only). |

`search` also takes the scope (`user_id`, `agent_id`, `run_id`) and a time window (`since`, `until`: a datetime, epoch seconds or ISO-8601 text; a time without a zone is read as UTC). The sections are shown only when the history does not fit the budget.

## Network, models and first run

No LLM is called and no stored text is sent anywhere. What can touch the network or load a model:

- **`pip install llmslim`** (numpy, scikit-learn, jsonschema) loads no model and downloads nothing at run time. Token counts are the 4-characters-per-token estimate.
- **tiktoken** (with the `mcp`, `server`, `proxy` or `fast-tokens` extra): the first token count downloads the `cl100k_base` file (about 1.7 MB) from `openaipublic.blob.core.windows.net` into tiktoken's cache (`TIKTOKEN_CACHE_DIR` sets where). If that download fails (offline, say) and there is no cached copy, LLMSlim falls back to the estimate, so its token counts, and the turns it selects, differ from an installation that has the file.
- **`relevance="semantic"`** needs `pip install "llmslim[semantic]"` (sentence-transformers and PyTorch). The first search that has to rank loads `cross-encoder/ms-marco-MiniLM-L-6-v2` (about 90 MB), downloading it from Hugging Face unless it is cached; set `HF_HUB_OFFLINE=1` to keep a cached copy from being checked online, and `LLMSLIM_RERANK_MODEL` to use another cross-encoder. Without the extra, that search raises an `ImportError` that names it (`llmslim serve` answers 501).
- **NLTK**, if it is installed with its `punkt` data, splits sentences instead of the built-in splitter. LLMSlim never downloads NLTK data.

## Stores

| Store | Use |
|---|---|
| `InMemoryStore()` | tests and short-lived agents (the default for `Memory()`) |
| `SQLiteStore(path)` | one file, Python's built-in `sqlite3`, safe across threads; `Memory("memory.db")` uses it |
| `PostgresStore(url)` | Postgres 12+ (self-hosted, Supabase, Neon, RDS) through psycopg 3, for several processes or machines; `Memory("postgresql://...")` uses it. `pip install "llmslim[postgres]"` (0.11.0 or newer) |

A store only persists and lists turns. Any object with the `MemoryStore` methods (`add`, `list`, `get`, `update`, `delete`, `delete_scope`) works, so other databases can plug in without changing selection.

**Postgres details:**
- `PostgresStore` creates its table (`llmslim_memory`, or `table=...`) and a `<table>_meta` version table if they don't exist. It does this under an advisory lock, so several processes can start at once.
- Pass a URL, and the store opens a small connection pool. You can pass your own `psycopg_pool.ConnectionPool`, or an autocommit `psycopg.Connection`, instead.
- Times are stored as `TIMESTAMPTZ` and come back in UTC, whatever the session time zone.

## Coming from Mem0

```python
# from mem0 import Memory
from llmslim.memory.compat import Mem0Memory as Memory

memory = Memory("memory.db")
memory.add(messages, user_id="alice")
hits = memory.search("Where does Alice live?", filters={"user_id": "alice"})
```

Method names, arguments and return shapes follow Mem0 2.x, with these differences:
- **`add`:** nothing is inferred, so `infer` and `prompt` are ignored and every event is `ADD`.
- **`search`:**
  - It returns the selected turns ranked by `score`, plus the prompt-ready text under `"context"`.
  - It takes a `budget` and maps `rerank=True` to the cross-encoder.
  - Filters other than `user_id`, `agent_id` and `run_id` raise instead of being ignored.
  - `expiration_date` and `reference_date` aren't supported and raise.

## Evidence

**The figures below were measured with the 0.11 read path**, which ranked rendered session text (one document per session, `[date] role: content` lines, one shared budget); with the benchmark's date format its output was byte-identical to the benchmark builder on 120 of 120 LongMemEval-S development contexts. The current read path (user turns as their own pool, per-turn blocks, question routing) selects differently and has not been re-measured on these benchmarks yet.

**What the 0.11 pipeline measured on held-out test questions** (Claude Haiku 5.5 reader, cost per 1,000 questions end to end; [full report](../benchmarks/live/round3/RESULTS.md)):
- **LongMemEval-S, on the 60 questions Mem0 was run on:**
  - LLMSlim with its reranker at 2,500 tokens answered 78.3% for $1.04;
  - Mem0's top 200 memories answered 76.7% for $220.88, almost all of it Mem0's extraction calls;
  - the whole history answered 78.3% for $90.20.
- **LongMemEval-S, all 180 questions at 10,000 tokens:** LLMSlim answered 77.8%, the same as the whole history, for $2.13 instead of $90.21. Dense retrieval over turns scored 80.6% for $4.45; the gap isn't significant.
- **LoCoMo:** LLMSlim with its reranker answered 93.0% at about 2,500 tokens for $0.95, against 91.0% for Mem0 for $2.66.

## Limits

- **Lexical mode matches words, not meanings.** Forms of the same word match ("move", "moved" and "moving"), but a question phrased in different words from the stored turn can miss it, e.g. "allergy" against "allergic", or "home" against "apartment". Use `relevance="semantic"` where users paraphrase.
- **Nothing is reconciled.** When a fact changes ("I moved to Pune"), both turns stay, each under its date, and the model sees which is newer. Delete or `update` a turn to correct it.
- **`score` is for display and ordering.** It is a lexical overlap from 0 to 1. Selection itself ranks user turns and reply windows with LLMSlim's focus engine (and the reranker when `relevance="semantic"`).
- **Question routing is a fixed English pattern.** A question phrased unusually can get the wrong sections; the turns that answer it are still ranked by relevance.
- **Questions with no Latin-script word are matched on their letters.** Ranking matches Latin-script words and numbers. A question with neither (written in Chinese, Japanese, Russian or Arabic, say, or made only of common words such as "What is it?") is matched on its other letters instead: each pair of adjacent letters counts as a word (a letter on its own, when it stands alone), ranked with the same BM25. There is no dictionary, so this is rougher than matching words. Turns that share none of them come after the turns that do; when no turn shares any (as for "What is it?"), the most recent turns come first. With `relevance="semantic"` or your own scorer, the scorer then reads the strongest of these candidates, as for any question; the default cross-encoder was trained on English, so expect less from it in other languages. A history check with nothing to match gets no conflicts section. Stored text in any script is kept and shown as it was written.
- **Cutting a long turn.** When a budget is too small for any whole turn, the best one is cut to fit, at a space when it has one. A turn with no space where a whole word fits (Chinese or Japanese prose, a long URL or token) is cut between two characters instead. A cut never splits what shows as one character (a letter and its accents, an emoji with its modifiers, a flag), the context stays within the budget, and the cut text ends with " ...". With a budget it fits in, the turn is returned whole.
- **The same context on one installation.** With lexical relevance, a search is deterministic. Across installations the token counter (tiktoken or the estimate) and the sentence splitter (NLTK or the built-in one) change what is selected, and a semantic model's scores can differ in their last digits between machines, thread counts and batch sizes, which can swap two near-tied turns.
- **Scale.** `search` reads the whole scope on every call. With the 0.11 read path, a LongMemEval history (about 500 turns, 111k tokens) took about half a second on a CPU. Keep scopes per user or per agent.
