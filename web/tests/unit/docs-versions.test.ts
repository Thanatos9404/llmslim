import { describe, expect, it } from "vitest"
import { API_REFERENCE_DOCS } from "@/data/api-reference"
import { API_REFERENCE_DOCS_0_12 } from "@/data/api-reference-0.12"
import { DOCS_BY_VERSION, DOCS_REGISTRY, docsInOrder, isNewIn, versionNoticeText, type DocPage, type DocSection } from "@/data/docs"
import { DEFAULT_DOCS_VERSION, DOCS_VERSIONS, docHref, docsHome, parseDocsPath, resolveDocLink, versionStatus, type DocsVersion } from "@/data/docs-versions"
import { llmsTxt, markdownFor, markdownPaths } from "@/lib/agent-content"

const VERSIONS = DOCS_VERSIONS.map((version) => version.id)

/** Every piece of text a section shows, links included. */
function sectionText(section: DocSection): string[] {
  return [
    section.content, section.after ?? "", ...(section.items ?? []), ...(section.table?.rows.flat() ?? []), ...(section.table?.headers ?? []),
    section.callout?.content ?? "", section.callout?.title ?? "",
    ...[section.codeSnippet, ...(section.snippets ?? [])].flatMap((snippet) => (snippet ? [snippet.code, snippet.filename ?? ""] : [])),
  ]
}
const pageText = (page: DocPage) => [...page.sections.flatMap(sectionText), ...page.faqs.flatMap((faq) => [faq.question, faq.answer]), page.title, page.subtitle, page.description]
const links = (text: string) => [...text.matchAll(/\]\(([^)\s]+)\)/g)].map((match) => match[1])

describe("docs versions", () => {
  it("shows what pip installs by default, until 1.0 is released", () => {
    expect(DEFAULT_DOCS_VERSION).toBe("0.12")
    expect(versionStatus("0.12")).toBe("current")
    expect(versionStatus("1.0")).toBe("preview")
    expect(DOCS_REGISTRY).toBe(DOCS_BY_VERSION[DEFAULT_DOCS_VERSION])
  })

  it("puts the default version at /docs and the others under their number", () => {
    expect(docsHome("0.12")).toBe("/docs")
    expect(docHref("0.12", "quickstart-python")).toBe("/docs/quickstart-python")
    expect(docHref("1.0", "import-history")).toBe("/docs/1.0/import-history")
    expect(parseDocsPath("/docs")).toEqual({ version: "0.12", slug: null })
    expect(parseDocsPath("/docs/quickstart-mcp")).toEqual({ version: "0.12", slug: "quickstart-mcp" })
    expect(parseDocsPath("/docs/1.0")).toEqual({ version: "1.0", slug: null })
    expect(parseDocsPath("/docs/1.0/remote-mcp/")).toEqual({ version: "1.0", slug: "remote-mcp" })
    expect(parseDocsPath("/pricing")).toBeNull()
  })

  it("flips with one constant: 1.0 moves to /docs and 0.12 becomes a previous version", () => {
    expect(docHref("1.0", "import-history", "1.0")).toBe("/docs/import-history")
    expect(docHref("0.12", "quickstart-python", "1.0")).toBe("/docs/0.12/quickstart-python")
    expect(versionStatus("1.0", "1.0")).toBe("current")
    expect(versionStatus("0.12", "1.0")).toBe("previous")
    expect(parseDocsPath("/docs/import-history", "1.0")).toEqual({ version: "1.0", slug: "import-history" })
  })

  it("gives every version the four quickstarts and the generated reference", () => {
    for (const version of VERSIONS) {
      for (const slug of ["quickstart-python", "quickstart-mcp", "quickstart-http", "quickstart-typescript", "api-llmslim", "api-llmslim-memory", "storage-backends", "coding-agents", "migrate-from-mem0"]) {
        expect(DOCS_BY_VERSION[version][slug], `${version}/${slug}`).toBeDefined()
      }
    }
  })

  it("keeps 1.0-only guides out of the 0.12 docs", () => {
    for (const slug of ["import-history", "explain", "openai-compatible-endpoint", "remote-mcp", "migrate-to-1-0", "api-stability"]) {
      expect(DOCS_BY_VERSION["0.12"][slug], slug).toBeUndefined()
      expect(DOCS_BY_VERSION["1.0"][slug], slug).toBeDefined()
      expect(isNewIn("1.0", slug)).toBe(true)
    }
  })

  it("mentions a 1.0 feature on a 0.12 page only next to a link to the 1.0 preview", () => {
    const unreleased = /llmslim import (?:claude|chatgpt|mem0|jsonl|auto)|import_history|explain=True|"explain"|--transport|MongoStore|mongodb:\/\/|--allowed-host|--upstream-url|chat\/completions|store_unavailable/
    for (const page of Object.values(DOCS_BY_VERSION["0.12"])) {
      for (const section of page.sections) {
        const text = sectionText(section).join("\n")
        if (unreleased.test(text)) expect(text, `${page.slug}#${section.id}`).toMatch(/doc@1\.0:/)
      }
      for (const faq of page.faqs) expect(unreleased.test(faq.answer), `${page.slug}: ${faq.question}`).toBe(false)
    }
  })

  it("documents each release's own API in its reference", () => {
    const text = (pages: DocPage[]) => JSON.stringify(pages)
    for (const name of ["import_history", "MongoStore", "SearchExplanation"]) {
      expect(text(API_REFERENCE_DOCS)).toContain(name)
      expect(text(API_REFERENCE_DOCS_0_12)).not.toContain(name)
    }
    expect(API_REFERENCE_DOCS_0_12[0].description).toMatch(/generated from the source of llmslim 0\.12\.0\.$/)
    expect(DOCS_BY_VERSION["0.12"]["api-llmslim-memory"].description).toBe(API_REFERENCE_DOCS_0_12[1].description)
    expect(DOCS_BY_VERSION["1.0"]["api-llmslim-memory"].description).toBe(API_REFERENCE_DOCS[1].description)
  })

  it("resolves every link to a guide and a section of the version that shows it", () => {
    for (const version of VERSIONS) {
      for (const page of Object.values(DOCS_BY_VERSION[version])) {
        const ids = new Set(page.sections.map((section) => section.id))
        expect(ids.size, `${version}/${page.slug}: section ids are unique`).toBe(page.sections.length)
        for (const href of pageText(page).flatMap(links)) {
          const where = `${version}/${page.slug} -> ${href}`
          if (href.startsWith("#")) { expect(ids.has(href.slice(1)), where).toBe(true); continue }
          const match = href.match(/^doc(?:@([\d.]+))?:([a-z0-9-]+)(?:#([a-z0-9-]+))?$/)
          if (!match) { expect(href, where).toMatch(/^(https:\/\/|\/)/); continue }
          const target = (match[1] ?? version) as DocsVersion
          const doc = DOCS_BY_VERSION[target]?.[match[2]]
          expect(doc, where).toBeDefined()
          if (match[3]) expect(doc.sections.some((section) => section.id === match[3]), where).toBe(true)
          expect(resolveDocLink(href, version)).toBe(docHref(target, match[2]) + (match[3] ? `#${match[3]}` : ""))
        }
        for (const related of page.relatedPages) expect(DOCS_BY_VERSION[version][related.slug], `${version}/${page.slug} related`).toBeDefined()
      }
    }
  })

  it("lists every page of a version once, in category order", () => {
    for (const version of VERSIONS) {
      const order = docsInOrder(version).map((page) => page.slug)
      expect(new Set(order).size).toBe(order.length)
      expect(order.length).toBe(Object.keys(DOCS_BY_VERSION[version]).length)
    }
  })
})

describe("docs for agents", () => {
  it("serves every docs page of every version as Markdown", () => {
    for (const path of markdownPaths().filter((parts) => parts[0] === "docs")) expect(markdownFor(path), path.join("/")).not.toBeNull()
    expect(markdownFor(["docs", "1.0", "nope"])).toBeNull()
    expect(markdownFor(["docs", "0.12", "quickstart-python"])).toBeNull() // the default version lives at /docs/<slug>
  })

  it("opens every preview page with the notice, and leaves the default version's pages without one", () => {
    const notice = versionNoticeText("1.0")!
    expect(notice).toContain("pip install llmslim")
    expect(versionNoticeText(DEFAULT_DOCS_VERSION)).toBeNull()
    for (const slug of Object.keys(DOCS_BY_VERSION["1.0"])) expect(markdownFor(["docs", "1.0", slug])!.split("\n").slice(0, 3).join("\n")).toContain(notice)
    for (const slug of Object.keys(DOCS_REGISTRY)) expect(markdownFor(["docs", slug])).not.toContain("Upcoming in")
  })

  it("makes guide links absolute and keeps the version", () => {
    const text = markdownFor(["docs", "1.0", "quickstart-python"])!
    expect(text).toContain("](https://www.llmslim.app/docs/1.0/migrate-to-1-0#try-it)")
    expect(text).not.toMatch(/\]\(doc[:@]/)
    expect(markdownFor(["docs", "quickstart-mcp"])).toContain("](https://www.llmslim.app/docs/1.0/remote-mcp)")
  })

  it("lists the default version in llms.txt and names the preview as not on PyPI", () => {
    const text = llmsTxt()
    expect(text).toContain("https://www.llmslim.app/docs/quickstart-python.md")
    expect(text).not.toContain("https://www.llmslim.app/docs/import-history.md")
    expect(text).toMatch(/LLMSlim 1\.0 docs \(preview\)\]\(https:\/\/www\.llmslim\.app\/docs\/1\.0\.md\): upcoming and not on PyPI yet/)
  })
})
