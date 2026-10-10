/** Homepage FAQ shown on the page, mirrored in its FAQPage structured data and in /index.md. */
export const homeFaqs: ReadonlyArray<readonly [question: string, answer: string]> = [
  ["Does it need an API key?", "Not for local extraction. LLMSlim’s default extractive strategy runs in your Python application. Rewrite and hybrid strategies use a provider you supply."],
  ["Does it work with my model?", "LLMSlim prepares text before your model call. Use the output with Sarvam, OpenAI, Anthropic, Gemini, or a local model. Your application keeps control of the request."],
  ["How much should I compress?", "Start with a conservative target ratio and evaluate the answers your application produces. The right setting depends on the documents, question, and model. Compression can remove useful information; there is no universal quality guarantee."],
  ["What is LLMSlim Platform?", "A private beta that builds on the open-source Core. It keeps a verifiable timeline of what your agents were told and what changed, explains and replays every context decision, and can learn from outcomes which context helps. Learned policies start in shadow mode and change nothing until an administrator promotes them. Core stays MIT licensed: pip install llmslim."],
]
