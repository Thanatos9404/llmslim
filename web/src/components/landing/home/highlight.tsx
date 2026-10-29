import type { ReactNode } from "react"

export type CodeLanguage = "python" | "json" | "bash" | "ts"

// A small highlighter for the home page's four snippets, run on the server: comments, strings, keywords, numbers
// and function names. Anything it does not recognise stays plain text.
const KEYWORDS: Record<CodeLanguage, string[]> = {
  python: ["from", "import", "def", "return", "print", "None", "True", "False"],
  ts: ["import", "from", "const", "await", "new", "export", "async"],
  bash: ["pip", "curl", "llmslim", "npm", "uvx", "claude"],
  json: [],
}

const TOKEN = /(#[^\n]*|\/\/[^\n]*)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|\b(\d+(?:\.\d+)?)\b|([A-Za-z_][\w]*)(?=\()|([A-Za-z_][\w-]*)/g

export function highlight(code: string, language: CodeLanguage): ReactNode[] {
  const keywords = new Set(KEYWORDS[language])
  const out: ReactNode[] = []
  let last = 0
  let key = 0
  for (const match of code.matchAll(TOKEN)) {
    const [text, comment, string, number, call, word] = match
    const at = match.index ?? 0
    if (at > last) out.push(code.slice(last, at))
    last = at + text.length
    // In bash, "#" starts a comment only at the start of a word.
    if (comment && language === "bash" && comment.startsWith("//")) { out.push(text); continue }
    if (comment && language !== "json" && !(language === "python" && comment.startsWith("//"))) {
      out.push(<span key={key++} className="lp-tk-comment">{text}</span>)
    } else if (string) {
      const isKey = language === "json" && /^\s*:/.test(code.slice(last))
      out.push(<span key={key++} className={isKey ? "lp-tk-key" : "lp-tk-string"}>{text}</span>)
    } else if (number) {
      out.push(<span key={key++} className="lp-tk-number">{text}</span>)
    } else if (call && !keywords.has(call)) {
      out.push(<span key={key++} className="lp-tk-call">{text}</span>)
    } else if ((call || word) && keywords.has(text)) {
      out.push(<span key={key++} className="lp-tk-keyword">{text}</span>)
    } else {
      out.push(text)
    }
  }
  if (last < code.length) out.push(code.slice(last))
  return out
}
