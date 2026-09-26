#!/usr/bin/env python3
"""
Fetch public M3U sources, filter Chinese-related channels
(Mainland / Taiwan / Singapore focus), basic alive check,
generate cleaned lives and update tvbox.json
"""

import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources" / "live_repos.txt"
OUTPUT_M3U = ROOT / "lives" / "chinese.m3u"
TVBOX_JSON = ROOT / "tvbox.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IPTV-Updater/1.0)"}
TIMEOUT = 12

# Keywords to keep (Chinese media focus)
KEEP_KEYWORDS = [
    "cctv", "央视", "卫视", "中国", "大陸", "大陆", "台灣", "台湾", "singapore", "新加坡",
    "tvb", "鳳凰", "凤凰", "中天", "东森", "民视", "三立", "tvbs", "華視", "公视",
    "cgtn", "香港", "澳门", "華語", "华语", "中文","周潤發","周润发","刘德华","周星驰","沈腾","林正英","成龙","甄子丹","洪金宝"
]

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
    """Yield (name, url) pairs from M3U content."""
    lines = content.splitlines()
    name = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            # Extract name after the last comma
            if "," in line:
                name = line.split(",", 1)[1].strip()
            else:
                name = "Unknown"
        elif line and not line.startswith("#") and name:
            yield name, line
            name = None

def basic_alive(url: str) -> bool:
    """Very lightweight check."""
    try:
        req = Request(url, method="HEAD", headers=HEADERS)
        with urlopen(req, timeout=6) as resp:
            return 200 <= resp.status < 400
    except Exception:
        # Some servers don't support HEAD well, try short GET
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

    collected = []  # list of (name, url)
    seen_urls = set()

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
            seen_urls.add(url)
            collected.append((name, url))
            count += 1
        print(f"  Added {count} Chinese-related entries")

    print(f"Total unique candidates: {len(collected)}")

    # Light alive filter (only check a portion to save time)
    print("Running basic alive checks (this may take a while)...")
    alive = []
    for i, (name, url) in enumerate(collected):
        if i > 0 and i % 30 == 0:
            print(f"  Checked {i}/{len(collected)}...")
            time.sleep(0.3)
        if basic_alive(url):
            alive.append((name, url))

    print(f"Alive after check: {len(alive)}")

    # Write standalone M3U
    OUTPUT_M3U.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_M3U.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in alive:
            f.write(f"#EXTINF:-1,{name}\n{url}\n")
    print(f"Wrote {OUTPUT_M3U}")

    # Update tvbox.json lives section
    if TVBOX_JSON.exists():
        data = json.loads(TVBOX_JSON.read_text(encoding="utf-8"))
    else:
        data = {"lives": []}

    # Keep a simple structure: one main Chinese live entry pointing to our generated file
    # + fallback to a couple of public ones
    new_lives = [
        {
            "name": "中文精选(自动更新)",
            "type": 0,
            "url": "https://raw.githubusercontent.com/RyuKyou/personal-iptv-config/main/lives/chinese.m3u",
            "playerType": 2
        },
        {
            "name": "备用-CollectIPTV",
            "type": 0,
            "url": "https://raw.githubusercontent.com/zilong7728/Collect-IPTV/main/best_sorted.m3u",
            "playerType": 2
        }
    ]

    data["lives"] = new_lives
    TVBOX_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated tvbox.json lives section")

    print("Done.")

if __name__ == "__main__":
    main()
