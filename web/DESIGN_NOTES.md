# LLMSlim website redesign

The landing page follows the user's Raycast reference: a cinematic composition, custom dimensional artwork, concise product copy, and open layouts rather than a grid of promotional cards. Light and dark modes use separate artwork and shared semantic theme tokens. The existing theme persistence script and SEO infrastructure remain in place.

## Assets

- `public/compression-ribbon-dark.webp`: custom 3D artwork, 1536 × 1024, 167,482 bytes.
- `public/compression-ribbon-light.webp`: matching light treatment, 1536 × 1024, 95,156 bytes.
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

## Generation prompts

Both artwork variants were generated using the built-in image-generation tool, then encoded as WebP using Sharp. No image-generation API key or runtime image generation is required by the website.

### Dark artwork

Use case: stylized-concept. Asset type: premium 3D brand artwork for LLMSlim, an AI context compression developer tool. Create a museum-quality Octane/Cinema4D render of five broad, substantial sculptural ribbons made of glossy polished glass and titanium, sweeping from upper left and gracefully converging into three precisely aligned continuous ribbons toward lower right, communicating compression and flow. A single elegant coherent sculptural form, not scattered objects. Iridescent cobalt blue, electric cyan, subtle violet and emerald-green reflections from the LLMSlim logo. Macro product-photography quality, real depth, smooth bevels, exceptional refraction and specular highlights. The ribbons form a loose twisting S through the frame. Mostly near-black metallic sides with luminous blue-green glass edges. Strong dynamic diagonal perspective, sophisticated industrial design, dramatic studio rim lighting, entirely isolated on an ACTUAL TRANSPARENT BACKGROUND with alpha, no checkerboard pattern. Wide landscape 1536x1024 composition, sculpture fills 85% of frame with margins, no hard cropping. Designed to layer behind or alongside website typography on both near-black and white backgrounds. No text, no letters, no UI, no logo, no extra particles, no stars, no planets, no rectangular cards, no platforms, no boxes, no gradients in the background. This must feel like expensive art direction for a premium developer product similar in execution quality to Raycast.

### Light artwork

Create the matching LIGHT MODE version of this exact premium 3D brand render. Preserve the sculpture's exact shape, placement, flowing five ribbons merging to three, camera angle, and composition. Change only studio lighting and background: pure white #ffffff seamless background all the way to every edge, natural diffuse studio shadows, bright polished silver titanium and clear glass with beautiful cobalt blue, violet, cyan and emerald edge refraction. High-end industrial product render on white, brighter material. No black background, no text, no new objects. Wide landscape same dimensions. This image must sit seamlessly on a white website.

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
