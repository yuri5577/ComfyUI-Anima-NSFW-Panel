/**
 * 性能基准：用真实数据规模（11097 标签 / 8000 角色）跑面板的关键操作。
 *
 *   node tools/animansfw_perf.mjs
 *
 * 不需要启动 ComfyUI，不联网（fetch 全走桩）。
 *
 * 看两个核心指标：
 *   建 DOM   —— 一次交互新建了多少节点（原来开面板要建 11 万个）
 *   写 style —— 写了多少次样式（原来 62 万次，会累积成严重卡顿）
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.dirname(HERE);
const SRC = path.join(PKG_ROOT, "web", "anima_nsfw_panel.js");

let elCount = 0;
let styleWrites = 0;
const RESET = () => { elCount = 0; styleWrites = 0; };

// ---------------------------------------------------------------- DOM 桩
function matchesSel(el, sel) {
  let m = /^([a-zA-Z]*)\[([\w-]+)(?:=["']?([^"']*)["']?)?\]$/.exec(sel);
  if (m) {
    const [, tag, attr, val] = m;
    if (tag && el.__tag !== tag.toLowerCase()) return false;
    const have = el[attr];
    if (have === undefined || have === null) return false;
    if (val !== undefined && String(have) !== val) return false;
    return true;
  }
  m = /^\.([\w-]+)$/.exec(sel);
  if (m) return String(el.className || "").includes(m[1]);
  return el.__tag === sel.toLowerCase();
}

const ctxStub = new Proxy({}, {
  get: (t, k) => (k === "canvas" ? { width: 800, height: 600 }
    : k === "measureText" ? (() => ({ width: 10 }))
      : typeof k === "string" ? () => {} : undefined),
  set: () => true,
});

class El {
  constructor(tag) {
    elCount++;
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    // 用 Proxy 计 style 写入次数；真实浏览器里每次赋值都可能触发样式重算
    this.style = new Proxy({ cssText: "" }, {
      get: (t, k) => t[k] ?? "",
      set: (t, k, v) => { styleWrites++; t[k] = v; return true; },
    });
    this.dataset = {};
    this.classList = { add() {}, remove() {}, contains: () => false };
    this._text = ""; this._html = ""; this.value = ""; this.checked = false;
    this.files = []; this.listeners = {}; this.parentNode = null; this.__tag = tag;
  }
  set textContent(v) { this._text = String(v ?? ""); this.children.length = 0; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  set innerHTML(v) { this._html = String(v ?? ""); this.children.length = 0; }
  get innerHTML() { return this._html; }
  appendChild(c) { this.children.push(c); c.parentNode = this; return c; }
  insertBefore(c, ref) {
    const i = ref ? this.children.indexOf(ref) : -1;
    if (i >= 0) this.children.splice(i, 0, c); else this.children.push(c);
    c.parentNode = this; return c;
  }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; }
  remove() { this.parentNode?.removeChild(this); }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  removeEventListener() {}
  setAttribute(k, v) { this[k] = v; }
  getAttribute(k) { return this[k] ?? null; }
  querySelector(sel) {
    const walk = (n) => {
      for (const c of n.children) { if (matchesSel(c, sel)) return c; const r = walk(c); if (r) return r; }
      return null;
    };
    return walk(this);
  }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 600 }; }
  getContext() { return ctxStub; }
  focus() {}
  setSelectionRange() {}
  allButtons(out = []) { for (const c of this.children) { if (c.__tag === "button") out.push(c); c.allButtons(out); } return out; }
  visibleButtons(out = []) {
    for (const c of this.children) {
      const hidden = c.style && (c.style.display === "none" || c.style.visibility === "hidden");
      if (!hidden) { if (c.__tag === "button") out.push(c); c.visibleButtons(out); }
    }
    return out;
  }
  byText(needle) { return this.visibleButtons().filter((b) => String(b.label || b.textContent || "").includes(needle)); }
}

const body = new El("body");
globalThis.document = {
  body, createElement: (t) => new El(t), createDocumentFragment: () => new El("fragment"),
  querySelector: (s) => body.querySelector(s), querySelectorAll: () => [],
  addEventListener() {}, removeEventListener() {},
};
globalThis.window = globalThis;
globalThis.alert = () => {};
try {
  Object.defineProperty(globalThis, "navigator", {
    configurable: true, value: { clipboard: { writeText: async () => {} }, language: "zh-CN" },
  });
} catch (e) { /* ignore */ }
globalThis.localStorage = {
  _d: {}, getItem(k) { return this._d[k] ?? null; },
  setItem(k, v) { this._d[k] = String(v); }, removeItem(k) { delete this._d[k]; },
};
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);
globalThis.cancelAnimationFrame = () => {};

// ---------------------------------------------------------------- 数据
const FIXTURES = {};
FIXTURES.tags = JSON.parse(fs.readFileSync(path.join(HERE, "tags_fixture.json"), "utf8"));
FIXTURES.chars = JSON.parse(fs.readFileSync(path.join(PKG_ROOT, "web", "characters.json"), "utf8"));
try {
  const sf = JSON.parse(fs.readFileSync(path.join(HERE, "story_fixture.json"), "utf8"));
  FIXTURES.story = sf.story;
  FIXTURES.storyScenes = sf.scenes;
} catch (e) { /* ignore */ }

console.log(`数据规模：标签 ${FIXTURES.tags.tags.length} / 角色 ${FIXTURES.chars.chars.length}`);

let fetchCount = 0;
globalThis.fetch = async (url) => {
  fetchCount++;
  const u = String(url);
  let data = null;
  if (u.includes("anima_nsfw/tags")) data = FIXTURES.tags;
  else if (u.includes("anima_nsfw/characters")) data = FIXTURES.chars;
  else if (u.includes("anima_nsfw/story/scene")) {
    const m = /[?&]arc=([^&]+)/.exec(u);
    const ms = /[?&]scene=(\d+)/.exec(u);
    const mc = /[?&]cast=([^&]*)/.exec(u);
    const k = m && ms && mc ? `${decodeURIComponent(m[1])}|${ms[1]}|${decodeURIComponent(mc[1])}` : "";
    const sc = FIXTURES.storyScenes?.[k];
    if (sc) data = { ok: true, scene: sc };
  } else if (u.includes("anima_nsfw/story")) data = FIXTURES.story;
  else if (u.includes("anima_nsfw/custom")) data = { ok: true, data: {}, info: { counts: {} } };
  else if (u.includes("anima_nsfw/preview")) {
    data = { positive: "x".repeat(400), negative: "y".repeat(400), info: { tags: [] } };
  }
  if (data == null) return { ok: false, status: 404, json: async () => ({}) };
  return { ok: true, status: 200, json: async () => data };
};

// ---------------------------------------------------------------- 节点桩
const graph = {
  links: {}, _nodes: [], _nodes_by_id: {}, setDirtyCanvas() {},
  getNodeById(id) { return this._nodes_by_id[id] || null; },
};
const registered = [];
globalThis.app = { registerExtension(e) { registered.push(e); }, graph, canvas: { setDirtyCanvas() {}, draw() {} } };

function makeNode(type, defs) {
  const node = {
    id: 1, type, size: [400, 320], widgets: [], properties: {}, inputs: [], outputs: [], graph,
    addWidget(kind, name, val, cb) {
      const w = { type: kind, name, label: name, value: val, callback: cb, options: {} };
      node.widgets.push(w); return w;
    },
    addDOMWidget(name, t, element, options = {}) {
      const w = { name, type: t, element, options, serialize: false, value: "" };
      node.widgets.push(w); return w;
    },
    computeSize() { return [400, 320]; },
    setSize(s) { node.size = s; },
    setDirtyCanvas() {},
  };
  for (const [n, v] of Object.entries(defs || {})) {
    node.widgets.push({ name: n, value: v, options: {}, callback: null });
  }
  return node;
}

// ---------------------------------------------------------------- 跑
const code = fs.readFileSync(SRC, "utf8");
const stubDir = path.join(process.env.TEMP || "/tmp", `animansfw_perf_${process.pid}`);
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, "app_stub.mjs"),
  "export const app = globalThis.app;\nexport default globalThis.app;\n", "utf8");
const stubUrl = "file:///" + path.join(stubDir, "app_stub.mjs").replace(/\\/g, "/");
const patched = code.replace(/(["'])\.\.\/\.\.\/scripts\/[a-zA-Z_.\/-]+\1/g, JSON.stringify(stubUrl));
const shadow = path.join(stubDir, "__panel.mjs");
fs.writeFileSync(shadow, patched, "utf8");

const origWarn = console.warn;
console.warn = () => {};
await import("file:///" + shadow.replace(/\\/g, "/"));
console.warn = origWarn;

const ext = registered[0];
const nodeType = { prototype: {} };
await ext.beforeRegisterNodeDef(nodeType, { name: "AnimaNsfwPromptBuilder" });

const node = makeNode("AnimaNsfwPromptBuilder", {
  mode: "NSFW（不限）", seed_mode: "固定（每次同图）", seed: 1234,
  tags: "1girl, solo", intensity: "hard", quality_preset: "无（自己写）",
  caption_enabled: true, caption_seed: 0, sort_tags: true, dedupe_tags: true,
  outfit_preset: "", pose_preset: "", caption_text: "", extra_front: "",
  extra_tail: "", upstream_prompt: "",
});
nodeType.prototype.onNodeCreated?.call(node);

const panelBtn = node.widgets.find((w) => w.type === "button" && String(w.label || "").includes("面板"));
if (!panelBtn) {
  console.error("!! 找不到「打开面板」按钮");
  process.exit(1);
}

async function openPanel() {
  RESET();
  panelBtn.callback();
  await new Promise((r) => setTimeout(r, 300));
  const ov = body.children.filter((c) => String(c.className || "").includes("animansfw-overlay")).pop();
  return { ov, els: elCount, styles: styleWrites };
}

function time(label, fn) {
  RESET();
  const t = performance.now();
  fn();
  return { label, ms: performance.now() - t, de: elCount, ds: styleWrites };
}

function report(rows) {
  console.log(`\n${"操作".padEnd(30)}${"耗时".padStart(10)}${"建 DOM".padStart(10)}${"写 style".padStart(11)}`);
  console.log("-".repeat(63));
  for (const r of rows) {
    if (r.note) {
      console.log(`${r.label.padEnd(30)}${"—".padStart(10)}${String(r.de).padStart(10)}`
        + `${String(r.ds).padStart(11)}  ${r.note}`);
      continue;
    }
    const flag = r.ms > 100 ? "  ← 卡" : r.ms > 30 ? "  ← 偏慢" : "";
    console.log(`${r.label.padEnd(30)}${(r.ms.toFixed(1) + " ms").padStart(10)}`
      + `${String(r.de).padStart(10)}${String(r.ds).padStart(11)}${flag}`);
  }
}

const rows = [];

// 1) 开面板（含全部数据）
const o1 = await openPanel();
rows.push({ label: "开面板（首次）", ms: 0, de: o1.els, ds: o1.styles, note: "（含整个面板的 DOM 构建）" });
let ov = o1.ov;

// 2) 开面板（第二次）
const o2 = await openPanel();
rows.push({ label: "开面板（第二次）", ms: 0, de: o2.els, ds: o2.styles });
ov = o2.ov;

// 3) 切换分类
const catBtns = ov.allButtons().filter((b) => b.__catId);
if (catBtns.length > 1) {
  const cat = catBtns[1];
  rows.push(time(`切分类「${String(cat.textContent).slice(0, 10)}」`, () => cat.onclick({ target: cat })));
}

// 4) 点一个标签
const cards = ov.allButtons().filter((b) => b.onclick && b.children.length === 2
  && String(b.textContent || "").length > 1 && b.__catId === undefined);
if (cards.length) {
  rows.push(time("点一个标签", () => cards[0].onclick({ target: cards[0] })));
}

// 5) 搜索框输入
const searchInput = ov.querySelector('input[type="text"]');
if (searchInput) {
  rows.push(time("搜索框输入 1 个字符", () => {
    searchInput.value = "girl";
    (searchInput.listeners.input || []).forEach((f) => f({ target: searchInput }));
  }));
}

// 6) 切到「游戏/作品」（会建 337 个作品 + 作品→角色映射）
const workCat = ov.allButtons().find((b) => b.__catId === "copyright");
if (workCat) {
  rows.push(time("切到「游戏/作品」分类", () => workCat.onclick({ target: workCat })));
  await new Promise((r) => setTimeout(r, 150));
}

// 7) 展开一个作品
const workRows = ov.allButtons().filter((b) => String(b.title || "").includes("个角色"));
if (workRows.length) {
  rows.push(time("展开一个作品的角色", () => workRows[0].onclick({ target: workRows[0] })));
}

// 8) 剧情视图
const storyBtn = ov.byText("剧情")[0];
if (storyBtn) {
  rows.push(time("切到剧情视图", () => storyBtn.onclick({ target: storyBtn })));
  await new Promise((r) => setTimeout(r, 300));
}

// 9) 角色视图
ov = body.children.filter((c) => String(c.className || "").includes("animansfw-overlay")).pop();
const charBtn = ov?.allButtons().find((b) => String(b.textContent || "").includes("角色") && !b.__catId);
if (charBtn) {
  rows.push(time("切到角色视图", () => charBtn.onclick({ target: charBtn })));
  await new Promise((r) => setTimeout(r, 300));
}

// 10) 预览请求防抖：连点 5 个标签
ov = body.children.filter((c) => String(c.className || "").includes("animansfw-overlay")).pop();
const tagCat = ov?.allButtons().find((b) => b.__catId && b.__catId !== "copyright");
if (tagCat) tagCat.onclick({ target: tagCat });
const tagCards = (ov?.allButtons() || []).filter((b) => b.onclick && b.children.length === 2
  && String(b.textContent || "").length > 1 && b.__catId === undefined);
if (tagCards.length >= 5) {
  const before = fetchCount;
  for (let i = 0; i < 5; i++) tagCards[i].onclick({ target: tagCards[i] });
  await new Promise((r) => setTimeout(r, 80));
  const during = fetchCount - before;
  await new Promise((r) => setTimeout(r, 600));
  const after = fetchCount - before;
  rows.push({
    label: "连点 5 个标签的预览请求", ms: 0, de: 0, ds: 0,
    note: `连点后立即 ${during} 次 / 稳定后 ${after} 次（防抖前：5 次）`,
  });
}

report(rows);
console.log(`\n预览/数据请求累计: ${fetchCount} 次`);
console.log("\n判读：");
console.log(`  「建 DOM」和「写 style」是一次交互新增的数量。`);
console.log(`  开面板应保持在几千以内 —— 曾经漏掉分页时这里是 11 万 / 62 万，` +
  `全同步执行，一开面板就卡死。`);

fs.rmSync(stubDir, { recursive: true, force: true });
