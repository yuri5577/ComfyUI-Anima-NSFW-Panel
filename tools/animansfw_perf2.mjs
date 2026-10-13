/**
 * 阶段计时版：把「开面板」拆开，看 250ms 花在哪。
 *
 *   node tools/animansfw_perf2.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.dirname(HERE);
const SRC = path.join(PKG_ROOT, "web", "anima_nsfw_panel.js");

let elCount = 0, styleWrites = 0;
const RESET = () => { elCount = 0; styleWrites = 0; };

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

class El {
  constructor(tag) {
    elCount++;
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.style = new Proxy({}, {
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
}

const ctxStub = new Proxy({}, {
  get: (t, k) => (k === "canvas" ? { width: 800, height: 600 }
    : k === "measureText" ? (() => ({ width: 10 })) : typeof k === "string" ? () => {} : undefined),
  set: () => true,
});

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
globalThis.localStorage = { _d: {}, getItem(k) { return this._d[k] ?? null; }, setItem(k, v) { this._d[k] = String(v); }, removeItem(k) { delete this._d[k]; } };
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);
globalThis.cancelAnimationFrame = () => {};

// ---- 计时打点：包一层 fetch，量 JSON.parse 和数据处理 ----
const t0 = performance.now();
const FIXTURES = {};
const tagText = fs.readFileSync(path.join(HERE, "tags_fixture.json"), "utf8");
const tRead = performance.now();
FIXTURES.tags = JSON.parse(tagText);
const tParseTags = performance.now();
const charText = fs.readFileSync(path.join(PKG_ROOT, "web", "characters.json"), "utf8");
FIXTURES.chars = JSON.parse(charText);
const tParseChars = performance.now();
try {
  const sf = JSON.parse(fs.readFileSync(path.join(HERE, "story_fixture.json"), "utf8"));
  FIXTURES.story = sf.story; FIXTURES.storyScenes = sf.scenes;
} catch (e) { /* ignore */ }

console.log("=== 数据加载（Node 侧，浏览器里由 fetch 完成）===");
console.log(`  读文件        ${(tRead - t0).toFixed(0)} ms`);
console.log(`  JSON.parse tags     ${(tParseTags - tRead).toFixed(0)} ms   (${(tagText.length / 1048576).toFixed(1)} MB)`);
console.log(`  JSON.parse chars    ${(tParseChars - tParseTags).toFixed(0)} ms   (${(charText.length / 1048576).toFixed(1)} MB)`);

globalThis.fetch = async (url) => {
  const u = String(url);
  let data = null;
  if (u.includes("anima_nsfw/tags")) data = FIXTURES.tags;
  else if (u.includes("anima_nsfw/characters")) data = FIXTURES.chars;
  else if (u.includes("anima_nsfw/story/scene")) {
    const m = /[?&]arc=([^&]+)/.exec(u), ms = /[?&]scene=(\d+)/.exec(u), mc = /[?&]cast=([^&]*)/.exec(u);
    const k = m && ms && mc ? `${decodeURIComponent(m[1])}|${ms[1]}|${decodeURIComponent(mc[1])}` : "";
    const sc = FIXTURES.storyScenes?.[k];
    if (sc) data = { ok: true, scene: sc };
  } else if (u.includes("anima_nsfw/story")) data = FIXTURES.story;
  else if (u.includes("anima_nsfw/custom")) data = { ok: true, data: {}, info: { counts: {} } };
  else if (u.includes("anima_nsfw/preview")) data = { positive: "x".repeat(400), negative: "y".repeat(400), info: { tags: [] } };
  if (data == null) return { ok: false, status: 404, json: async () => ({}) };
  return { ok: true, status: 200, json: async () => data };
};

const graph = { links: {}, _nodes: [], _nodes_by_id: {}, setDirtyCanvas() {}, getNodeById(id) { return this._nodes_by_id[id] || null; } };
const registered = [];
globalThis.app = { registerExtension(e) { registered.push(e); }, graph, canvas: { setDirtyCanvas() {}, draw() {} } };

function makeNode(type, defs) {
  const node = {
    id: 1, type, size: [400, 320], widgets: [], properties: {}, inputs: [], outputs: [], graph,
    addWidget(kind, name, val, cb) { const w = { type: kind, name, label: name, value: val, callback: cb, options: {} }; node.widgets.push(w); return w; },
    addDOMWidget(name, t, element, options = {}) { const w = { name, type: t, element, options, serialize: false, value: "" }; node.widgets.push(w); return w; },
    computeSize() { return [400, 320]; }, setSize(s) { node.size = s; }, setDirtyCanvas() {},
  };
  for (const [n, v] of Object.entries(defs || {})) node.widgets.push({ name: n, value: v, options: {}, callback: null });
  return node;
}

const code = fs.readFileSync(SRC, "utf8");
const stubDir = path.join(process.env.TEMP || "/tmp", `animansfw_perf2_${process.pid}`);
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, "app_stub.mjs"), "export const app = globalThis.app;\nexport default globalThis.app;\n", "utf8");
const stubUrl = "file:///" + path.join(stubDir, "app_stub.mjs").replace(/\\/g, "/");
const patched = code.replace(/(["'])\.\.\/\.\.\/scripts\/[a-zA-Z_.\/-]+\1/g, JSON.stringify(stubUrl));
const shadow = path.join(stubDir, "__panel.mjs");
fs.writeFileSync(shadow, patched, "utf8");

const origWarn = console.warn; console.warn = () => {};
await import("file:///" + shadow.replace(/\\/g, "/"));
console.warn = origWarn;

const ext = registered[0];
const nodeType = { prototype: {} };
await ext.beforeRegisterNodeDef(nodeType, { name: "AnimaNsfwPromptBuilder" });
const node = makeNode("AnimaNsfwPromptBuilder", {
  mode: "NSFW（不限）", seed_mode: "固定（每次同图）", seed: 1234,
  tags: "1girl, solo", intensity: "hard", quality_preset: "无（自己写）",
  caption_enabled: true, caption_seed: 0, sort_tags: true, dedupe_tags: true,
  outfit_preset: "", pose_preset: "", caption_text: "", extra_front: "", extra_tail: "", upstream_prompt: "",
});
nodeType.prototype.onNodeCreated?.call(node);
const panelBtn = node.widgets.find((w) => w.type === "button" && String(w.label || "").includes("面板"));

console.log("\n=== 开面板阶段拆解（每段单独测）===");

// A) 只 buildPanel（数据已在内存）
console.log("\n  A. 重新打开面板（数据已缓存）：");
for (let i = 0; i < 3; i++) {
  RESET();
  const tA = performance.now();
  panelBtn.callback();
  await new Promise((r) => setTimeout(r, 200));
  const ms = performance.now() - tA;
  console.log(`     #${i + 1}  ${ms.toFixed(0)} ms   建 DOM ${elCount}   写 style ${styleWrites}`);
}

// B) 单独量几个热点
console.log("\n  B. 单个热点：");
const ov = body.children.filter((c) => String(c.className || "").includes("animansfw-overlay")).pop();

const measure = (label, fn) => {
  RESET();
  const t = performance.now();
  const r = fn();
  console.log(`     ${label.padEnd(34)} ${(performance.now() - t).toFixed(1).padStart(7)} ms   DOM ${String(elCount).padStart(6)}   style ${String(styleWrites).padStart(6)}`);
  return r;
};

// 侧栏：切到「游戏/作品」——会对 337 个作品各 filter 一次 8000 角色
const workCat = ov.allButtons().find((b) => b.__catId === "copyright");
if (workCat) {
  measure("切到「游戏/作品」（含作品→角色映射）", () => workCat.onclick({ target: workCat }));
}
// 角色视图
const charBtn = ov.allButtons().find((b) => String(b.textContent || "").includes("角色") && !b.__catId);
if (charBtn) {
  measure("切到角色视图（8000 角色）", () => charBtn.onclick({ target: charBtn }));
}
// 剧情
const storyBtn = ov.allButtons().find((b) => String(b.textContent || "").includes("剧情") && !b.__catId);
if (storyBtn) {
  measure("切到剧情视图", () => storyBtn.onclick({ target: storyBtn }));
}

// 全量统计一遍 rendering 的关键输入规模
console.log("\n  C. 规模：");
console.log(`     标签 ${FIXTURES.tags.tags.length}  角色 ${FIXTURES.chars.chars.length}  作品(角色库) ${new Set(FIXTURES.chars.chars.map(c => c.c)).size}`);
console.log(`     作品标签(版权) ${FIXTURES.tags.tags.filter(t => t.c === "copyright").length}`);
console.log(`     剧情 ${FIXTURES.story.arcs.length} 线 / ${FIXTURES.story.arcs.reduce((a, x) => a + x.scenes.length, 0)} 拍`);

fs.rmSync(stubDir, { recursive: true, force: true });
