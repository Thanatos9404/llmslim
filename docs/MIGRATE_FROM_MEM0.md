# Migrating from Mem0

Move a Mem0 memory into LLMSlim in three steps: export it with Mem0's `get_all`, import it, and point your code at
LLMSlim. Your Mem0 calls can stay as they are: `Mem0Memory` takes Mem0's method names, filters and result shapes.

Mem0 extracts facts with an LLM when you add a memory. LLMSlim stores every turn word for word and selects what
answers a question when you search, within a token budget, with no LLM call on either side. How the two compare on
public benchmarks, where Mem0 is better, and what each costs: [llmslim.app/compare/mem0](https://www.llmslim.app/compare/mem0).
The same guide is on the site at [llmslim.app/docs/migrate-from-mem0](https://www.llmslim.app/docs/migrate-from-mem0).

**How this was tested.** Every output below is copied from a run on 2 November 2026 (Windows, Python 3.12, with
tiktoken installed): `llmslim import` from main (`pip install -e .`), and the `Memory.add` loop and the search with
llmslim 0.12.0 from PyPI. The export ran on a sample of six memories for two users, written by hand in the shape
Mem0's `get_all` returns. We have no Mem0 account, so the export script follows Mem0's SDK source (mem0ai 2.2.1) but
was not run against Mem0.

## 1. Install

```bash
# main from GitHub, which becomes 1.0: adds llmslim import
pip install "llmslim[fast-tokens] @ git+https://github.com/Thanatos9404/llmslim"

# 0.12.0 from PyPI: no importer (see step 3b)
pip install "llmslim[fast-tokens]"
```

`llmslim import` comes with LLMSlim 1.0. Until then, install main from GitHub to use it, or add the memories with the
loop in step 3b on 0.12.0. Main reports its version as 0.12.0 until the release changes it. `fast-tokens` brings
tiktoken for exact token counts; without it, counts are estimated at about 4 characters per token.

## 2. Export your memories from Mem0

`get_all` lists a scope's memories as `{"results": [...]}`. On the Platform it is paged, 200 at a time, with a `next`
link while more remain ([API reference](https://docs.mem0.ai/api-reference/memory/get-memories)). Write each memory as
one JSON line:

```python
import json

from mem0 import MemoryClient

client = MemoryClient()  # reads MEM0_API_KEY
user_ids = ["asha", "ravi"]  # the users whose memories you are moving

with open("mem0-export.jsonl", "w", encoding="utf-8") as out:
    for user_id in user_ids:
        page = 1
        while True:
            batch = client.get_all(filters={"user_id": user_id}, page=page, page_size=200)
            for memory in batch["results"]:
                memory.setdefault("user_id", user_id)
                out.write(json.dumps(memory, ensure_ascii=False) + "\n")
            if not batch.get("next"):
                break
            page += 1

# Open-source Mem0 returns every memory of a scope in one call:
#   Memory.from_config(config).get_all(filters={"user_id": user_id}, top_k=100_000)["results"]
```

Two of the six lines of the sample export:

```json
{"id": "3f1c2a9e-5b7d-4e21-9a0c-1d2e3f4a5b01", "memory": "Is allergic to peanuts", "user_id": "asha", "metadata": null, "categories": ["health"], "created_at": "2026-03-02T09:14:11.482913-08:00", "updated_at": "2026-03-02T09:14:11.482931-08:00", "expiration_date": null}
{"id": "3f1c2a9e-5b7d-4e21-9a0c-1d2e3f4a5b05", "memory": "Works as a data engineer in Bengaluru", "user_id": "ravi", "agent_id": "career-coach", "metadata": null, "categories": ["professional_details"], "created_at": "2026-06-05T22:40:00.000000-07:00", "updated_at": "2026-06-05T22:40:00.000000-07:00", "expiration_date": null}
```

The Platform's [memory export](https://docs.mem0.ai/platform/features/memory-export) writes JSON shaped by a schema you
define, not a list of memories, so `llmslim import mem0` doesn't read it. Use `get_all`.

## 3a. Import them with `llmslim import` (1.0, or main today)

`llmslim import mem0` reads JSON lines like these, what `get_all` returns (`{"results": [...]}`), a plain list of
memories, or `{"memories": [...]}`. Each memory becomes one `user` turn under its own `user_id`, `agent_id` and
`run_id` (or `session_id`), at its original `created_at`, so Mem0-style filters find it where they did. Look first
with `--dry-run`; importing again stores only what is new.

```bash
llmslim import mem0 mem0-export.jsonl --db memory.db --dry-run   # look first: stores nothing
llmslim import mem0 mem0-export.jsonl --db memory.db             # import
llmslim import mem0 mem0-export.jsonl --db memory.db             # again: only what is new
```

```text
  (no session): 4 turns, 4 new, 0 already there
  (no session): 2 turns, 2 new, 0 already there
Would import Mem0 history from mem0-export.jsonl
  into:        memory.db (user asha, ravi)
  files:       1
  sessions:    2
  turns:       6 to import, 0 already there, 0 skipped
  dry run: nothing was stored
  (no session): 4 turns, 4 new, 0 already there
  (no session): 2 turns, 2 new, 0 already there
Imported Mem0 history from mem0-export.jsonl
  into:        memory.db (user asha, ravi)
  files:       1
  sessions:    2
  turns:       6 imported, 0 already there, 0 skipped
  (no session): 4 turns, 0 new, 4 already there
  (no session): 2 turns, 0 new, 2 already there
Imported Mem0 history from mem0-export.jsonl
  into:        memory.db (user asha, ravi)
  files:       1
  sessions:    2
  turns:       0 imported, 6 already there, 0 skipped
```

`--db` also takes a `postgresql://` or `mongodb://` URL. Without it, the turns go to `~/.llmslim/memory.db`, the memory
`llmslim mcp` and `llmslim serve` read. `--user-id` stores every turn under one user instead of each memory's own. The
other options are in [IMPORT.md](IMPORT.md).

## 3b. Or add them in a loop (0.12.0)

0.12.0 has no importer. This loop stores the same turns; unlike the importer, it stores everything again if you run it
twice.

```python
import json

from llmslim.memory import Memory

memory = Memory("memory.db")
count = 0
with open("mem0-export.jsonl", encoding="utf-8") as export:
    for line in export:
        item = json.loads(line)
        memory.add(
            {"role": "user", "content": item["memory"]},
            user_id=item.get("user_id"),
            agent_id=item.get("agent_id"),
            run_id=item.get("run_id") or item.get("session_id"),
            timestamp=item["created_at"],
            metadata={"source_id": item["id"]},
        )
        count += 1
print(count, "memories added")
```

```text
6 memories added
```

## 4. Switch one import and search

`Mem0Memory` answers the calls your Mem0 code makes; `Memory` is LLMSlim's own API, with a token budget.

```python
from llmslim.memory import Memory
from llmslim.memory.compat import Mem0Memory

# Code written for Mem0 keeps its calls: the same method names, filters and result shape.
mem0_style = Mem0Memory("memory.db")
hits = mem0_style.search("What is Asha allergic to?", filters={"user_id": "asha"})
for hit in hits["results"]:
    print(f'{hit["score"]:.3f}  {hit["memory"]}')
coach = mem0_style.get_all(filters={"user_id": "ravi", "agent_id": "career-coach"})
print(len(coach["results"]), "memories for ravi with career-coach")

# LLMSlim's own API: the turns that answer the question, within a token budget.
memory = Memory("memory.db")
for question in ["Where did Asha move to?", "Where does Asha live now?"]:
    context = memory.search(question, user_id="asha", budget=40)
    print(f"{question} ({context.tokens} of {context.history_tokens} tokens)\n  {context.text}")
```

Output, the same on 0.12.0 and on main:

```text
0.642  Is allergic to peanuts
0.344  Is going to Jaipur in December for her sister's wedding
0.179  Moved to Pune in September 2026, to Koregaon Park
0.000  Prefers window seats on flights
2 memories for ravi with career-coach
Where did Asha move to? (31 of 107 tokens)
  [2026-09-21 (Mon) 15:30] user: Moved to Pune in September 2026, to Koregaon Park
Where does Asha live now? (21 of 107 tokens)
  [2026-03-02 (Mon) 17:14] user: Is allergic to peanuts
```

The last two lines show the limit of lexical relevance. Mem0's memories are short facts without their subject, so
"Where did Asha move to?" shares the word "move" with "Moved to Pune" and finds it, while "Where does Asha live now?"
shares no word with it, and the budget goes to the oldest memory instead. For questions worded unlike what was stored,
use `relevance="semantic"` (`pip install "llmslim[semantic]"`), a 22M-parameter cross-encoder that runs on a CPU, or a
budget that holds the whole history. We did not run the semantic mode in this test.

Put `context.text` (or `hits["context"]`) into the new user turn of your prompt as data, not instructions: see
[MEMORY.md](MEMORY.md).

## What comes across, and what doesn't

- **Each memory, as it is.** Mem0's memories are facts its model extracted ("Is allergic to peanuts"), not what was
  said, and they are stored as they are. From then on, what you `add` is stored word for word.
- **Scope and time.** Each turn keeps the memory's `user_id`, `agent_id` and `run_id` (or `session_id`), its
  `created_at` as its time (in UTC), and its `id` as `source_id` in its metadata.
- **Not imported:** Mem0's `categories`, `metadata`, `hash` and `updated_at`, and anything that lives only in the
  Platform, such as graph relations and user profiles.

## What `Mem0Memory` does differently

It follows the open-source `Memory` class of Mem0 2.x, not the hosted `MemoryClient`. The differences fail loudly
rather than silently:

- **Nothing is extracted.** `add` stores turns verbatim and makes no model call; `infer`, `prompt` and `memory_type`
  are accepted and ignored, and every returned event is `ADD`.
- **`search`** selects the turns that answer the question within a token `budget` (default 2,000), returns them ranked
  by a lexical overlap `score`, and also returns the prompt-ready text under `"context"`. `rerank=True` uses the
  optional cross-encoder; `threshold` and `explain` are ignored.
- **Filters** match `user_id`, `agent_id` and `run_id` exactly, and at least one is required. Any other filter key
  raises `ValueError`.
- **`expiration_date`, `reference_date` and `reset`** raise.

The full list is in [MEMORY.md](MEMORY.md#coming-from-mem0).

## Coming from Zep

`llmslim import` has no Zep format. The closest path is Zep's message history: export each thread's messages as JSON
lines with `role`, `content`, `timestamp`, `session_id`, `user_id` and `id`, and import them with
`llmslim import jsonl`. The script and its tested output are on
[llmslim.app/compare/zep](https://www.llmslim.app/compare/zep#migrate-title).
