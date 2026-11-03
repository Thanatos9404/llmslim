# LLMSlim website redesign

The landing page follows the user's Raycast reference: a cinematic composition, custom dimensional artwork, concise product copy, and open layouts rather than a grid of promotional cards. Light and dark modes use separate artwork and shared semantic theme tokens. The existing theme persistence script and SEO infrastructure remain in place.

## Design pilot, phase 1 (3 November 2026)

Pages: `/compare/mem0`, `/compare/zep`, `/compare/llmlingua`, `/integrations`. Everything else changes only through
the shared tokens in `globals.css`. The glass and aurora direction of #114 and #116 (closed on 30 October) is not
revisited: no frosted panels, no aurora light, no navy sky.

### Direction

1. Keep the site's character and raise the volume: ivory and near-black surfaces, the brand green, Geist with an
   Instrument Serif italic second line, hairline tables, the pixel and ASCII backdrop; display type up to 96px.
2. One memorable thing per page: a dark plate, a free photo under a veil, with the new memory glyph playing on it and
   the two products' real logos beneath (on /integrations, the stack drawing).
3. The data is the hero of a comparison: a logo on every result row, accuracy bars on an honest 0 to 100 scale with
   the 95% interval outlined, numbers that count up, paired differences on an axis centred on zero.
4. Motion is weighted and quiet: one decelerating curve, transform and opacity only, reveals once, springs only
   under the pointer; reduced motion gets the final state from the first paint.
5. One palette from the brand: green, blue and violet from the mark; neutrals pulled a little toward the brand navy.

### Palette

| Token | Light | Dark | Note |
|---|---|---|---|
| `--surface` | `#fbfbfa` ivory (unchanged) | `#090a10` (was `#0b0b0a`) | near-black with a trace of navy `#060816` |
| `--soft` | `#f4f4f2` (unchanged) | `#10121a` (was `#121211`) | cards, chips, tiles |
| `--ink` | `#11131c` (was `#141413`) | `#eceef2` (was `#ededea`) | navy ink on ivory |
| `--subtle` | `#5f6270` (was `#6b6a65`) | `#8e92a0` (was `#8f8e89`) | 5.8:1 and 6.4:1 on the surfaces (AA) |
| `--line` | `#e5e6ea` (was `#e7e6e2`) | `#22252e` (was `#252523`) | hairlines |
| `--brand` | `#007a52` | `#00f59b` | unchanged; 5.2:1 on ivory |
| `--brand-blue`, `--brand-violet` | `#2f67ee`, `#4a3df0` | `#4f8cff`, `#7c5cff` | unchanged; the glyph and strands |
| `--spectrum` | violet to blue to green | same | new; glyph, strands and data accents only |

The island, window, plate and button tokens follow the same shift. Plates are always dark, in both themes.

**One fix with visible effects on every page.** `--mono` listed itself (`…,var(--mono)`), a cycle that made every
`font: … var(--mono)` declaration invalid, so code blocks, table headings, eyebrows and the install line all fell back
to Geist at the inherited size (code blocks were 16px Geist). The token now ends in real monospace fallbacks, so those
elements render as they were written: Geist Mono at 9 to 13px. This is the largest change outside the pilot pages
(home hero release line, footer eyebrows, docs code); revert that one line if it is not wanted.

`--serif` also gains a metric fallback, Georgia sized to Instrument Serif's widths (76.2% upright, 78.6% italic,
measured on the headings' phrases), so a serif line wraps the same before and after the font loads. Without it the
96px serif line wrapped differently on the fallback and shifted the hero (CLS 0.04 to 0.06 on the first build).
`--mono` gets the same treatment (Courier New at Geist Mono's 0.6em advance), so the right-anchored ASCII backdrop and
mono labels keep their width when Geist Mono arrives.

### Type scale

Tailwind steps, fluid between two of them only at display sizes (`--fs-*` in `globals.css`): label 12, small 14,
body 16, lede 17 to 20, h3 24, h2 36 to 60, h1 40 to 72, display 48 to 96. Headings keep the site's two-tone form: Geist
600 to 620 at about -0.05em, then the Instrument Serif italic line at 56% ink.

### Motion

- Curve `--ease-out: cubic-bezier(.22,1,.36,1)`; `--ease-spring` for hover overshoot; 300ms colour, 500ms movement,
  800ms reveals.
- Scroll reveals: `Reveal` is fixed, not forked. The hidden state is now CSS, under `prefers-reduced-motion:
  no-preference` only, cancelled by a `<noscript>` rule; before, it was server-rendered inline opacity 0, so
  reduced-motion visitors saw nothing until hydration and visitors without scripts never saw it.
- Results tables (`MotionTable`): one client wrapper per table; bars grow with Framer Motion's WAAPI `animate`, numbers
  count up to the printed value. Only a table that starts below the fold is armed. The final text is always in the DOM.
- Hover: the stage's logos lift on the spring curve and set context flowing along their strand; integration rows lift
  and tilt their logo tile; cards and chips lift 1 to 2px. These are CSS transitions on `--ease-spring`, not Framer
  Motion components: on /integrations, Framer hover components on the stage and the rows, flowing strands and animated
  group glyphs cost 8 mobile points (hydration, style and paint work; SVG transforms and stroke animations are not
  composited), so that page now hydrates one delegated hover handler and animates nothing on its own. Phones (640px
  and under) no longer load the stage photo: a `<picture>` source gives them a blank pixel. Measured afterwards,
  interleaved against `main`, median of five: 67 against 72 on a phone (runs 61 to 80 against 66 to 76). The gap
  left is hydration and first-render work (React's hydration task about 1.0 s against 0.8 s, style and layout
  0.56 s against 0.33 s), not bytes.
- Parallax: the compare plates' photos drift 6% against the scroll (`ParallaxPhoto`, `useScroll`/`useTransform`); the
  integrations stage photo is still, and shown only above 640px.
- The glyph plays once on load (CSS keyframes), again on pointer enter, and on phones when the plate scrolls into view.

### The glyph

`MemoryGlyph` takes the LogoMark's idea (five strands, three kept) as a memory: five stored turns with the mark's
rounded ends slide in, the three that fit the token budget light up in the mark's gradient (`--mark-*`) and get a
square pixel on a budget rail, and the other two dim. Hero size on the plates; 14px in place of the kicker's pixel.

### Design rules

Followed: one base curve and transform/opacity-only motion, reveals once via IntersectionObserver, reduced motion as
a still state, visible focus rings and hover/active states, headings and display sizes on Tailwind steps, no
single-sided card borders; one bold element per page, structure that encodes information (the interval outlines,
the zero axis), a token plan checked against the brief before building, screenshots as critique.

Kept on purpose, because the brief or the site's identity says so: Instrument Serif italic in headings (common
guidance discourages italics in headlines; it is the site's signature); photo veils are gradients (no gradient
backgrounds), only behind photos; no tagline reveal section or new marketing copy (the pilot keeps every word); mono
uppercase table headings stay (existing identity, now rendering as designed); scroll reveals and hover lifts are
used although they are common, because the founder asked for them, kept to one curve and one distance; the near-black surface with a green accent is the brand, not a
default; lucide icons stay rather than Phosphor or Solar; body sizes of 15 and 17px stay where the existing pages use
them, rather than snapping every one to a step.

### Logos and photos

Logos: `public/logos/SOURCES.md` (Simple Icons 16.36.0, CC0 data, and the companies' own files). Photos:
`public/media/stock/CREDITS.md` (four Pexels photos, no people). Both self-hosted; the CSP is unchanged.

## Assets

The 3D compression ribbon that floated behind the home hero was removed on 30 October 2026, with both of its images.

- `public/llmslim_logo.png`: existing official LLMSlim logo, unchanged.
- `public/sarvam-symbol.svg`: official Sarvam flower mark.
- `public/sarvam-wordmark.svg`: official Sarvam wordmark.
- `public/fonts/geist-latin.woff2`: self-hosted variable font; license in `public/fonts/OFL.txt`.

Sarvam assets came from its public brand website. The program-logo layout and acceptance wording follow the user's supplied `Untitled design (8).png` reference. Both brands remain independently identifiable. The relationship is Sarvam Startup Program acceptance only: not a partnership, collaboration, co-branding, or endorsement.

Sources:
- https://www.raycast.com/
- https://www.box.com/
- https://www.sarvam.ai/brand-guidelines
- https://assets.sarvam.ai/tr:dpr-auto/assets/brand/logos/sarvam-logo-black.svg
- https://assets.sarvam.ai/tr:dpr-auto/assets/brand/logos/sarvam-wordmark-black.svg
- https://docs.sarvam.ai/api-reference/chat/chat-completions

### Startup program logos added on 12 October 2026

Downloaded with curl from each company's own site, checked as untrusted SVG (no scripts, event handlers,
`foreignObject`, external references or CSS imports) and copied byte for byte into `public/startups/`.

- Honeycomb: `honeycomb-light.svg` and `honeycomb-dark.svg` are the light and dark logos of Honeycomb's
  documentation site (https://mintcdn.com/honeycomb/TYbxiKcJ1fL3Sm5n/_assets/logos/light.svg and
  `.../dark.svg`, referenced from https://docs.honeycomb.io/). They match the organisation logo on
  https://www.honeycomb.io/news (https://www.honeycomb.io/api/assets/honeycomb-logo.svg), which has no dark variant.
- Exa: `exa-blue.svg` and `exa-white.svg` are `Logo/SVGs/Logo/Exa Logo Blue.svg` and `Exa Logo White.svg`
  from the brand kit on https://exa.ai/brand (https://exa.ai/assets/Exa%20Brand%20Assets.zip).
- Neo4j: `neo4j-full-color.svg` is the organisation logo used across neo4j.com, including the newsroom
  (https://dist.neo4j.com/wp-content/uploads/20230926084108/Logo_FullColor_RGB_TransBG.svg); `neo4j-white.png`
  is `Logo/png/logo-white-RGB-transBG.png` from the newsroom's logo kit (https://media.neo4j.com/Neo4j-Logo.zip,
  linked from https://neo4j.com/newsroom/), which has no white SVG of the same logo.

### Cartesia Startups logo, added on 15 October 2026

Cartesia's grant email (14 October 2026) asks recipients to "include the Cartesia Startups logo on your website".
It attaches no logo file, and https://cartesia.ai/startups has no badge or brand kit. The only Cartesia Startups
artwork it sends is the lockup on its "Grant recipient" card: the Cartesia wordmark, a hairline divider and
"Startups" in a serif. At the founder's direction the lockup was rebuilt as SVG instead of being cropped from that
raster card:

- The mark and letters are the wordmark SVG from the header of https://cartesia.ai (viewBox `0 0 579 83`), with the
  path data unchanged and only the fill colours set.
- "Startups" is Instrument Serif Regular (SIL OFL, `public/fonts/`) converted to outlines, at the wordmark's cap
  height and baseline. Cartesia's own serif is not public, so this is close to the card but not the same.
- `cartesia-startups-light.svg` uses the card's colours: forest `#1a6b2e` for the wordmark, and carbon `#1e1c1a`
  for the divider and "Startups". `cartesia-startups-dark.svg` uses Cartesia's verdant `#309d4b` for the mark and its
  page colour `#f4f4f1` for everything else. These are the brand colours named in the email's own stylesheet.
- Both files are self-contained: no fonts, scripts or external references. They come from a scratch script,
  `cartesia_lockup.py`, which is not committed, and are about 10 KB each.

## Design rollout, phase 2: results and benchmarks (November 2026)

(Placed here, not with the other phase 2 sections at the top, so that the four phase 2 pull requests do not edit the
same lines of this file.) The pilot's system on `/results` and `/benchmarks`. Every number, caption, axis and note is
unchanged, including the round 6 BEAM-1M results; the additions are logos beside names already on the page.

- **Logos on every row that names a system.** `SystemMark` (`src/components/results/SystemMark.tsx`) takes the logo
  from the name (`logoForSystem`): LLMSlim's mark, Mem0's, Zep's, LLMLingua's (for LLMLingua-2 and LongLLMLingua), Qwen's
  for the Qwen-embedding baseline, and a neutral pixel for baselines such as the full context. It sits on the plates'
  rulers and the head-to-head board on /results, and on the bars (`ResultBars`) and both tables on /benchmarks. The
  systems each hero's lede names (Mem0, Zep, LLMLingua-2, LongLLMLingua) also appear as logo chips under it.
- **Glyph.** The memory glyph replaces the pixel in the kickers: still on /results (its sections are client
  components that render on load, and SVG animation is main-thread work), playing when revealed on /benchmarks. The
  close of /results carries it at hero size on a small dark plate, playing when revealed.
- **Type.** /benchmarks' headline and section headings move to `--fs-h1` and `--fs-h2`, with the Instrument Serif half
  on its own line (the headline's second half was plain grey before).
- **Hover and motion.** Board rows, weak-spot cells and table rows tint under the pointer on `--ease-out`; the weak spots
  and method notes on /benchmarks hang from a spectrum hairline. /benchmarks now imports `Reveal` from its own module
  rather than through the home page's components.
- **Where styles live.** /results in its route stylesheet (`story.css`); /benchmarks with the other `bm-*` rules in
  `globals.css`, scoped to `.bm-page` (it has no route stylesheet, and a new one would be a second render-blocking
  request).

## Behavior and scope

- Scroll-linked artwork and pointer response use animation frames and direct CSS transforms without rendering React on every scroll event.
- Section reveals use IntersectionObserver. Reduced-motion preferences disable parallax, pointer movement, and transitions.
- The context example is explicitly illustrative. Its displayed 54 → 27 word count is calculated from visible text; it is not a token benchmark or a simulated live engine result.
- Python code tabs, copy-install command, FAQs, and keyboard-dismissable mobile navigation are functional.
- Sarvam is a provider integration guide using the existing LLMSlim Python API and the official Sarvam SDK. No live authenticated Sarvam request was made during this website redesign.
- Existing docs, benchmarks, articles, Studio, and changelog remain available with shared visual styling.
- Sitemap source, robots source, SEO helpers, site metadata configuration, and Google verification assets were not changed. The existing sitemap generator automatically discovers the new Sarvam registry entry.

## Verification

- Production Next.js build passed, including TypeScript and all 30 generated entries.
- ESLint passed for all files edited by this redesign.
- All 23 distinct sitemap page paths and 12 homepage local links returned HTTP 200.
- robots.txt returned HTTP 200.
- Production homepage preserves H1, description, canonical, structured data, and Open Graph output.
- No production browser source maps were emitted.
- Homepage JavaScript: 206 KiB gzip including Next.js/React and existing analytics; no new runtime dependencies added.
- Desktop light/dark and 390px mobile light/dark views inspected in the browser; no broken images or horizontal page overflow.
- Theme switch, mobile menu/Escape, context example, Python tabs, FAQ, and Sarvam guide verified.
- Browser console inspection found no runtime warnings or errors.

The local production preview is started with `node node_modules/next/dist/bin/next start --port 3000` from `web/`. No public deployment was performed.

## October 2026 design system

- Palette: warm neutrals with one accent, vermilion (`#c2410c` light, `#ff7a3d` dark). No gradients on data.
- Type: Geist for text, Instrument Serif italic for emphasis in headings, Geist Mono for code and numbers. All three are self-hosted under `public/fonts` (OFL).
- Mark: the converging-lines logo drawn as one-colour SVG in the header (`Mark` in `SiteHeader.tsx`); the PNG stays for app icons.
- Photos from Pexels (free to use, Pexels license): the light-theme hero, programme and closing bands (Pexels 11705368, 10975806, 614115) and the Platform hero (1654138 by night, 32231937 by day).

### Startup program logos added on 2 November 2026

Downloaded with curl from each company's own site, CDN or media kit, checked as untrusted SVG (no scripts, event
handlers, `foreignObject`, external references or CSS imports) and copied byte for byte into `public/startups/`.

- Composio: `composio-black.svg` and `composio-white.svg` are https://composio.dev/logos/composio-full-black.svg and
  `.../composio-full-white.svg` (viewBox `0 0 483 93`).
- Snyk: Snyk has no public press kit (https://snyk.io/press-kit/ redirects to the contact page). The snyk.io header
  draws its wordmark as a CSS background from Snyk's own Cloudinary brand folder, and `snyk-dark-text.svg` and
  `snyk-white-text.svg` are that folder's `wordmark-light.svg` (text `#030328`, for light backgrounds) and
  `wordmark-dark.svg` (white text, for dark backgrounds):
  https://res.cloudinary.com/snyk/image/upload/snyk-mktg-brandui/brand-logos/wordmark-light.svg and `.../wordmark-dark.svg`.
  Both have the viewBox `0 0 77 52` with built-in padding: the letters fill about 60% of the height.
- Gitar: `gitar-wordmark.svg` is the sub-brand wordmark on https://www.sonarsource.com/products/gitar/ (gitar.ai now
  redirects there), served from Sonar's CDN at
  https://assets-eu-01.kc-usercontent.com/ef593040-b591-0198-9506-ed88b30bc023/22779193-4b6d-4bdf-a860-37007a6d2315/gitar-wordmark.svg.
  It is one colour, purple `#6D2A78`, and no white or dark variant is published. In its own dark mode Sonar shows this
  file through `brightness(0) invert`, so it is used here as a single-colour mark tinted to the text colour ("mask").
- Future AGI: no logo file or brand kit is published (futureagi.com/brand, /press, /media-kit and /brand-kit return
  404). `futureagi-symbol.svg` is https://futureagi.com/favicon.svg; its four paths are identical to the symbol in the
  site header (viewBox `0 0 47 47`). `futureagi-wordmark.svg` is the second inline `<svg>` of the futureagi.com header
  (`aria-label="FutureAGI"`, viewBox `54 12 139 23`, white letters), cut out of the served HTML byte for byte from
  `<svg` to `</svg>` with nothing added. Both are white or light grey, made for Future AGI's dark site, so they are
  used as masks tinted to the text colour.
- Notion: `notion-lockup.svg`, `notion-block.svg` and `notion-block-sticker-white.svg` are
  `notion-logo-lockup-main.svg`, `notion-logo-block-main.svg` and `notion-logo-block-sticker-white.svg` from
  `NotionLogoFiles.zip` in Notion's Media Kit (https://notion.notion.site/Media-Kit-205535b1d9c4440497a3d7a2ac096286,
  published by the "Notion Official" workspace). The kit has no reverse lockup: the lockup's "Notion" letters are
  black, so it only works on light backgrounds. The block's "N" is drawn in black on a white page, not cut out, so
  the block cannot be used as a mask either (it would become a solid square). The sticker variant adds a white
  outline for dark backgrounds.
- Nebius: `nebius.svg` is now `SVGs/NEBIUS-color.svg` from the logo pack on https://nebius.com/media-kit
  (https://assets.nebius.com/assets/2dd2ad13-45c1-4429-a47c-156bedd4d71d/NEBIUS-logos%2807.25%29%20%281%29.zip).
  The file it replaces had the same artwork with Illustrator's XML prolog, comment and `id` removed and the
  indentation changed; its source had not been recorded. The lime badge with deep-blue letters is the same in both
  themes, so it needs no dark variant.
