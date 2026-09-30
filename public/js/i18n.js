// 《种子》三部曲 · 客户端 i18n 运行时
// 依赖 public/js/i18n-data.js（window.SEED_I18N）
(function () {
  const KEY = 'seed-lang';
  const dict = window.SEED_I18N || { zh: {}, en: {} };

  function getLang() {
    const saved = localStorage.getItem(KEY);
    if (saved === 'en' || saved === 'zh') return saved;
    // 浏览器语言检测
    const nav = (navigator.language || 'zh').toLowerCase();
    return nav.startsWith('zh') ? 'zh' : 'en';
  }

  function apply(lang) {
    const other = lang === 'zh' ? 'en' : 'zh';
    document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : 'en';
    document.documentElement.setAttribute('data-lang', lang);

    // 1. data-i18n 元素：替换文本
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      const val = dict[lang][key];
      if (val != null) {
        // 保留 aria-label 等属性也走 data-i18n-attr
        el.textContent = val;
      }
    });

    // 2. data-i18n-attr="attr:key" 属性翻译
    document.querySelectorAll('[data-i18n-attr]').forEach((el) => {
      const spec = el.getAttribute('data-i18n-attr') || '';
      spec.split(';').forEach((pair) => {
        const [attr, key] = pair.split(':');
        if (!attr || !key) return;
        const val = dict[lang][key.trim()];
        if (val != null) el.setAttribute(attr.trim(), val);
      });
    });

    // 3. data-lang-zh / data-lang-en 成对元素：显示当前语言，隐藏另一种
    document.querySelectorAll('[data-lang-zh]').forEach((el) => {
      el.hidden = lang !== 'zh';
    });
    document.querySelectorAll('[data-lang-en]').forEach((el) => {
      el.hidden = lang !== 'en';
    });

    // 4. 切换按钮状态
    document.querySelectorAll('[data-lang-toggle]').forEach((btn) => {
      const label = dict[lang][other === 'zh' ? 'lang.zh' : 'lang.en'];
      btn.textContent = label;
      btn.setAttribute('aria-label', dict[lang]['lang.toggle']);
    });

    // 触发自定义事件，便于其他脚本（如搜索）响应语言切换
    window.dispatchEvent(new CustomEvent('seed:langchange', { detail: { lang } }));
  }

  function setLang(lang) {
    localStorage.setItem(KEY, lang);
    apply(lang);
  }

  function toggle() {
    setLang(getLang() === 'zh' ? 'en' : 'zh');
  }

  // 初始化
  const lang = getLang();
  // 尽早设置 data-lang，避免闪烁
  document.documentElement.setAttribute('data-lang', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : 'en';

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => apply(lang));
  } else {
    apply(lang);
  }

  // 绑定切换按钮
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-lang-toggle]');
    if (btn) { e.preventDefault(); toggle(); }
  });

  // 暴露 API
  window.SeedI18n = { getLang, setLang, toggle, apply };
})();
