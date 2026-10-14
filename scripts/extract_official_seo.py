"""Extract SEO meta from official-web static mirrors into JSON."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "official-web" / "sites"
SITES = ["qlyc", "yizhichan", "jinanyunji", "qinghuicai"]


def extract(html: str) -> dict:
    def one(pattern: str) -> str:
        match = re.search(pattern, html, re.I | re.S)
        return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""

    title = one(r"<title>(.*?)</title>")
    description = one(r'name=["\']description["\']\s+content=["\'](.*?)["\']')
    if not description:
        description = one(r'content=["\'](.*?)["\']\s+name=["\']description["\']')
    keywords = one(r'name=["\']keywords["\']\s+content=["\'](.*?)["\']')
    if not keywords:
        keywords = one(r'content=["\'](.*?)["\']\s+name=["\']keywords["\']')
    json_ld = one(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>')
    return {
        "seoTitle": title,
        "seoDescription": description,
        "seoKeywords": keywords,
        "jsonLd": json_ld,
    }


def main() -> None:
    result = {}
    for key in SITES:
        index = ROOT / key / "index.html"
        robots = ROOT / key / "robots.txt"
        sitemap = ROOT / key / "sitemap.xml"
        item = extract(index.read_text(encoding="utf-8", errors="ignore")) if index.exists() else {}
        item["robotsTxt"] = robots.read_text(encoding="utf-8", errors="ignore").strip() if robots.exists() else ""
        item["hasSitemap"] = sitemap.exists()
        if sitemap.exists():
            locs = re.findall(r"<loc>(.*?)</loc>", sitemap.read_text(encoding="utf-8", errors="ignore"))
            item["sitemapSample"] = locs[:5]
            item["sitemapCount"] = len(locs)
        result[key] = item
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
