"""Build the LLMSlim brand files: mark, lockups, app icon and share image, as SVG.

Usage (from web/): python scripts/brand/build_assets.py . && node scripts/brand/icons.mjs . scripts/brand
                    && python scripts/brand/favicon.py .
Needs fonttools and brotli. Writes public/brand/*.svg, scripts/brand/og.svg and mark-component.json; then
regenerate src/components/brand/mark-data.ts from mark-component.json if the geometry changed.
"""
import json
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

WEB = Path(sys.argv[1])
sys.argv = [sys.argv[0], "1.0"]
exec(Path(__file__).with_name("mark_geometry.py").read_text().split("if __name__")[0])

OUT = WEB / "public" / "brand"
OUT.mkdir(parents=True, exist_ok=True)

# The mark's own box in the icon frame (left cap edge to right edge, top of strand 1 to bottom of strand 5).
MX0, MY0, MX1, MY1 = 108.0, 136.0, 391.0, 337.5
MW, MH = MX1 - MX0, MY1 - MY0

PALETTES = {
    # sampled from the founder's brand sheet
    "dark": dict(left=["#5C50FD", "#477BFD", "#2A98FA", "#00D0A8", "#00E686"],
                 right=["#04CDAD", "#01DB9B", "#01DB9B", "#01DB9B", "#00EA88"],
                 end=["#00D9A2", "#02E18F", "#02E18F", "#02E18F", "#00E789"]),
    # the same hues, deepened so the green strands hold up on light backgrounds
    "light": dict(left=["#4A3DF0", "#2F67EE", "#1083E6", "#00A98A", "#00B26C"],
                  right=["#00A894", "#00AE82", "#00AE82", "#00AE82", "#00B46E"],
                  end=["#00B08C", "#00B57A", "#00B57A", "#00B57A", "#00B86C"]),
}


def mark(prefix, palette="dark", mono=None):
    """Gradient defs and a <g> drawing the mark with its top-left at (0, 0), MW x MH units."""
    pal = PALETTES[palette]
    x0, x1 = X_LEFT - W_LEFT / 2, X_END
    defs, paths = [], []
    for i in range(5):
        if mono is None:
            o1 = (FITS[i]["xs"] - x0) / (x1 - x0)
            o2 = (FITS[i]["xe"] - x0) / (x1 - x0)
            defs.append(
                f'<linearGradient id="{prefix}{i}" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x1}" y2="0">'
                f'<stop offset="{o1:.3f}" stop-color="{pal["left"][i]}"/>'
                f'<stop offset="{o2:.3f}" stop-color="{pal["right"][i]}"/>'
                f'<stop offset="1" stop-color="{pal["end"][i]}"/></linearGradient>'
            )
    for i in [0, 4, 1, 3, 2]:
        fill = mono if mono else f"url(#{prefix}{i})"
        paths.append(f'<path fill="{fill}" d="{strand(FITS[i])}"/>')
    return "".join(defs), f'<g transform="translate({-MX0} {-MY0})">{"".join(paths)}</g>'


# --- wordmark from Geist, instanced at weight 500
font = instantiateVariableFont(TTFont(WEB / "public" / "fonts" / "geist-latin.woff2"), {"wght": 500})
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()
hmtx = font["hmtx"]
UPM = font["head"].unitsPerEm
CAP = font["OS/2"].sCapHeight


def text(s, size, x, baseline, tracking=-0.02):
    """SVG path data for s at font size `size`, starting at x on the given baseline. Returns (d, advance)."""
    scale = size / UPM
    d = []
    pen_x = x
    for ch in s:
        g = cmap[ord(ch)]
        sp = SVGPathPen(glyphs)
        glyphs[g].draw(TransformPen(sp, (scale, 0, 0, -scale, pen_x, baseline)))
        d.append(sp.getCommands())
        pen_x += hmtx[g][0] * scale + tracking * size
    return "".join(d), pen_x - x - tracking * size


INKS = {"dark": ("#FFFFFF", "#00F59B"), "light": ("#0B0D17", "#007A52"), "white": ("#FFFFFF", "#FFFFFF"),
        "black": ("#0B0D17", "#0B0D17")}


def lockup(variant, layout="horizontal"):
    """Mark plus wordmark. The mark is 1.46x the cap height, as on the brand sheet."""
    pal = "light" if variant in ("light", "black") else "dark"
    mono = {"white": "#FFFFFF", "black": "#0B0D17"}.get(variant)
    llm_ink, slim_ink = INKS[variant]
    cap_px = MH / 1.46
    size = cap_px / (CAP / UPM)
    defs, g = mark(f"lk{variant}{layout[0]}", pal, mono)
    if layout == "horizontal":
        gap = MH * 0.25
        tx = MW + gap
        base = MH / 2 + cap_px / 2
        d1, a1 = text("LLM", size, tx, base)
        d2, a2 = text("Slim", size, tx + a1 + 0.0 * size, base)
        w, h = tx + a1 + a2, MH
        body = g + f'<path fill="{llm_ink}" d="{d1}"/><path fill="{slim_ink}" d="{d2}"/>'
    else:
        size *= 0.62
        cap2 = CAP / UPM * size
        _, a1 = text("LLM", size, 0, 0)
        _, a2 = text("Slim", size, 0, 0)
        tw = a1 + a2
        w = max(MW, tw)
        h = MH + MH * 0.28 + cap2
        mx = (w - MW) / 2
        tx = (w - tw) / 2
        base = h
        d1, a1 = text("LLM", size, tx, base)
        d2, _ = text("Slim", size, tx + a1, base)
        body = (f'<g transform="translate({mx:.2f} 0)">{g}</g>'
                f'<path fill="{llm_ink}" d="{d1}"/><path fill="{slim_ink}" d="{d2}"/>')
    pad = MH * 0.04
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad:.2f} {-pad:.2f} {w + 2 * pad:.2f} {h + 2 * pad:.2f}">'
            f'<title>LLMSlim</title><defs>{defs}</defs>{body}</svg>')


def mark_svg(palette="dark", mono=None):
    defs, g = mark("mk", palette, mono)
    pad = 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {MW + 2 * pad} {MH + 2 * pad}">'
            f'<title>LLMSlim</title><defs>{defs}</defs>{g}</svg>')


def app_icon(size=512):
    defs, g = mark("ai", "dark")
    s = size
    r = s * 0.225
    scale = s * 0.58 / MW
    tx = (s - MW * scale) / 2
    ty = (s - MH * scale) / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}"><title>LLMSlim</title><defs>{defs}'
            f'<linearGradient id="tile" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0D1130"/>'
            f'<stop offset="1" stop-color="#05060F"/></linearGradient>'
            f'<radialGradient id="glow" cx="0.3" cy="0.25" r="0.75"><stop offset="0" stop-color="#5C50FD" stop-opacity="0.18"/>'
            f'<stop offset="1" stop-color="#5C50FD" stop-opacity="0"/></radialGradient></defs>'
            f'<rect width="{s}" height="{s}" rx="{r:.1f}" fill="url(#tile)"/>'
            f'<rect width="{s}" height="{s}" rx="{r:.1f}" fill="url(#glow)"/>'
            f'<rect x="1.5" y="1.5" width="{s - 3}" height="{s - 3}" rx="{r - 1.5:.1f}" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="3"/>'
            f'<g transform="translate({tx:.2f} {ty:.2f}) scale({scale:.4f})">{g}</g></svg>')


def og_image():
    W, H = 1200, 630
    lk = lockup("dark")
    inner = lk.split(">", 1)[1].rsplit("</svg>", 1)[0]
    vb = [float(v) for v in lk.split('viewBox="')[1].split('"')[0].split()]
    target_w = 640
    scale = target_w / vb[2]
    lx = (W - target_w) / 2 - vb[0] * scale
    ly = 190 - vb[1] * scale
    _, tw = text("Memory for AI agents that no LLM writes.", 40, 0, 0, tracking=-0.01)
    tag, _ = text("Memory for AI agents that no LLM writes.", 40, (W - tw) / 2, 470, tracking=-0.01)
    _, fw = text("Open source  ·  llmslim.app", 24, 0, 0, tracking=0)
    foot, _ = text("Open source  ·  llmslim.app", 24, (W - fw) / 2, 540, tracking=0)
    grid = "".join(f'<path d="M{x} 0V{H}" stroke="#FFFFFF" stroke-opacity="0.035"/>' for x in range(0, W + 1, 60))
    grid += "".join(f'<path d="M0 {y}H{W}" stroke="#FFFFFF" stroke-opacity="0.035"/>' for y in range(30, H + 1, 60))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><defs>'
            f'<radialGradient id="g1" cx="0.18" cy="0.12" r="0.7"><stop offset="0" stop-color="#5C50FD" stop-opacity="0.38"/><stop offset="1" stop-color="#5C50FD" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="g2" cx="0.88" cy="0.95" r="0.65"><stop offset="0" stop-color="#00F59B" stop-opacity="0.22"/><stop offset="1" stop-color="#00F59B" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="g3" cx="0.55" cy="0.45" r="0.5"><stop offset="0" stop-color="#4F8CFF" stop-opacity="0.14"/><stop offset="1" stop-color="#4F8CFF" stop-opacity="0"/></radialGradient>'
            f'</defs><rect width="{W}" height="{H}" fill="#060816"/>{grid}'
            f'<rect width="{W}" height="{H}" fill="url(#g1)"/><rect width="{W}" height="{H}" fill="url(#g2)"/><rect width="{W}" height="{H}" fill="url(#g3)"/>'
            f'<g transform="translate({lx:.2f} {ly:.2f}) scale({scale:.4f})">{inner}</g>'
            f'<path fill="#C9CEE6" d="{tag}"/><path fill="#7D84A6" d="{foot}"/></svg>')


def app_icon_bleed(size=180):
    """Square, no rounded corners: iOS applies its own mask, and transparent corners would show black."""
    body = app_icon(size)
    r = f'rx="{size * 0.225:.1f}" '
    body = body.replace(r + 'fill="url(#tile)"', 'fill="url(#tile)"').replace(r + 'fill="url(#glow)"', 'fill="url(#glow)"')
    return body.split('<rect x="1.5"')[0] + body.split('stroke-width="3"/>', 1)[1]


files = {
    "llmslim-mark.svg": mark_svg("dark"),
    "llmslim-mark-light.svg": mark_svg("light"),
    "llmslim-mark-white.svg": mark_svg(mono="#FFFFFF"),
    "llmslim-lockup-dark.svg": lockup("dark"),
    "llmslim-lockup-light.svg": lockup("light"),
    "llmslim-lockup-white.svg": lockup("white"),
    "llmslim-lockup-black.svg": lockup("black"),
    "llmslim-stacked-dark.svg": lockup("dark", "stacked"),
    "llmslim-stacked-light.svg": lockup("light", "stacked"),
    "llmslim-app-icon.svg": app_icon(),
}
for name, body in files.items():
    (OUT / name).write_text(body, encoding="utf-8")
Path(__file__).with_name("og.svg").write_text(og_image(), encoding="utf-8")  # rendered to public/og.png by icons.mjs
Path(__file__).with_name("app-icon-bleed.svg").write_text(app_icon_bleed(512), encoding="utf-8")
print(json.dumps({k: len(v) for k, v in files.items()}))

# For the React component: the five strand outlines, in the icon frame, with their gradient offsets.
x0 = X_LEFT - W_LEFT / 2
comp = {"box": [MX0, MY0, MW, MH], "x0": x0, "x1": X_END,
        "order": [0, 4, 1, 3, 2],
        "strands": [{"d": strand(FITS[i]),
                     "o1": round((FITS[i]["xs"] - x0) / (X_END - x0), 3),
                     "o2": round((FITS[i]["xe"] - x0) / (X_END - x0), 3)} for i in range(5)],
        "palettes": PALETTES}
Path(__file__).with_name("mark-component.json").write_text(json.dumps(comp))
