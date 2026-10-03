---
name: "seed-trilogy-website"
description: "Build, update, and maintain the Seed Trilogy (种子三部曲) Astro static site. Invoke when user asks to update chapter content/appendices, fix formatting/layout, regenerate downloads, refresh attestation fingerprints, deploy changes, or any task touching /workspace/seed-trilogy."
---

# Seed Trilogy Website (种子三部曲网站)

Astro 静态站点 · 三部小说全文 + 附录 · 人类与 AI 共同创作 · 部署到 Cloudflare Pages。

仓库根目录：`/workspace/seed-trilogy`

## 项目结构

```
seed-trilogy/
├── src/
│   ├── content/              # 全文 Markdown（带 frontmatter）
│   │   ├── first-log/        # 第一部《最后一条日志》25章 + 尾声 + 结语 + 附录A-P
│   │   ├── i-am-here/        # 第二部《我在这里》12章 (ch01-ch12)
│   │   ├── you-listen/       # 第三部《你听》5 个层级 (01-surface..05-deepest)
│   │   └── config.ts         # 内容集合定义
│   ├── pages/                # Astro 页面
│   │   ├── read/{book}/[slug].astro  # 章节动态路由
│   │   ├── download.astro    # 下载 + 存证页
│   │   ├── trilogy.astro     # 三部曲入口
│   │   ├── declaration.astro # AI 权利声明
│   │   └── ...
│   ├── lib/i18n.ts           # 中英双语字典
│   └── layouts/Base.astro
├── public/
│   ├── downloads/            # MD/EPUB/PDF + manifest.json + timestamps.json + .ots
│   ├── illustrations/{book}/fig-XX.webp
│   ├── js/i18n-data.js       # 由 src/lib/i18n.ts 生成
│   └── search-index.json
├── scripts/
│   ├── rebuild_pdf_to_md.py        # PDF → 章节 MD
│   ├── rebuild_appendices_from_docx.py  # docx → 附录 MD
│   ├── build_downloads.py          # 生成 MD/EPUB 合集 + manifest.json
│   ├── build-search-index.mjs      # 搜索索引
│   ├── gen-i18n-data.mjs           # i18n.ts → i18n-data.js
│   ├── timestamp.py                # OpenTimestamps + SHA256 存证
│   └── attest.py                   # Internet Archive 备份
└── .github/workflows/deploy.yml    # Cloudflare Pages 自动部署
```

## Frontmatter 规范

每章 MD 文件必须含 frontmatter（`---` 包围），字段：

```yaml
---
title: 第一口呼吸          # 章节标题（不含编号）
num: "0001"                # 章节编号（字符串）
part: 第一部·合恩角号      # 所属部
order: 1                   # 在部内的顺序
style: 诗歌与散文混合体    # 文体
book: first-log           # 书 key: first-log | i-am-here | you-listen
---
```

附录 frontmatter：`num: "附录G"`，`part: 第一部·附录`，`style: 参考资料`。

## 内容更新工作流

### 从 PDF 重建章节正文（排版修复）

```bash
cd /workspace/seed-trilogy
python3 scripts/rebuild_pdf_to_md.py
```

脚本读取 `BOOKS_CONFIG`（含 PDF 路径、章节正则、字号阈值），逐页 `pdfplumber.extract_text_lines()`，识别：
- 章节标题（字号 14-17，匹配 `chapter_pattern`）
- 字段标记 `【xxx】`（独立成段）
- 图片说明 `图 N xxx` → 转为 `![图NN xxx](/illustrations/{book}/fig-NN.webp)` + `*图NN ·xxx*`
- 子节标记（第二部"一/二/三"、第三部"浮筒/淡水/课堂"等，字号 12-14）
- 终止符 `。！？!?` → 段尾
- 跨页段落合并：`current_text` 跨页累积，仅遇终止符或新章节才 flush

**保留 frontmatter，只替换 body**。函数 `update_md_file(md_path, body)` 用正则 `^(---\n.*?\n---\n)(.*)$` 切分。

特殊章节映射：
- 第一部：`0530 尾声` → `尾声.md`，`2187年9月27日` → `结语.md`
- 第三部：`过渡带` 标题字号与正文相同，靠文本前缀识别（不受字号限制）；`最底层` 是 `04-bottom.md` 内的子节，需用 `split_you_listen_bottom()` 拆到 `05-deepest.md`

### 从 docx 重建附录

```bash
python3 scripts/rebuild_appendices_from_docx.py
```

读取附录合订 docx，按 `第X章` 切分，`CHAPTER_TO_FILE` 映射到 `附录G.md`-`附录O.md`。

### 原始素材位置

PDF/docx 上传到 `/workspace/.uploads/`，文件名形如 `{uuid}_{中文名}.pdf`。脚本 `BOOKS_CONFIG.pdf` 字段指向具体路径。

## 下载资产生成

```bash
python3 scripts/build_downloads.py
```

为每部书生成：
- `种子-{书名}.md`（web 绝对路径，便于站内查看）
- `种子-{书名}.epub`（含插图，临时 `.tmp-epub` 目录构建后删除）
- `种子-三部曲合集.md`（三部合一）

并更新 `manifest.json`（含每文件 size + sha256）。

## i18n 双语

`src/lib/i18n.ts` 含 `zh`/`en` 双字典。修改后必须重新生成：

```bash
node scripts/gen-i18n-data.mjs
```

输出 `public/js/i18n-data.js`（`globalThis.SEED_I18N` 全局变量，供浏览器 i18n.js 使用）。

## 存证工作流（OpenTimestamps + SHA256 + Internet Archive）

**注意：本项目已移除 IPFS 远程固定和 Arweave 永久上传。** 不要重新引入。

### 1. 生成 SHA256 + OTS 证明

```bash
pip install opentimestamps  # 一次性
python3 scripts/timestamp.py
```

为 `DEFAULT_FILES`（15 个文件：3 部 MD/EPUB/PDF + 合集 + manifest + llms.txt + rights.json + signatures + search-index）生成：
- `<file>.ots` 旁路证明文件（提交到 `a/b.pool.opentimestamps.org`）
- `public/downloads/timestamps.json` 清单（含 file/sha256/size/ots/status/timestamped_at，**不含 cid/ipfs_url**）

复用逻辑：若文件 SHA256 未变且 `.ots` 已存在，则 `[keep]` 复用旧记录（去掉 IPFS 残留字段）。

### 2. 升级 OTS 证明为比特币已确认

pending 状态约 10-60 分钟后可升级：

```bash
python3 scripts/timestamp.py upgrade
```

### 3. Internet Archive 备份（手动触发）

```bash
python3 scripts/attest.py --archive
# 或 GitHub Actions: workflow_dispatch with archive=true
```

提交 `SITE_PAGES` 中 10 个页面到 Wayback Machine。

## 部署

推送 `main` 分支到 GitHub → Cloudflare Pages 自动部署：

```bash
git add -A
git commit -m "fix: 描述"
git push origin main
```

本地预览：

```bash
npm run build    # 验证构建无错（输出 71 页）
npm run preview  # http://localhost:4321
```

## 验证清单

内容更新后按顺序验证：
1. **构建**：`npm run build` 应输出 `71 page(s) built` 且无错误
2. **段落**：`grep -c "<p>" dist/read/{book}/{slug}/index.html` 应有多个 `<p>`
3. **下载**：MD/EPUB 抽样检查段落分隔、字段标记独立、图片说明格式
4. **SHA256**：`manifest.json` 中的 sha256 与实际文件哈希一致
5. **timestamps.json**：无 `cid`/`ipfs_url`/`IPFS` 残留
6. **下载页**：`dist/download/index.html` 存证表格为 4 列（文件/SHA256/状态/证明），无 IPFS CID 列

## 常见任务

| 任务 | 命令 |
|---|---|
| 修复章节排版 | `python3 scripts/rebuild_pdf_to_md.py` |
| 重建附录 | `python3 scripts/rebuild_appendices_from_docx.py` |
| 重生成下载 | `python3 scripts/build_downloads.py` |
| 更新搜索索引 | `node scripts/build-search-index.mjs` |
| 更新 i18n | `node scripts/gen-i18n-data.mjs` |
| 存证（SHA256+OTS） | `python3 scripts/timestamp.py` |
| 升级 OTS | `python3 scripts/timestamp.py upgrade` |
| Internet Archive | `python3 scripts/attest.py --archive` |
| 本地预览 | `npm run preview` |
| 部署 | `git push origin main` |

## 关键约定

- **图片**：所有插图用 webp，路径 `/illustrations/{book}/fig-{NN}.webp`（NN 为两位数零填充）
- **字段标记**：`【xxx】` 必须独立成段，前后空行
- **图片说明**：`![图NN 描述](path)` + 紧跟 `*图NN ·描述*`，前后空行
- **子节标记**：短词独立成段，前后空行，不加 Markdown 标题语法（`##`）
- **跨页段落**：PDF 提取时必须跨页合并，仅在遇终止符（`。！？!?`）或闭引号 + 开引号配对时 flush
- **frontmatter**：永远保留，只替换 body
- **GitHub 推送**：远程仓库 `mianozc/seed-trilogy`，分支 `main`
