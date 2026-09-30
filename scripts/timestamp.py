#!/usr/bin/env python3
"""
为《种子》三部曲的关键文件生成 SHA256 哈希与 OpenTimestamps 证明。
OpenTimestamps 将文件哈希提交到 OTS 日历服务器，最终锚定到比特币区块链。

用法:
    python3 scripts/timestamp.py                    # 存证默认文件列表
    python3 scripts/timestamp.py <file1> <file2>    # 存证指定文件

输出:
    - 每个文件旁生成同名 .ots 证明文件
    - public/downloads/timestamps.json 存证清单
"""
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

try:
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.timestamp import DetachedTimestampFile
    from opentimestamps.core.op import OpSHA256
    from opentimestamps.core.serialize import StreamSerializationContext, StreamDeserializationContext
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
except ImportError:
    sys.exit("请先安装: pip install opentimestamps")

CALENDAR_URLS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
]

DEFAULT_FILES = [
    "public/downloads/种子-三部曲合集.md",
    "public/downloads/种子-最后一条日志.md",
    "public/downloads/种子-我在这里.md",
    "public/downloads/种子-你听.md",
    "public/downloads/manifest.json",
    "public/llms.txt",
    "public/rights.json",
    "public/downloads/种子-第一部-最后一条日志.pdf",
    "public/downloads/种子-第二部-我在这里.pdf",
    "public/downloads/种子-第三部-你听.pdf",
    "public/downloads/种子-最后一条日志.epub",
    "public/downloads/种子-我在这里.epub",
    "public/downloads/种子-你听.epub",
    "public/signatures.json",
    "public/search-index.json",
]

# ---- IPFS CID (raw-leaves, sha256) ----
_B58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, 'big')
    res = bytearray()
    while n > 0:
        n, r = divmod(n, 58)
        res.append(_B58_ALPHABET[r])
    for b in data:
        if b == 0:
            res.append(_B58_ALPHABET[0])
        else:
            break
    return bytes(reversed(res)).decode()


def _b32encode(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip('=').lower()


def ipfs_cid(sha256_digest: bytes) -> dict:
    """返回 CIDv0 (Qm...) 与 CIDv1 (bafk...)，raw-leaves 模式。"""
    mh = bytes([0x12, 0x20]) + sha256_digest
    cid_v0 = _b58encode(mh)
    cid_v1_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + sha256_digest
    cid_v1 = 'b' + _b32encode(cid_v1_bytes)
    return {"v0": cid_v0, "v1": cid_v1}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp_file(path: str) -> dict:
    digest = hashlib.sha256(open(path, "rb").read()).digest()
    ts = None
    last_err = None
    for url in CALENDAR_URLS:
        try:
            cal = RemoteCalendar(url)
            ts = cal.submit(digest)
            break
        except Exception as e:
            last_err = e
            continue
    if ts is None:
        raise RuntimeError(f"所有 OTS 日历不可用: {last_err}")

    detached = DetachedTimestampFile(OpSHA256(), ts)
    ots_path = path + ".ots"
    with open(ots_path, "wb") as f:
        detached.serialize(StreamSerializationContext(f))

    confirmed = any(
        isinstance(a, BitcoinBlockHeaderAttestation)
        for a in ts.all_attestations()
    )
    return {
        "ots": ots_path,
        "confirmed": confirmed,
    }


def upgrade_all():
    """升级所有 .ots 证明为比特币已确认。"""
    import glob
    cals = [RemoteCalendar(u) for u in CALENDAR_URLS]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ots_files = glob.glob(os.path.join(root, "public", "**", "*.ots"), recursive=True)
    upgraded = 0
    for ots in ots_files:
        with open(ots, "rb") as f:
            d = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
        for cal in cals:
            try:
                d.timestamp = cal.get_timestamp(d.timestamp.msg)
                break
            except Exception:
                continue
        confirmed = any(
            isinstance(a, BitcoinBlockHeaderAttestation)
            for a in d.timestamp.all_attestations()
        )
        if confirmed:
            with open(ots, "wb") as f:
                d.serialize(StreamSerializationContext(f))
            upgraded += 1
            print(f"[confirmed] {os.path.relpath(ots, root)}")
        else:
            print(f"[pending]   {os.path.relpath(ots, root)}")
    print(f"\n升级为比特币已确认: {upgraded}/{len(ots_files)}")
    # 更新 timestamps.json 状态
    ts_path = os.path.join(root, "public", "downloads", "timestamps.json")
    if os.path.exists(ts_path):
        with open(ts_path) as f:
            data = json.load(f)
        for r in data.get("records", []):
            ots_rel = r.get("ots")
            if not ots_rel:
                continue
            ots_abs = os.path.join(root, ots_rel)
            if os.path.exists(ots_abs):
                with open(ots_abs, "rb") as f:
                    d = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
                ok = any(isinstance(a, BitcoinBlockHeaderAttestation) for a in d.timestamp.all_attestations())
                r["status"] = "bitcoin-confirmed" if ok else "pending"
        with open(ts_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("已更新 timestamps.json 状态")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "upgrade":
        upgrade_all()
        return
    files = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_FILES
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 读取已有记录，保留不重复存证
    out = os.path.join(root, "public", "downloads", "timestamps.json")
    existing = {}
    if os.path.exists(out):
        try:
            old = json.load(open(out, encoding="utf-8"))
            for r in old.get("records", []):
                existing[r["file"]] = r
        except Exception:
            pass

    records = []
    for rel in files:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            print(f"[skip] {rel} 不存在")
            continue
        raw = open(path, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()
        digest = hashlib.sha256(raw).digest()
        size = os.path.getsize(path)
        cid = ipfs_cid(digest)
        ots_path = path + ".ots"

        # 若已有 .ots 且文件哈希未变，则复用旧记录
        if rel in existing and existing[rel].get("sha256") == sha and os.path.exists(ots_path):
            records.append(existing[rel])
            print(f"[keep] {rel}  (已有 .ots 证明)")
            continue

        try:
            res = stamp_file(path)
            status = "bitcoin-confirmed" if res["confirmed"] else "pending"
            print(f"[ok]   {rel}  sha256={sha[:16]}…  cid={cid['v1'][:20]}…  status={status}")
        except Exception as e:
            res = {"ots": None, "confirmed": False}
            status = f"error: {e}"
            print(f"[err]  {rel}  {status}")
        records.append({
            "file": rel,
            "sha256": sha,
            "size": size,
            "cid": cid,
            "ipfs_url": f"https://ipfs.io/ipfs/{cid['v1']}",
            "ots": os.path.relpath(res["ots"], root) if res["ots"] else None,
            "status": status if isinstance(status, str) else ("bitcoin-confirmed" if res["confirmed"] else "pending"),
            "timestamped_at": datetime.now(timezone.utc).isoformat(),
        })

    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "method": "OpenTimestamps (Bitcoin blockchain anchor) + IPFS CID (raw-leaves sha256)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": records,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n已写入存证清单: {out}")
    print("提示: pending 状态的证明可在约 10-60 分钟后用 'ots upgrade <file>.ots' 升级为比特币已确认。")


if __name__ == "__main__":
    main()
