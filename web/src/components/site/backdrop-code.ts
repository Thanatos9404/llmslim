/** Real snippets from the README and the integration guides, shown faintly behind the pages. */
export const BACKDROP_CODE = {
  memory: `from llmslim.memory import Memory

memory = Memory("memory.db")  # SQLite, built into Python
memory.add([{"role": "user", "content": "I'm allergic to peanuts."}], user_id="asha")
context = memory.search("Am I allergic to anything?", user_id="asha", budget=1500)
print(context.text)  # put it in the prompt as untrusted data`,
  compress: `from llmslim import compress

result = compress(chat_history, target_ratio=0.25,
                  query="Where should the card be shipped?")

print(result.compressed_text)   # what the model needs
print(result.tokens_saved)      # what you no longer pay for`,
  langchain: `from llmslim.integrations.langchain import LLMSlimCompressor

retriever = ContextualCompressionRetriever(
    base_compressor=LLMSlimCompressor(target_ratio=0.25),
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
)
docs = retriever.invoke("How many days do I have to return an item?")`,
  upgrade: (version: string) => `$ pip install --upgrade llmslim
$ python -c "import llmslim; print(llmslim.__version__)"
${version}`,
} as const
