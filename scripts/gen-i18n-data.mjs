// 从 src/lib/i18n.ts 生成 public/js/i18n-data.js
// 运行: node scripts/gen-i18n-data.mjs
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import vm from 'vm';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SRC = join(ROOT, 'src', 'lib', 'i18n.ts');
const OUT = join(ROOT, 'public', 'js', 'i18n-data.js');

const src = readFileSync(SRC, 'utf-8');

// 提取 dict 字面量：从 'export const dict' 到对应的 '};'
const startIdx = src.indexOf('export const dict');
if (startIdx === -1) throw new Error('dict not found');
// 从 '=' 后开始
const eqIdx = src.indexOf('=', startIdx);
let i = eqIdx + 1;
let depth = 0;
let started = false;
for (; i < src.length; i++) {
  const ch = src[i];
  if (ch === '{') { depth++; started = true; }
  else if (ch === '}') { depth--; if (started && depth === 0) break; }
}
const literal = src.slice(eqIdx + 1, i + 1).trim();

// 在沙箱中求值
const sandbox = {};
vm.createContext(sandbox);
const code = `dict = ${literal}`;
vm.runInContext(code, sandbox);
const dict = sandbox.dict;

// 输出为全局变量（兼容浏览器与 Node 验证）
const out = `// 由 src/lib/i18n.ts 生成，请勿手动编辑\n// 生成时间: ${new Date().toISOString()}\nglobalThis.SEED_I18N = ${JSON.stringify(dict, null, 2)};\n`;
writeFileSync(OUT, out, 'utf-8');
console.log(`i18n data: zh=${Object.keys(dict.zh).length}, en=${Object.keys(dict.en).length} keys -> ${join('public', 'js', 'i18n-data.js')}`);
