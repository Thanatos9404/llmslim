import Image from "next/image"
import type { CSSProperties } from "react"
import { RevealGroup, RevealItem } from "./motion"

// MCP clients LLMSlim's docs give a setup for. Logos in public/logos (sources in web/DESIGN_NOTES.md), shown to say
// which apps it works with, not as endorsements. "mono" logos are single-colour marks, tinted to the text colour.
const CLIENTS = [
  { name: "Claude", file: "claude" },
  { name: "Claude Code", file: "claude-code" },
  { name: "Cursor", file: "cursor", mono: true },
  { name: "VS Code", file: "vscode" },
  { name: "Codex", file: "codex" },
  { name: "Gemini CLI", file: "gemini-cli" },
  { name: "GitHub Copilot", file: "github-copilot", mono: true },
] as const

type Mask = CSSProperties & { "--logo": string }

/** A glass dock of the MCP clients LLMSlim works with, and the one command they all run. */
export function WorksWith() {
  return <section className="lp-works" aria-labelledby="works-title">
    <div className="lp-wrap">
      <h2 id="works-title" className="lp-works-title">Works with any MCP client</h2>
      <RevealGroup as="ul" className="lp-dock lp-glass" label="MCP clients">
        {CLIENTS.map((client) => <RevealItem as="li" key={client.file}>
          <span className="lp-dock-tile">
            {"mono" in client
              ? <span className="lp-dock-mono" role="img" aria-label={client.name} style={{ "--logo": `url('/logos/${client.file}.svg')` } as Mask} />
              : <Image src={`/logos/${client.file}.svg`} alt={client.name} width={28} height={28} unoptimized />}
          </span>
          <span className="lp-dock-name" aria-hidden="true">{client.name}</span>
        </RevealItem>)}
      </RevealGroup>
      <p className="lp-works-cmd"><span>One server for all of them</span><code>uvx --from &quot;llmslim[mcp]&quot; llmslim mcp</code></p>
    </div>
  </section>
}
