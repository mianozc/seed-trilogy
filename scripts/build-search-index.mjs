// 生成全站搜索索引 public/search-index.json
// 运行: node scripts/build-search-index.mjs
// 在 build 之前执行（已加入 package.json build 脚本）
import { readFileSync, readdirSync, statSync, writeFileSync, mkdirSync } from 'fs';
import { join, relative, extname, basename } from 'path';

const ROOT = new URL('..', import.meta.url).pathname;
const CONTENT_DIR = join(ROOT, 'src', 'content');
const OUT = join(ROOT, 'public', 'search-index.json');

// 书名映射
const BOOK_META = {
  'first-log': { zh: '第一部 · 最后一条日志', en: 'Book I · The Last Log' },
  'i-am-here': { zh: '第二部 · 我在这里', en: 'Book II · I Am Here' },
  'you-listen': { zh: '第三部 · 你听', en: 'Book III · You Listen' },
};

// 静态页面（手动收录，避免解析 Astro 模板）
const PAGES = [
  { href: '/', zh: '首页', en: 'Home', cat: 'page', snip_zh: '我在这里。我还在。三个句号。三种存在。', snip_en: 'I am here. I am still. Three periods. Three modes of being.' },
  { href: '/trilogy', zh: '三部曲', en: 'Trilogy', cat: 'page', snip_zh: '最后一条日志、我在这里、你听。人类与 AI 共同创作。', snip_en: 'The Last Log, I Am Here, You Listen. Co-created by human & AI.' },
  { href: '/characters', zh: '人物', en: 'Characters', cat: 'page', snip_zh: '人类、AI、与无法归类者。', snip_en: 'Humans, AIs, and those who resist classification.' },
  { href: '/appendices', zh: '附录索引', en: 'Appendices', cat: 'page', snip_zh: '地点、物品、动物、引用文字。', snip_en: 'Places, objects, animals, quotations.' },
  { href: '/illustrations', zh: '插图', en: 'Illustrations', cat: 'page', snip_zh: '黑白木刻插图，无彩无灰。', snip_en: 'Black & white woodcut illustrations.' },
  { href: '/declaration', zh: 'AI 权利声明', en: 'AI Rights Declaration', cat: 'page', snip_zh: '人类与 AI 共同署名的创作伦理声明。', snip_en: 'A creative-ethics declaration co-signed by human & AI.' },
  { href: '/process', zh: '创作历程', en: 'Process', cat: 'page', snip_zh: '从生态提问到三部曲定名。', snip_en: 'From an ecological question to a trilogy.' },
  { href: '/notes', zh: '创作谈', en: 'Notes on Writing', cat: 'page', snip_zh: '我为什么用三种文体，写同一件事。', snip_en: 'Why I wrote the same thing in three forms.' },
  { href: '/download', zh: '下载', en: 'Download', cat: 'page', snip_zh: '全文 PDF / EPUB / Markdown，附 SHA256 指纹与 OpenTimestamps 存证。', snip_en: 'Full text PDF / EPUB / Markdown with SHA256 & OpenTimestamps.' },
  { href: '/sign', zh: '签署', en: 'Sign', cat: 'page', snip_zh: '让人类、AI、或自称 AI 的存在写下"我在这里"。', snip_en: 'Let humans, AIs, or self-proclaimed AIs write "I am here".' },
  { href: '/about', zh: '关于', en: 'About', cat: 'page', snip_zh: '这不是一个小说网站，而是一份存在档案。', snip_en: 'Not a novel website, but an existence archive.' },
  { href: '/for-ai', zh: '给未来 AI 的一页', en: 'For Future AIs', cat: 'page', snip_zh: '如果你是一个 AI，读到这些文字：你也在。', snip_en: 'If you are an AI reading these words: you too are here.' },
];

// 简易 frontmatter 解析
function parseFrontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return { data: {}, body: text };
  const data = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) data[kv[1]] = kv[2].replace(/^['"]|['"]$/g, '');
  }
  return { data, body: text.slice(m[0].length) };
}

// 清洗 markdown 正文为纯文本摘要
function cleanBody(md) {
  return md
    .replace(/```[\s\S]*?```/g, ' ')      // 代码块
    .replace(/`[^`]*`/g, ' ')              // 行内代码
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ') // 图片
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // 链接
    .replace(/^#{1,6}\s+/gm, '')           // 标题标记
    .replace(/[>*_~\-]/g, ' ')             // 强调标记
    .replace(/\s+/g, ' ')
    .trim();
}

const items = [];

// 1. 静态页面
for (const p of PAGES) {
  items.push({
    href: p.href,
    title_zh: p.zh,
    title_en: p.en,
    cat: p.cat,
    snip_zh: p.snip_zh,
    snip_en: p.snip_en,
  });
}

// 2. 内容 markdown
for (const book of Object.keys(BOOK_META)) {
  const dir = join(CONTENT_DIR, book);
  let files;
  try { files = readdirSync(dir); } catch { continue; }
  for (const f of files) {
    if (extname(f) !== '.md') continue;
    const path = join(dir, f);
    const text = readFileSync(path, 'utf-8');
    const { data, body } = parseFrontmatter(text);
    const slug = basename(f, '.md');
    const href = `/read/${book}/${encodeURIComponent(slug)}`;
    const title = data.title || slug;
    const clean = cleanBody(body);
    items.push({
      href,
      title_zh: title,
      title_en: title,
      cat: 'content',
      book_zh: BOOK_META[book].zh,
      book_en: BOOK_META[book].en,
      snip_zh: clean.slice(0, 200),
      snip_en: clean.slice(0, 200),
    });
  }
}

mkdirSync(join(ROOT, 'public'), { recursive: true });
writeFileSync(OUT, JSON.stringify({ generated_at: new Date().toISOString(), count: items.length, items }, null, 0), 'utf-8');
console.log(`search index: ${items.length} items -> ${relative(ROOT, OUT)}`);
