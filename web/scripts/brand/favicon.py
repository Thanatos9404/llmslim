"""Pack the rendered icon sizes into src/app/favicon.ico. Run after icons.mjs. Needs Pillow."""
import sys
from pathlib import Path

from PIL import Image

web = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
here = Path(__file__).parent
sizes = (256, 64, 48, 32, 16)
images = [Image.open(here / f"ico-{s}.png").convert("RGBA") for s in sizes]
images[0].save(web / "src" / "app" / "favicon.ico", sizes=[(s, s) for s in sorted(sizes)], append_images=images[1:])
