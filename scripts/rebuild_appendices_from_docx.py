"""从附录合订 docx 提取章节内容，重建附录G-O的 md body。
保留原 frontmatter，只替换 body 部分。
"""
import docx
import re
from pathlib import Path

DOCX_PATH = '/workspace/.uploads/种子三部曲_附录（合订）_1790862931071475763.docx'
CONTENT_DIR = '/workspace/seed-trilogy/src/content/first-log'

# 第X章 → 附录X.md
CHAPTER_TO_FILE = {
    '第一章': '附录G.md',  # 地点与坐标
    '第二章': '附录H.md',  # 核心物品
    '第三章': '附录I.md',  # 动物与物种
    '第四章': '附录J.md',  # 引用文字
    '第五章': '附录K.md',  # 名物索引（按出现顺序）
    '第六章': '附录L.md',  # 人物志
    '第七章': '附录M.md',  # 时间线
    '第八章': '附录N.md',  # 大事记
    '第九章': '附录O.md',  # 跨部呼应索引
}

# 章节标题正则
CHAPTER_TITLE_RE = re.compile(r'^第([一二三四五六七八九十]+)章\s*(.*)$')

def extract_chapters(docx_path):
    """从 docx 提取章节内容。返回 dict: chapter_num → (chapter_title, [paragraphs])"""
    d = docx.Document(docx_path)
    chapters = {}
    current_chapter = None  # '一', '二', ...
    current_title = None
    current_paras = []

    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        m = CHAPTER_TITLE_RE.match(text)
        if m:
            # 保存上一章
            if current_chapter:
                chapters[current_chapter] = (current_title, current_paras)
            current_chapter = m.group(1)
            current_title = m.group(2).strip()
            current_paras = []
            continue
        if current_chapter is None:
            continue
        current_paras.append(text)

    if current_chapter:
        chapters[current_chapter] = (current_title, current_paras)

    return chapters

def render_md_body(paragraphs):
    """把段落列表渲染为 md body 文本。"""
    lines = ['']
    for text in paragraphs:
        # 跳过分隔符
        if re.match(r'^(\*\s*){2,}\*?$', text) or text == '* * *' or text == '*  *  *':
            continue
        lines.append(text)
        lines.append('')
    body = '\n'.join(lines)
    body = re.sub(r'\n{4,}', '\n\n\n', body)
    return body.strip() + '\n'

def update_md_file(md_path, new_body):
    """更新 md 文件：保留 frontmatter，替换 body。"""
    text = md_path.read_text(encoding='utf-8')
    m = re.match(r'^(---\n.*?\n---\n)(.*)$', text, re.S)
    if not m:
        print(f"  WARN: no frontmatter in {md_path.name}")
        return False
    fm = m.group(1)
    new_text = fm + '\n' + new_body
    md_path.write_text(new_text, encoding='utf-8')
    return True

def main():
    print(f"Extracting chapters from {DOCX_PATH}...")
    chapters = extract_chapters(DOCX_PATH)
    print(f"Found {len(chapters)} chapters")
    for k, (title, paras) in chapters.items():
        cn_chapter = f'第{k}章'
        target_filename = CHAPTER_TO_FILE.get(cn_chapter)
        if not target_filename:
            print(f"  {cn_chapter} ({title}): no mapping, SKIP")
            continue
        md_path = Path(CONTENT_DIR) / target_filename
        if not md_path.exists():
            print(f"  {cn_chapter} ({title}): {md_path.name} not found, SKIP")
            continue
        body = render_md_body(paras)
        if update_md_file(md_path, body):
            print(f"  ✓ {cn_chapter} ({title}) → {md_path.name} ({len(paras)} paras)")

if __name__ == '__main__':
    main()
