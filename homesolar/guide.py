"""Load installer-guide Markdown pages (with a small front-matter block)."""
from functools import lru_cache
import markdown

from .config import CONTENT


def _parse(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---"):
        _, head, body = text.split("---", 2)
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
        return meta, body
    return meta, text


@lru_cache
def pages() -> list[dict]:
    out = []
    for f in (CONTENT / "guide").glob("*.md"):
        meta, body = _parse(f.read_text(encoding="utf-8"))
        out.append({"slug": f.stem, "title": meta.get("title", f.stem), "summary": meta.get("summary", ""),
                    "order": int(meta.get("order", 99)), "html": markdown.markdown(body)})
    return sorted(out, key=lambda p: p["order"])


def page(slug: str) -> dict | None:
    return next((p for p in pages() if p["slug"] == slug), None)
