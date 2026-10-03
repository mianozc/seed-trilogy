"""从 PDF 提取每章内容并按段落重建 md body。
保留原 frontmatter，只替换 body 部分。
支持三部书 + 附录 docx。
"""
import pdfplumber
import re
from pathlib import Path

# ============ 配置 ============
BOOKS_CONFIG = {
    'first-log': {
        'pdf': '/workspace/.uploads/c8bcb199-2a6e-455d-a4f5-665318e8c75e_最后一条日志（黑白木刻插图版）.pdf',
        'content_dir': '/workspace/seed-trilogy/src/content/first-log',
        'skip_pages': 2,  # 跳过封面、凡例
        'chapter_pattern': re.compile(r'^(\d{4})\s+(.+)$'),
        'title_size_min': 13.0,
        'title_size_max': 17.0,
        'body_size': 10.5,
    },
    'i-am-here': {
        'pdf': '/workspace/.uploads/e72418e3-a86d-49b4-9817-5bc412c1b788_我在这里（排版插图版）.pdf',
        'content_dir': '/workspace/seed-trilogy/src/content/i-am-here',
        'skip_pages': 0,
        'chapter_pattern': re.compile(r'^第([一二三四五六七八九十]+)章\s+(.+)$'),
        'title_size_min': 14.0,
        'title_size_max': 18.0,
        'body_size': 10.5,
        'subsection_size': 12.0,  # 子节标记 "一""二" 等
    },
    'you-listen': {
        'pdf': '/workspace/.uploads/604d27ef-a2d8-45e3-b3a3-86fccf155249_你听（排版插图版）.pdf',
        'content_dir': '/workspace/seed-trilogy/src/content/you-listen',
        'skip_pages': 1,  # 跳过封面
        'chapter_pattern': re.compile(r'^(表层|中层|过渡带|底层)[:：]\s*(.+)$'),
        'title_size_min': 14.0,
        'title_size_max': 18.0,
        'body_size': 10.5,
        'subsection_size': 14.0,  # 浮筒/淡水/课堂/沉积层 等
    },
}

# 终止符（段尾标志）
END_CHARS = set('。！？!?')
# 行末分隔符（独立成段的标记）
SEPARATOR_CHARS = set('*·•—–-')

# ============ 通用辅助函数 ============
def get_avg_size(line):
    chars = line.get('chars', [])
    sizes = [c.get('size', 0) for c in chars if c.get('size')]
    return sum(sizes) / len(sizes) if sizes else 0

def get_fonts(line):
    chars = line.get('chars', [])
    return set(c.get('fontname', '') for c in chars)

def is_page_number(line):
    """识别页码：纯数字，特定字体。"""
    text = line.get('text', '').strip()
    if not text or not text.isdigit():
        return False
    chars = line.get('chars', [])
    if not chars:
        return True
    fonts = set(c.get('fontname', '') for c in chars)
    return any('Liberation' in f for f in fonts)

def is_image_caption(line):
    """识别图片说明：'图 N xxx'。"""
    text = line.get('text', '').strip()
    return bool(re.match(r'^图\s*\d+\s+', text))

def is_field_marker(line):
    """识别字段标记：【xxx】。"""
    text = line.get('text', '').strip()
    return bool(re.match(r'^【.+】$', text))

def is_separator(line):
    """识别分隔符 * * * / *  *  *"""
    text = line.get('text', '').strip()
    return bool(re.match(r'^(\*\s*){2,}\*?$', text)) or text == '* * *'

def is_chapter_title(line, book_key):
    """识别章节标题。返回 (类型, *args) 或 None。"""
    text = line.get('text', '').strip()
    if not text:
        return None
    avg_size = get_avg_size(line)
    cfg = BOOKS_CONFIG[book_key]

    # 特殊章节标题（不受字号限制）
    if book_key == 'you-listen' and text.startswith('过渡带'):
        m = re.match(r'^过渡带[:：]\s*(.+)$', text)
        if m:
            return ('chapter', '过渡带', m.group(1))
        return ('chapter', '过渡带', '')

    if avg_size < cfg['title_size_min'] or avg_size > cfg['title_size_max']:
        return None

    if book_key == 'first-log':
        # 特殊章节标题
        if text == '0530 尾声':
            return ('chapter', '尾声', '尾声')
        if text == '2187年9月27日':
            return ('chapter', '结语', '2187年9月27日')
        m = cfg['chapter_pattern'].match(text)
        if m:
            return ('chapter', m.group(1), m.group(2))
        if text.startswith('第一部分') or text.startswith('第二部分') or text.startswith('第三部分') or text.startswith('第四部分'):
            return ('part', None, text)
        return None

    if book_key == 'i-am-here':
        # 第十二章 2187 年（带空格的特殊标题）
        if text == '第十二章 2187 年':
            return ('chapter', '十二', '2187 年')
        m = cfg['chapter_pattern'].match(text)
        if m:
            return ('chapter', m.group(1), m.group(2))
        return None

    if book_key == 'you-listen':
        # 3 个层级标题（表层/中层/底层 sz=16）
        m = cfg['chapter_pattern'].match(text)
        if m:
            return ('chapter', m.group(1), m.group(2))
        return None

    return None

def is_subsection_marker(line, book_key):
    """识别子节标记。返回 True/False。"""
    text = line.get('text', '').strip()
    if not text:
        return False
    cfg = BOOKS_CONFIG[book_key]
    if 'subsection_size' not in cfg:
        return False
    avg_size = get_avg_size(line)
    # 子节标记字号必须严格匹配
    if abs(avg_size - cfg['subsection_size']) > 0.5:
        return False
    if book_key == 'i-am-here':
        # 单个汉字数字 "一" "二" 等
        return bool(re.match(r'^[一二三四五六七八九十]$', text))
    if book_key == 'you-listen':
        # 短词，无标点
        if len(text) > 12:
            return False
        # 排除正文短句（含标点）
        if any(c in text for c in '。，、；：！？""'''):
            return False
        # 已知子节标记列表（动态发现，这里只过滤明显非标记的）
        # 子节标记一般 2-6 字
        return bool(re.match(r'^[\u4e00-\u9fa5]{1,8}$', text))
    return False

# ============ 提取逻辑 ============
def extract_book_paragraphs(pdf_path, book_key):
    """提取整本书的章节内容。返回 dict: chapter_key -> (title, [paragraphs])。
    paragraph 是 (ptype, content) 元组，ptype ∈ {'text','image','field','subsection','part'}
    """
    cfg = BOOKS_CONFIG[book_key]
    chapters = {}
    current_chapter_key = None
    current_chapter_title = None
    current_paragraphs = []
    all_paragraphs = []
    current_text = ''
    started = False  # 是否已找到首个章节标题

    def flush_text():
        nonlocal current_text
        if current_text.strip():
            all_paragraphs.append(('text', current_text.strip()))
        current_text = ''

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            if pi < cfg['skip_pages']:
                continue
            try:
                lines = page.extract_text_lines()
            except Exception:
                continue
            for line in lines:
                text = (line.get('text') or '').strip()
                if not text:
                    continue
                if is_page_number(line):
                    continue
                # 跳过封面标题（在第一章标题出现前）
                if not started:
                    title_info = is_chapter_title(line, book_key)
                    if title_info and title_info[0] == 'chapter':
                        started = True
                        # 继续处理这个章节标题
                    else:
                        continue
                if is_separator(line):
                    flush_text()
                    # 分隔符作为段落分隔，不存为段落
                    continue
                if is_image_caption(line):
                    flush_text()
                    all_paragraphs.append(('image', text))
                    continue
                if is_field_marker(line):
                    flush_text()
                    all_paragraphs.append(('field', text))
                    continue
                if is_subsection_marker(line, book_key):
                    flush_text()
                    all_paragraphs.append(('subsection', text))
                    continue
                title_info = is_chapter_title(line, book_key)
                if title_info:
                    flush_text()
                    if title_info[0] == 'chapter':
                        all_paragraphs.append(('chapter', title_info[1:]))
                    elif title_info[0] == 'part':
                        all_paragraphs.append(('part', title_info[2]))
                    continue
                # 普通正文：累加
                current_text += text
                # 行末是终止符 → 段尾
                if text and text[-1] in END_CHARS:
                    flush_text()
                # 闭引号 + 段以开引号开始 → 段尾（诗歌等）
                elif text.endswith('"') and current_text.startswith('"'):
                    flush_text()
                elif text.endswith('”') and current_text.startswith('“'):
                    flush_text()
            # 页结束时不 flush，跨页保留段落
        # 文档结束
        flush_text()

    # 第二轮：按章节切分
    for ptype, pcontent in all_paragraphs:
        if ptype == 'part':
            if current_chapter_key:
                current_paragraphs.append(('part', pcontent))
            continue
        if ptype == 'chapter':
            if current_chapter_key:
                chapters[current_chapter_key] = (current_chapter_title, current_paragraphs)
            num, title = pcontent
            current_chapter_key = num
            current_chapter_title = title
            current_paragraphs = []
            continue
        if current_chapter_key is None:
            continue
        current_paragraphs.append((ptype, pcontent))
    if current_chapter_key:
        chapters[current_chapter_key] = (current_chapter_title, current_paragraphs)

    return chapters

# ============ 渲染 ============
def render_md_body(paragraphs, book_key):
    """把段落列表渲染为 md body 文本。"""
    lines = []
    lines.append('')  # 起始空行
    for ptype, pcontent in paragraphs:
        if ptype == 'part':
            lines.append('')
            lines.append(f'**{pcontent}**')
            lines.append('')
        elif ptype == 'image':
            m = re.match(r'^图\s*(\d+)\s+(.+)$', pcontent)
            if m:
                num = int(m.group(1))
                desc = m.group(2).strip()
                num_str = f'{num:02d}'
                if book_key == 'first-log':
                    img_path = f'/illustrations/first-log/fig-{num_str}.webp'
                else:
                    img_path = f'/illustrations/{book_key}/fig-{num_str}.webp'
                lines.append(f'![图{num_str} {desc}]({img_path})')
                lines.append('')
                lines.append(f'*图{num_str} ·{desc}*')
                lines.append('')
        elif ptype == 'field':
            # 字段标记 【xxx】
            lines.append('')
            lines.append(pcontent)
            lines.append('')
        elif ptype == 'subsection':
            # 子节标记：保留为独立短行
            lines.append('')
            lines.append(pcontent)
            lines.append('')
        elif ptype == 'text':
            # 正文段落
            lines.append(pcontent)
            lines.append('')
    body = '\n'.join(lines)
    body = re.sub(r'\n{4,}', '\n\n\n', body)
    return body.strip() + '\n'

# ============ 文件映射 ============
CN_NUM_MAP = {
    '一': '01', '二': '02', '三': '03', '四': '04', '五': '05',
    '六': '06', '七': '07', '八': '08', '九': '09', '十': '10',
    '十一': '11', '十二': '12',
}

def map_chapter_to_md_file(book_key, chapter_key, chapter_title, content_dir):
    """章节 key → md 文件路径。"""
    if book_key == 'first-log':
        if chapter_key.isdigit():
            return Path(content_dir) / f'{chapter_key}.md'
        if chapter_key == '尾声':
            return Path(content_dir) / '尾声.md'
        if chapter_key == '结语':
            return Path(content_dir) / '结语.md'
    elif book_key == 'i-am-here':
        # chapter_key 是中文数字
        if chapter_key in CN_NUM_MAP:
            return Path(content_dir) / f'ch{CN_NUM_MAP[chapter_key]}.md'
    elif book_key == 'you-listen':
        # 4 个层级 + 最底层（特殊处理）
        mapping = {
            '表层': '01-surface.md',
            '中层': '02-middle.md',
            '过渡带': '03-transition.md',
            '底层': '04-bottom.md',
            '最底层': '05-deepest.md',
        }
        if chapter_key in mapping:
            return Path(content_dir) / mapping[chapter_key]
    return None

def split_you_listen_bottom(paragraphs):
    """对 you-listen 底层：将 '最底层' 子节之后的内容拆到 05-deepest.md。
    返回 (bottom_paragraphs, deepest_paragraphs)
    """
    bottom = []
    deepest = []
    in_deepest = False
    for ptype, pcontent in paragraphs:
        if ptype == 'subsection' and pcontent == '最底层':
            in_deepest = True
            # 把 '最底层' 作为最深层的子节标记保留
            deepest.append((ptype, pcontent))
            continue
        if in_deepest:
            deepest.append((ptype, pcontent))
        else:
            bottom.append((ptype, pcontent))
    return bottom, deepest

# ============ 文件更新 ============
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

# ============ 主流程 ============
def process_book(book_key):
    cfg = BOOKS_CONFIG[book_key]
    print(f"\n=== Processing {book_key} ===")
    print(f"PDF: {cfg['pdf']}")
    chapters = extract_book_paragraphs(cfg['pdf'], book_key)
    print(f"Found {len(chapters)} chapters")

    for k, (title, paras) in chapters.items():
        print(f"  {k} ({title}): {len(paras)} paragraphs")
        md_path = map_chapter_to_md_file(book_key, k, title, cfg['content_dir'])
        if md_path is None or not md_path.exists():
            print(f"    SKIP (no md file mapping)")
            continue

        # 特殊处理：you-listen 底层 拆为 04-bottom + 05-deepest
        if book_key == 'you-listen' and k == '底层':
            bottom_paras, deepest_paras = split_you_listen_bottom(paras)
            if deepest_paras:
                # 更新 04-bottom
                body = render_md_body(bottom_paras, book_key)
                if update_md_file(md_path, body):
                    print(f"    ✓ updated {md_path.name} ({len(bottom_paras)} paras)")
                # 更新 05-deepest
                deepest_path = Path(cfg['content_dir']) / '05-deepest.md'
                if deepest_path.exists():
                    body2 = render_md_body(deepest_paras, book_key)
                    if update_md_file(deepest_path, body2):
                        print(f"    ✓ updated {deepest_path.name} ({len(deepest_paras)} paras)")
                continue

        body = render_md_body(paras, book_key)
        if update_md_file(md_path, body):
            print(f"    ✓ updated {md_path.name}")

def main():
    for book_key in ['first-log', 'i-am-here', 'you-listen']:
        process_book(book_key)

if __name__ == '__main__':
    main()
