#!/usr/bin/env python3
"""远程存证脚本：IPFS 远程固定 + Arweave 永久存储 + Internet Archive 备份。

用法:
  python3 scripts/attest.py --ipfs --arweave --archive

环境变量:
  PINATA_JWT          Pinata JWT 令牌（IPFS 远程固定）
  ARWEAVE_WALLET      Arweave 钱包 JWK JSON 内容（Arweave 永久存储）
  SITE_URL            站点根 URL（Internet Archive 备份，默认从 astro.config 读取）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import base64
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMESTAMPS = ROOT / "public" / "downloads" / "timestamps.json"
MANIFEST = ROOT / "public" / "downloads" / "manifest.json"


# ─── IPFS 远程固定（Pinata）────────────────────────────────────────────────

def pin_ipfs(cid_v1: str, name: str) -> tuple[bool, str]:
    """通过 Pinata API 按 CID 固定（无需重新上传文件）。"""
    jwt = os.environ.get("PINATA_JWT", "").strip()
    if not jwt:
        return False, "PINATA_JWT 未设置"

    url = "https://api.pinata.cloud/pinning/pinByHash"
    payload = json.dumps({"hashToPin": cid_v1, "pinataMetadata": {"name": name}}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            return True, body.get("id", "ok")
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        # 已经 pin 过的会返回冲突，视为成功
        if e.code == 409 or "already" in detail.lower():
            return True, f"already pinned: {detail[:80]}"
        return False, f"HTTP {e.code}: {detail}"


def do_ipfs() -> int:
    """固定 timestamps.json 中所有文件的 CID。"""
    data = json.loads(TIMESTAMPS.read_text())
    records = data["records"]
    print(f"\n{'='*60}\n  IPFS 远程固定（Pinata）\n{'='*60}")
    ok = 0
    for r in records:
        cid = r["cid"]["v1"]
        name = Path(r["file"]).name
        success, msg = pin_ipfs(cid, name)
        status = "✓" if success else "✗"
        print(f"  {status} {name[:30]:30s} {cid[:20]}... → {msg}")
        if success:
            ok += 1
        time.sleep(0.5)
    print(f"\n  IPFS 固定完成: {ok}/{len(records)}")
    return 0 if ok == len(records) else 1


# ─── Arweave 永久存储 ──────────────────────────────────────────────────────

def arweave_upload(file_path: Path, wallet: dict) -> tuple[bool, str]:
    """上传文件到 Arweave，返回交易 ID。"""
    file_data = file_path.read_bytes()
    # 使用 arweave-js 兼容的 HTTP API
    # 简化版：直接调用 arweave.net 的 tx 端点（需要本地签名）
    # 完整实现需要 arweave 库或手动签名，这里使用 REST API 上传已签名的交易
    return False, "Arweave 上传需要 arweave Python 库，请用 npm 脚本或手动上传"


def do_arweave() -> int:
    print(f"\n{'='*60}\n  Arweave 永久存储\n{'='*60}")
    wallet_b64 = os.environ.get("ARWEAVE_WALLET", "").strip()
    if not wallet_b64:
        print("  ✗ ARWEAVE_WALLET 未设置，跳过")
        print("  提示: 在 GitHub Secrets 中添加 ARWEAVE_WALLET（JWK JSON 的 base64 编码）")
        return 2

    try:
        wallet = json.loads(base64.b64decode(wallet_b64))
    except Exception as e:
        print(f"  ✗ ARWEAVE_WALLET 解析失败: {e}")
        return 1

    # 检查 arweave 库
    try:
        from arweave import Wallet  # type: ignore
    except ImportError:
        print("  安装 arweave 库...")
        os.system(f"{sys.executable} -m pip install arweave-python-client -q")
        from arweave import Wallet  # type: ignore

    data = json.loads(TIMESTAMPS.read_text())
    records = data["records"]
    w = Wallet(wallet)
    ok = 0
    for r in records:
        fp = ROOT / r["file"]
        if not fp.exists():
            print(f"  ✗ 文件不存在: {r['file']}")
            continue
        try:
            tx = w.current_tx()
            tx.add_data(fp.read_bytes())
            tx.add_tag("Content-Type", "application/octet-stream")
            tx.add_tag("App-Name", "seed-trilogy")
            tx.add_tag("File-Name", Path(r["file"]).name)
            tx.sign()
            tx.send()
            print(f"  ✓ {Path(r['file']).name[:30]:30s} → {tx.id}")
            ok += 1
            time.sleep(1)
        except Exception as e:
            print(f"  ✗ {Path(r['file']).name[:30]:30s} → {e}")
    print(f"\n  Arweave 上传完成: {ok}/{len(records)}")
    return 0 if ok == len(records) else 1


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
    parser = argparse.ArgumentParser(description="远程存证：IPFS + Arweave + Internet Archive")
    parser.add_argument("--ipfs", action="store_true", help="IPFS 远程固定")
    parser.add_argument("--arweave", action="store_true", help="Arweave 永久存储")
    parser.add_argument("--archive", action="store_true", help="Internet Archive 备份")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", "https://seed-trilogy.com.cn"))
    args = parser.parse_args()

    if not any([args.ipfs, args.arweave, args.archive]):
        parser.print_help()
        sys.exit(0)

    results = {}
    if args.ipfs:
        results["ipfs"] = do_ipfs()
    if args.arweave:
        results["arweave"] = do_arweave()
    if args.archive:
        results["archive"] = do_archive(args.site_url)

    print(f"\n{'='*60}\n  汇总\n{'='*60}")
    for task, code in results.items():
        label = "✓ 成功" if code == 0 else ("⚠ 部分" if code == 1 else "⊘ 跳过")
        print(f"  {task:15s} {label}")

    sys.exit(0 if all(c == 0 for c in results.values()) else 1)


if __name__ == "__main__":
    main()
