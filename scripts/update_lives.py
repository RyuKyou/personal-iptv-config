#!/usr/bin/env python3
"""
Fetch public M3U sources, filter Chinese-related channels
(Mainland / Taiwan / Singapore focus), basic alive check,
deduplicate, sort by name, generate cleaned lives.
"""

import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources" / "live_repos.txt"
OUTPUT_M3U = ROOT / "lives" / "chinese.m3u"
TVBOX_JSON = ROOT / "tvbox.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IPTV-Updater/1.0)"}
TIMEOUT = 12

KEEP_KEYWORDS = [
    "央视", "卫视", "中国", "大陸", "大陆", "台灣", "台湾", "singapore", "新加坡", "日本", "japan",
    "tvb", "鳳凰", "凤凰", "中天", "东森", "民视", "三立", "tvbs", "華視", "公视",
    "cgtn", "香港", "古装", "華語", "华语", "喜剧", "成龙", "周润发", "刘德华", "周星驰", "甄子丹", "洪金宝", "林正英", "电影", "武侠", "狄仁杰", "纪晓岚", "電影",
]

def normalize_name(name: str) -> str:
    """Normalize for deduplication."""
    name = name.lower().strip()
    name = re.sub(r"\s+", "", name)
    name = re.sub(r"[\-_|【】\[\]()（）]", "", name)
    name = re.sub(r"(hd|4k|1080p|720p|高清|超清|蓝光)", "", name)
    return name

def is_chinese_related(name: str) -> bool:
    name_lower = name.lower()
    return any(k.lower() in name_lower for k in KEEP_KEYWORDS)

def fetch_text(url: str) -> str | None:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None

def parse_m3u(content: str):
    lines = content.splitlines()
    name = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            if "," in line:
                name = line.split(",", 1)[1].strip()
            else:
                name = "Unknown"
        elif line and not line.startswith("#") and name:
            yield name, line
            name = None

def basic_alive(url: str) -> bool:
    try:
        req = Request(url, method="HEAD", headers=HEADERS)
        with urlopen(req, timeout=6) as resp:
            return 200 <= resp.status < 400
    except Exception:
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=6) as resp:
                return 200 <= resp.status < 400
        except Exception:
            return False

def main():
    print("Reading source list...")
    sources = []
    for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, url = line.split("|", 1)
            sources.append((name.strip(), url.strip()))

    # Collect with URL + name-based dedup
    seen_urls = set()
    seen_names = set()
    collected = []

    for src_name, src_url in sources:
        print(f"Fetching {src_name}...")
        content = fetch_text(src_url)
        if not content:
            continue
        count = 0
        for name, url in parse_m3u(content):
            if not is_chinese_related(name):
                continue
            if url in seen_urls:
                continue
            norm = normalize_name(name)
            if norm in seen_names:
                continue
            seen_urls.add(url)
            seen_names.add(norm)
            collected.append((name, url))
            count += 1
        print(f"  Added {count} unique Chinese-related entries")

    print(f"Total unique candidates: {len(collected)}")

    print("Running basic alive checks...")
    alive = []
    for i, (name, url) in enumerate(collected):
        if i > 0 and i % 30 == 0:
            print(f"  Checked {i}/{len(collected)}...")
            time.sleep(0.3)
        if basic_alive(url):
            alive.append((name, url))

    print(f"Alive after check: {len(alive)}")

    # Sort by name
    alive.sort(key=lambda x: x[0].lower())

    # Write M3U
    OUTPUT_M3U.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_M3U.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in alive:
            f.write(f"#EXTINF:-1,{name}\n{url}\n")
    print(f"Wrote {OUTPUT_M3U} ({len(alive)} channels, sorted by name)")

    # Do not overwrite the full tvbox.json lives here, keep user curated ones
    print("Done.")

if __name__ == "__main__":
    main()
