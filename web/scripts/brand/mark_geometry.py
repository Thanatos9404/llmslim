"""The LLMSlim mark as SVG outlines: five tapered strands converging into three lines.

The curve fits, widths and colours were measured from the founder's app icon and brand sheet (October 2026),
in the icon's 500 x 500 frame. build_assets.py turns them into the brand files.
"""

import math
import sys
from pathlib import Path

FITS = [  # from fit.py on the founder's app icon (500 x 500 frame)
    {"y0": 148.0, "y1": 220.0, "xs": 199, "xe": 303, "k": 0.45},
    {"y0": 192.5, "y1": 250.0, "xs": 225, "xe": 311, "k": 0.30},
    {"y0": 237.0, "y1": 250.0, "xs": 235, "xe": 311, "k": 0.30},
    {"y0": 281.0, "y1": 250.0, "xs": 223, "xe": 311, "k": 0.30},
    {"y0": 325.5, "y1": 279.0, "xs": 195, "xe": 309, "k": 0.55},
]
X_LEFT, X_RIGHT, X_END, CORNER = (
    120.0,
    388.0,
    391.0,
    3.0,
)  # left cap centre, right corner start, right edge
W_LEFT, W_RIGHT = 24.0, 16.0
PINCH = (
    0.68  # how far the travelling strands narrow; build_assets.py draws the brand files with 1.0
)
STEPS = 28


def bez(p, t):
    u = 1 - t
    return (
        u**3 * p[0][0] + 3 * u * u * t * p[1][0] + 3 * u * t * t * p[2][0] + t**3 * p[3][0],
        u**3 * p[0][1] + 3 * u * u * t * p[1][1] + 3 * u * t * t * p[2][1] + t**3 * p[3][1],
    )


# Normal thickness of the outer strands along their curve, measured on the founder's icon.
PROFILE = [
    (0, 24),
    (0.15, 21),
    (0.3, 16.5),
    (0.45, 11),
    (0.55, 8),
    (0.65, 6),
    (0.72, 6),
    (0.8, 8.5),
    (0.88, 13),
    (0.95, 16),
    (1, 16),
]


def _profile(t):
    for (t0, w0), (t1, w1) in zip(PROFILE, PROFILE[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return w0 + (w1 - w0) * u
    return PROFILE[-1][1]


def width(t, travel, pinch=PINCH):
    base = W_LEFT + (W_RIGHT - W_LEFT) * (3 * t * t - 2 * t**3)
    # strands that travel further pinch more; the near-straight middle strand barely pinches
    amount = pinch * min(1.0, travel / 50.0)
    return base - (base - _profile(t)) * amount


def strand(f, pinch=PINCH):
    y0, y1, xs, xe, k = f["y0"], f["y1"], f["xs"], f["xe"], f["k"]
    p = [(xs, y0), (xs + k * (xe - xs), y0), (xe - k * (xe - xs), y1), (xe, y1)]
    travel = abs(y1 - y0)
    pts = [((X_LEFT, y0), W_LEFT)]
    for i in range(STEPS + 1):
        t = i / STEPS
        pts.append((bez(p, t), width(t, travel, pinch)))
    pts.append(((X_RIGHT, y1), W_RIGHT))
    upper, lower = [], []
    for i, ((x, y), w) in enumerate(pts):
        a = pts[max(i - 1, 0)][0]
        b = pts[min(i + 1, len(pts) - 1)][0]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        upper.append((x + nx * w / 2, y + ny * w / 2))
        lower.append((x - nx * w / 2, y - ny * w / 2))

    def f2(v):
        return f"{v:.2f}".rstrip("0").rstrip(".")

    d = f"M{f2(upper[0][0])} {f2(upper[0][1])}"
    for x, y in upper[1:]:
        d += f"L{f2(x)} {f2(y)}"
    hw = W_RIGHT / 2
    d += f"Q{f2(X_END)} {f2(y1 + hw)} {f2(X_END)} {f2(y1 + hw - CORNER)}L{f2(X_END)} {f2(y1 - hw + CORNER)}"
    d += f"Q{f2(X_END)} {f2(y1 - hw)} {f2(lower[-1][0])} {f2(lower[-1][1])}"
    for x, y in reversed(lower[:-1]):
        d += f"L{f2(x)} {f2(y)}"
    d += f"A{f2(W_LEFT / 2)} {f2(W_LEFT / 2)} 0 0 0 {f2(upper[0][0])} {f2(upper[0][1])}Z"
    return d


# Colours sampled from the brand sheet's large lockup.
LEFT = ["#5C50FD", "#477BFD", "#2A98FA", "#00D0A8", "#00E686"]
RIGHT = ["#04CDAD", "#01DB9B", "#01DB9B", "#01DB9B", "#00EA88"]
END = ["#00D9A2", "#02E18F", "#02E18F", "#02E18F", "#00E789"]


def svg(frame=(0, 0, 500, 500), bg=None, ids="m", pinch=PINCH):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(str(v) for v in frame)}">',
        "<defs>",
    ]
    x0, x1 = X_LEFT - W_LEFT / 2, X_END
    for i in range(5):
        o1 = (FITS[i]["xs"] - x0) / (x1 - x0)
        o2 = (FITS[i]["xe"] - x0) / (x1 - x0)
        parts.append(
            f'<linearGradient id="{ids}{i}" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x1}" y2="0">'
            f'<stop offset="{o1:.3f}" stop-color="{LEFT[i]}"/><stop offset="{o2:.3f}" stop-color="{RIGHT[i]}"/>'
            f'<stop offset="1" stop-color="{END[i]}"/></linearGradient>'
        )
    parts.append("</defs>")
    if bg:
        parts.append(bg)
    for i in [0, 4, 1, 3, 2]:
        parts.append(f'<path fill="url(#{ids}{i})" d="{strand(FITS[i], pinch)}"/>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    pinch = float(sys.argv[1]) if len(sys.argv) > 1 else PINCH
    out = sys.argv[2] if len(sys.argv) > 2 else "mark-500.svg"
    Path(out).write_text(svg(pinch=pinch))
