import { defineConfig } from 'astro/config';

// 给题词（独立短句以引号起）加 class，便于楷体灰处理
function rehypeEpigraph() {
  const walk = (node, fn) => {
    fn(node);
    if (node.children) for (const c of node.children) walk(c, fn);
  };
  return (tree) => {
    walk(tree, (node) => {
      if (node.type !== 'element' || node.tagName !== 'p') return;
      const text = (node.children || [])
        .map((c) => (c.type === 'text' ? c.value : ''))
        .join('')
        .trim();
      if (
        text.length > 0 &&
        text.length <= 48 &&
        (text.startsWith('"') || text.startsWith('“') || text.startsWith('「'))
      ) {
        node.properties = node.properties || {};
        node.properties.className = 'epigraph';
      }
    });
  };
}

// 《种子》三部曲 — 人类与 AI 共同创作的存在档案
// 纯静态站点，可部署到 Cloudflare Pages / Netlify / GitHub Pages 等免费静态托管
export default defineConfig({
  site: 'https://seed-trilogy.org',
  output: 'static',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  devToolbar: { enabled: false },
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark', wrap: false },
    rehypePlugins: [rehypeEpigraph],
  },
});
