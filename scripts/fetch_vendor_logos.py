#!/usr/bin/env python3
"""Vendor marks from Lobe Icons, kept local so the chart needs no image CDN."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "vendors"
BASE = "https://raw.githubusercontent.com/lobehub/lobe-icons/master/"
ICONS = ["openai", "anthropic", "google-color", "meta-color", "moonshot", "qwen-color", "deepseek-color", "mistral-color", "minimax-color", "microsoft-color", "xai", "zai", "stepfun-color"]


def fetch(name):
    try:
        with urlopen(BASE + f"packages/static-svg/icons/{name}.svg", timeout=30) as response:
            data = response.read()
        if b"<svg" not in data or b"<script" in data or b"<foreignObject" in data:
            raise ValueError("Unexpected SVG contents")
        (ROOT / f"{name}.svg").write_bytes(data)
        return f"Saved {name}"
    except Exception as exc:
        return f"Monogram fallback for {name}: {type(exc).__name__}"


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(fetch, ICONS):
            print(result)
    with urlopen(BASE + "LICENSE", timeout=30) as response:
        (ROOT / "LICENSE").write_bytes(response.read())
