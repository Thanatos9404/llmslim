/**
 * Code and output for moving memory from Mem0 or Zep into LLMSlim, shared by /compare/mem0, /compare/zep, the
 * "Migrate from Mem0" docs page and docs/MIGRATE_FROM_MEM0.md (keep them in step).
 *
 * Every output below is copied from a real run on 2 November 2026, on Windows, Python 3.12, with tiktoken installed
 * (`llmslim[fast-tokens]`): `llmslim import` from main (`pip install -e .` at 784c251, which reports 0.12.0), and the
 * Memory.add loops with llmslim 0.12.0 from PyPI. The sample Mem0 export was written by hand in the shape Mem0's
 * get_all returns, and the sample Zep messages in the shape of Zep's v4 list-messages response; the export scripts
 * that call Mem0 and Zep follow their SDK source (mem0ai 2.2.1, zep-cloud 4.0.1) but were not run against either
 * service.
 */

export type CodeSample = { language: string; filename: string; code: string; wrap?: boolean }

// ------------------------------------------------------------------ Mem0

export const MEM0_EXPORT: CodeSample = {
  language: "python", filename: "export_mem0.py",
  code: `import json

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
                out.write(json.dumps(memory, ensure_ascii=False) + "\\n")
            if not batch.get("next"):
                break
            page += 1

# Open-source Mem0 returns every memory of a scope in one call:
#   Memory.from_config(config).get_all(filters={"user_id": user_id}, top_k=100_000)["results"]`,
}

/** Two of the six lines of the sample export the outputs below come from. */
export const MEM0_SAMPLE: CodeSample = {
  language: "json", filename: "mem0-export.jsonl (2 of 6 lines)", wrap: true,
  code: `{"id": "3f1c2a9e-5b7d-4e21-9a0c-1d2e3f4a5b01", "memory": "Is allergic to peanuts", "user_id": "asha", "metadata": null, "categories": ["health"], "created_at": "2026-03-02T09:14:11.482913-08:00", "updated_at": "2026-03-02T09:14:11.482931-08:00", "expiration_date": null}
{"id": "3f1c2a9e-5b7d-4e21-9a0c-1d2e3f4a5b05", "memory": "Works as a data engineer in Bengaluru", "user_id": "ravi", "agent_id": "career-coach", "metadata": null, "categories": ["professional_details"], "created_at": "2026-06-05T22:40:00.000000-07:00", "updated_at": "2026-06-05T22:40:00.000000-07:00", "expiration_date": null}`,
}

export const MEM0_IMPORT_COMMANDS: CodeSample = {
  language: "bash", filename: "terminal",
  code: `llmslim import mem0 mem0-export.jsonl --db memory.db --dry-run   # look first: stores nothing
llmslim import mem0 mem0-export.jsonl --db memory.db             # import
llmslim import mem0 mem0-export.jsonl --db memory.db             # again: only what is new`,
}

export const MEM0_IMPORT_OUTPUT: CodeSample = {
  language: "text", filename: "output",
  code: `  (no session): 4 turns, 4 new, 0 already there
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
  turns:       0 imported, 6 already there, 0 skipped`,
}

/** 0.12.0 has no importer: the same memories through Memory.add. Running it twice stores them twice. */
export const MEM0_ADD_LOOP: CodeSample = {
  language: "python", filename: "import_mem0.py",
  code: `import json

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
print(count, "memories added")`,
}

export const MEM0_ADD_LOOP_OUTPUT: CodeSample = { language: "text", filename: "output", code: "6 memories added" }

export const MEM0_CHECK: CodeSample = {
  language: "python", filename: "check.py",
  code: `from llmslim.memory import Memory
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
    print(f"{question} ({context.tokens} of {context.history_tokens} tokens)\\n  {context.text}")`,
}

export const MEM0_CHECK_OUTPUT: CodeSample = {
  language: "text", filename: "output (the same on 0.12.0 and on main)",
  code: `0.642  Is allergic to peanuts
0.344  Is going to Jaipur in December for her sister's wedding
0.179  Moved to Pune in September 2026, to Koregaon Park
0.000  Prefers window seats on flights
2 memories for ravi with career-coach
Where did Asha move to? (31 of 107 tokens)
  [2026-09-21 (Mon) 15:30] user: Moved to Pune in September 2026, to Koregaon Park
Where does Asha live now? (21 of 107 tokens)
  [2026-03-02 (Mon) 17:14] user: Is allergic to peanuts`,
}

// ------------------------------------------------------------------ Zep

export const ZEP_EXPORT: CodeSample = {
  language: "python", filename: "export_zep.py",
  code: `import json
import os

from zep_cloud.client import Zep

client = Zep(api_key=os.environ["ZEP_API_KEY"])
users = {"asha": "<Asha's Zep user UUID>"}  # your user id -> Zep's user UUID


def to_llmslim(message, thread_uuid, user_id):
    return {
        "id": message.uuid_,
        "role": message.role,
        "content": message.content,
        "timestamp": message.reference_time or message.created_at,
        "session_id": thread_uuid,
        "user_id": user_id,
    }


with open("zep-history.jsonl", "w", encoding="utf-8") as out:
    for user_id, user_uuid in users.items():
        for thread in client.thread.list(user_uuid=user_uuid):  # the pager reads every page
            for message in client.thread.list_messages(thread.uuid_, order_by="created_at", order="asc"):
                out.write(json.dumps(to_llmslim(message, thread.uuid_, user_id), ensure_ascii=False) + "\\n")`,
}

export const ZEP_SAMPLE: CodeSample = {
  language: "json", filename: "zep-history.jsonl (2 of 5 lines)", wrap: true,
  code: `{"id": "c0a8f1e2-0001-4a7b-9c3d-5e6f7a8b9001", "role": "user", "content": "I moved to Pune last month, to Koregaon Park.", "timestamp": "2026-10-03T06:12:40.118Z", "session_id": "8a41c6d2-7f0e-4c11-b5e3-2d9f60a1c001", "user_id": "asha"}
{"id": "c0a8f1e2-0002-4a7b-9c3d-5e6f7a8b9002", "role": "assistant", "content": "Noted: you live in Pune now, in Koregaon Park.", "timestamp": "2026-10-03T06:12:44.902Z", "session_id": "8a41c6d2-7f0e-4c11-b5e3-2d9f60a1c001", "user_id": "asha"}`,
}

export const ZEP_IMPORT_COMMAND: CodeSample = {
  language: "bash", filename: "terminal",
  code: "llmslim import jsonl zep-history.jsonl --db memory.db",
}

export const ZEP_IMPORT_OUTPUT: CodeSample = {
  language: "text", filename: "output",
  code: `  8a41c6d2-7f0e-4c11-b5e3-2d9f60a1c001: 2 turns, 2 new, 0 already there
  8a41c6d2-7f0e-4c11-b5e3-2d9f60a1c002: 3 turns, 3 new, 0 already there
Imported JSONL history from zep-history.jsonl
  into:        memory.db (user asha)
  files:       1
  sessions:    2
  turns:       5 imported, 0 already there, 0 skipped`,
}

export const ZEP_ADD_LOOP: CodeSample = {
  language: "python", filename: "add_history.py",
  code: `import json

from llmslim.memory import Memory

memory = Memory("memory.db")
added = 0
with open("zep-history.jsonl", encoding="utf-8") as history:
    for line in history:
        row = json.loads(line)
        if row["role"] not in ("user", "assistant"):
            continue  # system, function and tool messages stay behind
        memory.add(
            {"role": row["role"], "content": row["content"]},
            user_id=row["user_id"],
            run_id=row["session_id"],
            timestamp=row["timestamp"],
            metadata={"source_id": row["id"]},
        )
        added += 1
print(added, "messages added")`,
}

export const ZEP_ADD_LOOP_OUTPUT: CodeSample = { language: "text", filename: "output", code: "5 messages added" }

export const ZEP_CHECK: CodeSample = {
  language: "python", filename: "check.py",
  code: `from llmslim.memory import Memory

memory = Memory("memory.db")
for question in ["What am I allergic to?", "Where did I move to?"]:
    context = memory.search(question, user_id="asha", budget=60)
    print(f"{question} ({context.tokens} of {context.history_tokens} tokens)\\n{context.text}\\n")`,
}

export const ZEP_CHECK_OUTPUT: CodeSample = {
  language: "text", filename: "output (main; 0.12.0 repeats the date on each reply)",
  code: `What am I allergic to? (42 of 149 tokens)
[2026-10-17 (Sat) 08:30] user: I'm allergic to peanuts, so never suggest satay.
assistant: Understood: no peanuts, and no satay.

Where did I move to? (47 of 149 tokens)
[2026-10-03 (Sat) 06:12] user: I moved to Pune last month, to Koregaon Park.
assistant: Noted: you live in Pune now, in Koregaon Park.`,
}

/** How to get `llmslim import` before 1.0 is on PyPI (the docs' "Try 1.0 before the release" command). */
export const INSTALL_MAIN: CodeSample = {
  language: "bash", filename: "terminal",
  code: `# main from GitHub, which becomes 1.0: adds llmslim import
pip install "llmslim[fast-tokens] @ git+https://github.com/Thanatos9404/llmslim"

# 0.12.0 from PyPI: no importer (see the loop below)
pip install "llmslim[fast-tokens]"`,
}
