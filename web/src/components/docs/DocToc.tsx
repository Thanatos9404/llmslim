"use client"
import { m, useReducedMotion, useScroll, useSpring } from "framer-motion"
import { useEffect, useState } from "react"

/** "On this page": follows the section in view. */
export function DocToc({ sections }: { sections: { id: string; title: string }[] }) {
  const [active, setActive] = useState(sections[0]?.id)
  const reduced = useReducedMotion()
  useEffect(() => {
    const seen = new Map<string, boolean>()
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => seen.set(entry.target.id, entry.isIntersecting))
      const first = sections.find((section) => seen.get(section.id))
      if (first) setActive(first.id)
    }, { rootMargin: "-90px 0px -55% 0px" })
    sections.forEach((section) => { const node = document.getElementById(section.id); if (node) observer.observe(node) })
    return () => observer.disconnect()
  }, [sections])
  return <nav className="doc-toc" aria-label="On this page">
    <p className="doc-toc-label">On this page</p>
    <ul>{sections.map((section) => <li key={section.id}>
      <a href={`#${section.id}`} aria-current={active === section.id ? "true" : undefined}>
        {active === section.id && <m.span layoutId="doc-toc-on" className="doc-toc-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}
        {section.title}
      </a>
    </li>)}</ul>
  </nav>
}

/** A hairline at the top of the page that fills as you read. */
export function ReadingProgress() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 40, restDelta: 0.001 })
  return <m.div className="doc-progress" style={{ scaleX }} aria-hidden="true" />
}
