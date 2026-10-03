#!/usr/bin/env python3
"""远程存证脚本：Internet Archive 备份。

用法:
  python3 scripts/attest.py --archive

环境变量:
  SITE_URL            站点根 URL（默认 https://seed-trilogy.com.cn）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMESTAMPS = ROOT / "public" / "downloads" / "timestamps.json"
MANIFEST = ROOT / "public" / "downloads" / "manifest.json"


# ─── Internet Archive 备份 ─────────────────────────────────────────────────

SITE_PAGES = [
    "/",
    "/download/",
    "/about/",
    "/rights/",
    "/characters/",
    "/appendices/",
    "/illustrations/",
    "/sign/",
    "/notes/",
    "/blog/",
]


def archive_page(full_url: str, retries: int = 3) -> tuple[bool, str]:
    """提交页面到 Wayback Machine，失败自动重试。"""
    save_url = f"https://web.archive.org/save/{full_url}"
    last_err = ""
    for attempt in range(retries):
        req = urllib.request.Request(save_url, method="POST", headers={
            "User-Agent": "seed-trilogy-archiver/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                archived = resp.headers.get("Content-Location", "")
                if archived:
                    return True, f"https://web.archive.org{archived}"
                return True, "submitted"
        except urllib.error.HTTPError as e:
            if e.code in (302, 405):
                loc = e.headers.get("Location", "")
                if loc:
                    return True, loc
            last_err = f"HTTP {e.code}"
        except Exception as e:
            last_err = str(e)[:100]
        if attempt < retries - 1:
            time.sleep(5)
    return False, last_err


def do_archive(site_url: str) -> int:
    print(f"\n{'='*60}\n  Internet Archive 备份（Wayback Machine）\n{'='*60}")
    ok = 0
    for page in SITE_PAGES:
        full = site_url.rstrip("/") + page
        success, msg = archive_page(full)
        status = "✓" if success else "✗"
        print(f"  {status} {page:20s} → {msg}")
        if success:
            ok += 1
        time.sleep(3)  # IA 限速
    print(f"\n  Internet Archive 完成: {ok}/{len(SITE_PAGES)}")
    # 部分成功也视为成功，未归档的页面可后续手动补充
    if ok > 0:
        print("  ✓ 至少一个页面已归档，视为成功")
        return 0
    return 1


# ─── 主入口 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="远程存证：Internet Archive 备份")
    parser.add_argument("--archive", action="store_true", help="Internet Archive 备份")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", "https://seed-trilogy.com.cn"))
    args = parser.parse_args()

    if not args.archive:
        parser.print_help()
        sys.exit(0)

    print(f"\n{'='*60}\n  汇总\n{'='*60}")
    code = do_archive(args.site_url)
    label = "✓ 成功" if code == 0 else ("⚠ 部分" if code == 1 else "⊘ 跳过")
    print(f"  {'archive':15s} {label}")

    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    main()
