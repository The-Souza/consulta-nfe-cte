"""Download Lucide icons and render them as white PNGs into assets/icons/.

Dev-only script (needs resvg-py from requirements-dev.txt). The generated PNGs are committed,
so neither CI nor the build needs to render SVG. Colors are applied at load time by ui/icons.py.

Usage: .venv\\Scripts\\python.exe tools\\render_icons.py
"""

import urllib.request
from pathlib import Path

import resvg_py

LUCIDE_VERSION = "1.66.0"
BASE_URL = f"https://cdn.jsdelivr.net/npm/lucide-static@{LUCIDE_VERSION}"
SIZE_PX = 48

ICONS = [
    "chevron-down",
    "chevron-left",
    "chevron-right",
    "cloud",
    "download",
    "eye",
    "eye-off",
    "file-check",
    "file-search",
    "funnel",
    "log-out",
    "rotate-cw",
    "search",
    "square",
    "upload",
    "wifi-off",
    "x",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def render(svg: str) -> bytes:
    white_svg = svg.replace("currentColor", "#ffffff")
    return bytes(resvg_py.svg_to_bytes(svg_string=white_svg, width=SIZE_PX, height=SIZE_PX))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ICONS:
        png = render(_fetch(f"{BASE_URL}/icons/{name}.svg"))
        (OUTPUT_DIR / f"{name}.png").write_bytes(png)
        print(f"{name}.png")
    (OUTPUT_DIR / "LICENSE").write_text(_fetch(f"{BASE_URL}/LICENSE"), encoding="utf-8")
    print(f"LICENSE (lucide-static {LUCIDE_VERSION})")


if __name__ == "__main__":
    main()
