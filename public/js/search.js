// 《种子》三部曲 · 站内搜索
// 依赖 public/search-index.json（构建时生成）
(function () {
  const modal = document.getElementById('search-modal');
  const input = document.getElementById('search-input');
  const resultsEl = document.getElementById('search-results');
  if (!modal || !input || !resultsEl) return;

  const dict = window.SEED_I18N || { zh: {}, en: {} };
  let index = null;
  let lang = (document.documentElement.getAttribute('data-lang')) || 'zh';

  // 加载索引
  async function loadIndex() {
    if (index) return index;
    try {
      const res = await fetch('/search-index.json', { cache: 'no-cache' });
      index = (await res.json()).items;
    } catch (e) {
      index = [];
    }
    return index;
  }

  function getLang() {
    return (document.documentElement.getAttribute('data-lang')) || 'zh';
  }

  // 简单分词：中文按字、英文按词
  function tokenize(q) {
    const tokens = [];
    // 英文词
    const en = q.toLowerCase().match(/[a-z0-9]+/g);
    if (en) tokens.push(...en);
    // 中文（按单字 + 二字组合）
    const zh = q.match(/[\u4e00-\u9fa5]+/g);
    if (zh) {
      for (const seg of zh) {
        for (let i = 0; i < seg.length; i++) tokens.push(seg[i]);
        for (let i = 0; i < seg.length - 1; i++) tokens.push(seg.slice(i, i + 2));
      }
    }
    return [...new Set(tokens)];
  }

  function highlight(text, q) {
    if (!q) return text;
    const tokens = tokenize(q);
    if (!tokens.length) return text;
    let out = text;
    // 按长度降序，先替换长词
    const sorted = [...tokens].sort((a, b) => b.length - a.length);
    for (const tok of sorted) {
      if (tok.length < 1) continue;
      const re = new RegExp(tok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      out = out.replace(re, (m) => `\u0000${m}\u0001`);
    }
    return out.split('\u0000').map((seg) => {
      if (seg.includes('\u0001')) {
        const [inner] = seg.split('\u0001');
        return `<mark>${inner}</mark>` + seg.slice(inner.length + 1);
      }
      return seg;
    }).join('');
  }

  function search(q) {
    if (!q) return [];
    const items = index || [];
    const tokens = tokenize(q);
    if (!tokens.length) return [];

    const scored = items.map((it) => {
      const title = (it[`title_${lang}`] || it.title_zh || '').toLowerCase();
      const snip = (it[`snip_${lang}`] || it.snip_zh || '').toLowerCase();
      const book = (it[`book_${lang}`] || it.book_zh || '').toLowerCase();
      const hay = (title + ' ' + snip + ' ' + book).toLowerCase();
      let score = 0;
      for (const tok of tokens) {
        if (!tok) continue;
        if (title.includes(tok.toLowerCase())) score += tok.length * 4;
        if (book.includes(tok.toLowerCase())) score += tok.length * 2;
        if (snip.includes(tok.toLowerCase())) score += tok.length;
      }
      return { it, score };
    }).filter((x) => x.score > 0).sort((a, b) => b.score - a.score).slice(0, 12);

    return scored;
  }

  function render(q) {
    const L = getLang();
    lang = L;
    if (!q.trim()) {
      resultsEl.innerHTML = `<p class="search-hint" data-i18n="search.hint">${dict[L]['search.hint'] || ''}</p>`;
      return;
    }
    const hits = search(q);
    if (!hits.length) {
      resultsEl.innerHTML = `<p class="search-empty" data-i18n="search.empty">${dict[L]['search.empty'] || ''}</p>`;
      return;
    }
    const countLabel = dict[L]['search.resultCount'] || 'results';
    const inLabel = dict[L]['search.in'] || 'in';
    const openLabel = dict[L]['search.open'] || 'Open';
    const rows = hits.map(({ it }) => {
      const title = it[`title_${L}`] || it.title_zh || '';
      const snip = it[`snip_${L}`] || it.snip_zh || '';
      const book = it[`book_${L}`] || it.book_zh || '';
      const catLabel = it.cat === 'page'
        ? (L === 'zh' ? '页面' : 'page')
        : book;
      return `<a class="search-item" href="${it.href}" data-search-close>
        <span class="si-title"><span>${highlight(title, q)}</span><span class="si-cat">${catLabel}</span></span>
        <span class="si-snip">${highlight(snip, q)}</span>
      </a>`;
    }).join('');
    resultsEl.innerHTML = `<p class="search-count">${hits.length} ${countLabel}</p>` + rows;
  }

  function open() {
    modal.hidden = false;
    loadIndex().then(() => {
      input.focus();
      input.value = '';
      render('');
    });
  }
  function close() {
    modal.hidden = true;
    input.value = '';
  }

  // 事件
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-search-open]')) { e.preventDefault(); open(); }
    else if (e.target.closest('[data-search-close]')) { e.preventDefault(); close(); }
  });
  document.addEventListener('keydown', (e) => {
    // ⌘K / Ctrl+K
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      modal.hidden ? open() : close();
    } else if (e.key === 'Escape' && !modal.hidden) {
      close();
    }
  });
  input.addEventListener('input', () => render(input.value.trim()));

  // 语言切换时重新渲染
  window.addEventListener('seed:langchange', () => {
    if (!modal.hidden) render(input.value.trim());
  });
})();
