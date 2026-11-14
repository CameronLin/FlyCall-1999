"""Assemble outputs/FlyCall-1999_專案介紹.html from the sources in docs/intro/.

Edit the small files under docs/intro/ (tabs, sections, css, js) and run:

    python scripts/build_intro_html.py            # write the page
    python scripts/build_intro_html.py --check    # exit 1 if the page is out of date

Markers in the sources:
    <!--INCLUDE:path-->   replaced by docs/intro/<path> (recursively)
    <!--DATA:bfs-->       docs/intro/data/bfs_data.json (made by scripts/build_intro_bfs_data.py)
    <!--DATA:figures-->   brain-comparison PNGs from the run folders in FIGURE_SETS, as lossless WebP data URIs
    <!--DATA:signal-->    outputs/FlyCall-1999_連接圖訊號傳遞.html, base64 (shown in an iframe)
"""
import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/intro"
OUT = ROOT / "outputs/FlyCall-1999_專案介紹.html"
SIGNAL = ROOT / "outputs/FlyCall-1999_連接圖訊號傳遞.html"
RUNS = ROOT / ".scratch/1999-connectome-demo/runs"

# figure set id -> run folder holding the 17 brain-comparison PNGs (same ids as build_intro_brain_section.py)
FIGURE_SETS = {
    "v1-t2": "fly-ab-brain-comparison-t-hops-20261113",
    "v1-t4": "fly-ab-brain-comparison-t4-20261113",
    "v2-t2": "fly-ab-brain-comparison-v2-t2-20261114",
    "v2-t4": "fly-ab-brain-comparison-v2-t4-20261114",
}
FIGURE_NAMES = [f"{g}_{obj}_{kind}" for g in ("G0", "G2") for obj in ("distance", "distance_supcon")
                for kind in ("hist_edge_change", "scatter_edge_a_vs_b", "hist_class_selectivity", "scatter_lesion")]
SUMMARY = ("all_all_summary", "summary_similarity_vs_seed_baseline.png")

INCLUDE = re.compile(r"<!--INCLUDE:([\w./-]+)-->\n?")


def include(text, depth=0):
    if depth > 5:
        raise RuntimeError("include nesting too deep")

    def repl(m):
        body = (SRC / m.group(1)).read_text(encoding="utf-8")
        return include(body, depth + 1)
    return INCLUDE.sub(repl, text)


def data_uri(path):
    """PNG -> lossless WebP data URI (about a third of the size, pixel-identical)."""
    buf = io.BytesIO()
    Image.open(path).save(buf, "WEBP", lossless=True, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def figures():
    out = {}
    for set_id, folder in FIGURE_SETS.items():
        run = RUNS / folder
        for name in FIGURE_NAMES:
            out[f"{set_id}/{name}"] = data_uri(run / f"{name}.png")
        out[f"{set_id}/{SUMMARY[0]}"] = data_uri(run / SUMMARY[1])
    return json.dumps(out)


def build():
    page = (SRC / "page.html").read_text(encoding="utf-8")
    # the page.html markers sit between tags, so restore the exact original line breaks
    page = include(page)
    page = page.replace("<!--DATA:bfs-->", (SRC / "data/bfs_data.json").read_text(encoding="utf-8"))
    page = page.replace("<!--DATA:figures-->", figures())
    page = page.replace("<!--DATA:signal-->", json.dumps(base64.b64encode(SIGNAL.read_bytes()).decode("ascii")))
    if "<!--INCLUDE:" in page or "<!--DATA:" in page:
        raise RuntimeError("unresolved marker")
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only compare with the existing page")
    args = ap.parse_args()
    page = build()
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == page
        print("up to date" if same else "out of date")
        sys.exit(0 if same else 1)
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page.encode()):,} bytes)")


if __name__ == "__main__":
    main()
