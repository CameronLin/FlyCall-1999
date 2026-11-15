"""Build the project briefing deck and its speaker notes from docs/briefing/deck.html.

    python scripts/build_briefing_html.py          write both outputs
    python scripts/build_briefing_html.py --check  exit 1 if the outputs are out of date

Outputs:
    outputs/FlyCall-1999_專案簡報.html        self-contained slide deck (open in a browser; N = notes, F = fullscreen)
    outputs/FlyCall-1999_專案簡報_講稿.md     the <aside class="notes"> of every slide, as Markdown

Markers in the source:
    <!--DATA:bfs-->          docs/intro/data/bfs_data.json (same data as the intro page's BFS animation)
    <!--DATA:fig:NAME-->     NAME.png from the v2・T=2 brain-comparison run, as a lossless WebP data URI
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_intro_html import data_uri  # noqa: E402

SRC = ROOT / "docs/briefing/deck.html"
BFS = ROOT / "docs/intro/data/bfs_data.json"
FIG_RUN = ROOT / ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-v2-t2-20261114"
OUT_HTML = ROOT / "outputs/FlyCall-1999_專案簡報.html"
OUT_NOTES = ROOT / "outputs/FlyCall-1999_專案簡報_講稿.md"


def build_html(src):
    figs = {}

    def fig(m):
        name = m.group(1)
        if name not in figs:
            figs[name] = data_uri(FIG_RUN / f"{name}.png")
        return figs[name]

    out = re.sub(r"<!--DATA:fig:([\w-]+)-->", fig, src)
    out = out.replace("<!--DATA:bfs-->", BFS.read_text(encoding="utf-8").strip())
    if "<!--DATA:" in out:
        raise SystemExit("unresolved DATA marker in " + str(SRC))
    return out


def text(fragment):
    fragment = re.sub(r"<li>\s*", "- ", fragment)
    fragment = re.sub(r"</(p|li|ul|ol)>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    lines = [html.unescape(line).strip() for line in fragment.splitlines()]
    return "\n\n".join(line for line in lines if line)


def build_notes(src):
    parts = ["# FlyCall-1999 專案簡報・講稿", "",
             "由 `docs/briefing/deck.html` 自動產生（`python scripts/build_briefing_html.py`），請改原始檔，不要直接改這份。", ""]
    slides = re.findall(r'<section class="slide[^"]*" data-title="([^"]+)"[^>]*>(.*?)</section>', src, flags=re.S)
    for i, (title, body) in enumerate(slides, 1):
        m = re.search(r'<aside class="notes">(.*?)</aside>', body, flags=re.S)
        parts += [f"## 第 {i} 頁｜{title}", "", text(m.group(1)) if m else "（沒有講稿）", ""]
    return "\n".join(parts)


def main():
    src = SRC.read_text(encoding="utf-8")
    outputs = {OUT_HTML: build_html(src), OUT_NOTES: build_notes(src)}
    if "--check" in sys.argv:
        stale = [p for p, c in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
        for p in stale:
            print("out of date:", p.relative_to(ROOT))
        sys.exit(1 if stale else 0)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
