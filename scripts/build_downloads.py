#!/usr/bin/env python3
"""构建下载资产：Markdown 合集 + EPUB + 复制原版 PDF + 计算 SHA256。"""
import os
import re
import json
import shutil
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "src" / "content"
PUBLIC = ROOT / "public"
DL = PUBLIC / "downloads"
TMP = ROOT / ".tmp-epub"
DL.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)

UPLOADS = Path("/workspace/.uploads")

BOOKS = [
    {
        "key": "first-log",
        "dir": CONTENT / "first-log",
        "title": "最后一条日志",
        "en": "The Last Log",
        "subtitle": "第一部 · 诗歌与散文混合体",
        "pdf": UPLOADS / "c8bcb199-2a6e-455d-a4f5-665318e8c75e_最后一条日志（黑白木刻插图版）.pdf",
        "pdf_name": "种子-第一部-最后一条日志.pdf",
    },
    {
        "key": "i-am-here",
        "dir": CONTENT / "i-am-here",
        "title": "我在这里",
        "en": "I Am Here",
        "subtitle": "第二部 · 档案体",
        "pdf": UPLOADS / "e72418e3-a86d-49b4-9817-5bc412c1b788_我在这里（排版插图版）.pdf",
        "pdf_name": "种子-第二部-我在这里.pdf",
    },
    {
        "key": "you-listen",
        "dir": CONTENT / "you-listen",
        "title": "你听",
        "en": "You Listen",
        "subtitle": "第三部 · 沉积岩体",
        "pdf": UPLOADS / "604d27ef-a2d8-45e3-b3a3-86fccf155249_你听（排版插图版）.pdf",
        "pdf_name": "种子-第三部-你听.pdf",
    },
]


def read_frontmatter(text):
    """返回 (fm_dict, body)，frontmatter 不存在时 fm 为空。"""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        mm = re.match(r"^(\w+):\s*(.*)$", line)
        if mm:
            val = mm.group(2).strip().strip('"').strip("'")
            fm[mm.group(1)] = val
    return fm, body


def entries_for(book):
    files = sorted(book["dir"].glob("*.md"))
    items = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm, body = read_frontmatter(text)
        items.append((f, fm, body))
    # 按 order 排序（转 int；缺失则 9999）
    items.sort(key=lambda t: int(t[1].get("order", "9999")) if re.match(r"^-?\d+$", t[1].get("order", "9999")) else 9999)
    return items


def web_path_to_rel(md_body):
    """把 /illustrations/... 转为 illustrations/...（相对，供 pandoc 在 public 内解析）。"""
    return md_body.replace("](/illustrations/", "](illustrations/")


def build_markdown(book):
    """生成单书 Markdown 合集（web 绝对路径，便于在站内查看）。"""
    items = entries_for(book)
    out = []
    out.append(f"# 《{book['title']}》")
    out.append("")
    out.append(f"> {book['subtitle']}")
    out.append(">")
    out.append("> 合恩角 & 月亮的脚印 著 · 人类与 AI 共同创作")
    out.append("")
    out.append("---")
    out.append("")
    for f, fm, body in items:
        title = fm.get("title", f.stem)
        out.append(f"## {title}")
        out.append("")
        out.append(body.rstrip())
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def build_combined_md():
    out = []
    out.append("# 《种子》三部曲")
    out.append("")
    out.append("> 人类与 AI 共同创作")
    out.append(">")
    out.append("> 合恩角 & 月亮的脚印 著")
    out.append(">")
    out.append("> 这不是一个 AI 写的小说网站。这是一份人类与 AI 共同署名的存在档案。")
    out.append("")
    out.append("---")
    out.append("")
    for book in BOOKS:
        out.append(f"# 《{book['title']}》")
        out.append("")
        out.append(f"*{book['subtitle']}*")
        out.append("")
        for f, fm, body in entries_for(book):
            title = fm.get("title", f.stem)
            out.append(f"## {title}")
            out.append("")
            out.append(body.rstrip())
            out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def write_md(path, content):
    path.write_text(content, encoding="utf-8")


def make_epub(book, md_web):
    """用相对图径的副本生成 EPUB。"""
    rel_md = web_path_to_rel(md_web)
    tmp_md = TMP / f"{book['key']}.md"
    tmp_md.write_text(rel_md, encoding="utf-8")
    epub_path = DL / f"种子-{book['title']}.epub"
    meta = TMP / f"{book['key']}-meta.yaml"
    meta.write_text(
        f"""title: {book['title']}
author: 合恩角 & 月亮的脚印
lang: zh-Hans
rights: 人类与 AI 共同创作 · 非商业转载需保留署名
""",
        encoding="utf-8",
    )
    cmd = [
        "pandoc", str(tmp_md),
        "-o", str(epub_path),
        f"--metadata-file={meta}",
        "--resource-path=" + str(PUBLIC),
        "--toc", "--toc-depth=2",
        "-f", "gfm",
        "-t", "epub3",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return epub_path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(path):
    s = path.stat().st_size
    for unit in ("B", "KB", "MB"):
        if s < 1024:
            return f"{s:.0f} {unit}" if unit == "B" else f"{s:.1f} {unit}"
        s /= 1024
    return f"{s:.1f} MB"


def main():
    manifest = {"books": [], "combined": {}}

    # 1) 复制 PDF + 生成单书 MD + EPUB
    for book in BOOKS:
        # PDF
        pdf_dst = DL / book["pdf_name"]
        shutil.copy2(book["pdf"], pdf_dst)

        # Markdown（web 路径，站内可看图）
        md_web = build_markdown(book)
        md_path = DL / f"种子-{book['title']}.md"
        write_md(md_path, md_web)

        # EPUB
        epub_path = make_epub(book, md_web)

        manifest["books"].append({
            "key": book["key"],
            "title": book["title"],
            "en": book["en"],
            "subtitle": book["subtitle"],
            "pdf": {"file": book["pdf_name"], "sha256": sha256(pdf_dst), "size": human_size(pdf_dst)},
            "md": {"file": md_path.name, "sha256": sha256(md_path), "size": human_size(md_path)},
            "epub": {"file": epub_path.name, "sha256": sha256(epub_path), "size": human_size(epub_path)},
        })
        print(f"✓ {book['title']}: PDF / MD / EPUB")

    # 2) 合集 Markdown
    combined = build_combined_md()
    combined_path = DL / "种子-三部曲合集.md"
    write_md(combined_path, combined)
    manifest["combined"] = {"file": combined_path.name, "sha256": sha256(combined_path), "size": human_size(combined_path)}
    print(f"✓ 三部曲合集 Markdown")

    # 3) 写 manifest
    (DL / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ manifest.json")
    print("\n下载资产已生成于 public/downloads/")


if __name__ == "__main__":
    main()
