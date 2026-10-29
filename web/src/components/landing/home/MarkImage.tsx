import Image from "next/image"

/**
 * The LLMSlim mark as the brand sheet's SVG files, one per theme, for decorative uses on the home page. Inline,
 * the mark's path data would add about 10 KB per copy to the HTML (and again to its RSC payload); as files, the browser
 * fetches only the one the theme shows (both are lazy, and the hidden one is never laid out).
 */
export function MarkImage({ size, className = "" }: { size: number; className?: string }) {
  const width = Math.round((size * 287) / 205.5)
  return <span className={`lp-markimg ${className}`} aria-hidden="true">
    <Image src="/brand/llmslim-mark-light.svg" alt="" width={width} height={size} unoptimized loading="lazy" className="art-light" />
    <Image src="/brand/llmslim-mark.svg" alt="" width={width} height={size} unoptimized loading="lazy" className="art-dark" />
  </span>
}
