# LLMSlim website redesign

The landing page follows the user's Raycast reference: a cinematic composition, custom dimensional artwork, concise product copy, and open layouts rather than a grid of promotional cards. Light and dark modes use separate artwork and shared semantic theme tokens. The existing theme persistence script and SEO infrastructure remain in place.

## Assets

- `public/compression-ribbon-dark.webp` — custom 3D artwork, 1536 × 1024, 167,482 bytes.
- `public/compression-ribbon-light.webp` — matching light treatment, 1536 × 1024, 95,156 bytes.
- `public/llmslim_logo.png` — existing official LLMSlim logo, unchanged.
- `public/sarvam-symbol.svg` — official Sarvam flower mark.
- `public/sarvam-wordmark.svg` — official Sarvam wordmark.
- `public/fonts/geist-latin.woff2` — self-hosted variable font; license in `public/fonts/OFL.txt`.

Sarvam assets came from its public brand website. The co-brand arrangement and acceptance wording follow the user's supplied `Untitled design (8).png` reference. Both brands remain independently identifiable.

Sources:
- https://www.raycast.com/
- https://www.box.com/
- https://www.sarvam.ai/brand-guidelines
- https://assets.sarvam.ai/tr:dpr-auto/assets/brand/logos/sarvam-logo-black.svg
- https://assets.sarvam.ai/tr:dpr-auto/assets/brand/logos/sarvam-wordmark-black.svg
- https://docs.sarvam.ai/api-reference/chat/chat-completions

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
