/**
 * 面板 JS 离线冒烟测试（不启动 ComfyUI、不联网）。
 *
 *   node tools/animansfw_panel_smoke.mjs            # 现代前端
 *   node tools/animansfw_panel_smoke.mjs --legacy   # 模拟低版本 ComfyUI 前端
 *
 * legacy 模式会剥掉：node.addDOMWidget / requestAnimationFrame /
 * localStorage / navigator.clipboard / element.style.cssText，
 * 用来验证「低版本打不开面板」的兜底路径。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const LEGACY = process.argv.includes("--legacy");
// 老前端（1.12.x）契约：addDOMWidget 只吃 3 个参数、widget 上没有 options
const OLD_FE = process.argv.includes("--oldfe");
const SELF_DIR = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.dirname(SELF_DIR);            // <包>/tools -> <包>
const HERE = SELF_DIR;                             // 别名（下面读 fixture 用）
const SRC = process.argv.find((a) => a.endsWith(".js"))
  || path.join(PKG_ROOT, "web", "anima_nsfw_panel.js");

const problems = [];
const notes = [];
const ok = (m) => notes.push("OK   " + m);
const bad = (m) => problems.push("ERR  " + m);
const info = (m) => notes.push("     " + m);

console.log(`模式: ${LEGACY ? "legacy（低版本前端）" : "modern"}`
  + `${OLD_FE ? " + oldfe（老前端 addDOMWidget 契约）" : ""}  源文件: ${SRC}\n`);

// ---------------------------------------------------------------- DOM 桩
/** 极简 CSS 选择器匹配：支持 tag / .class / [attr=value] / tag[attr=value] */
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
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.style = new Proxy({}, {
      get: (t, k) => {
        if (k === "cssText" && LEGACY) throw new Error("legacy: 不支持 cssText");
        return t[k] ?? "";
      },
      set: (t, k, v) => {
        if (k === "cssText" && LEGACY) throw new Error("legacy: 不支持 cssText");
        t[k] = v;
        return true;
      },
    });
    this.dataset = {};
    this.classList = { add() {}, remove() {}, contains: () => false };
    this._text = "";
    this._html = "";
    this.value = "";
    this.checked = false;
    this.files = [];
    this.listeners = {};
    this.parentNode = null;
    this.__tag = tag;
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
    const s = String(sel).trim();
    const walk = (n) => {
      for (const c of n.children) {
        if (matchesSel(c, s)) return c;
        const r = walk(c); if (r) return r;
      }
      return null;
    };
    return walk(this);
  }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 600 }; }
  getContext() { return ctxStub; }
  focus() {}
  setSelectionRange() {}
  allButtons(out = []) {
    for (const c of this.children) {
      if (c.__tag === "button") out.push(c);
      c.allButtons(out);
    }
    return out;
  }
  /** 只算"可见"的按钮：模拟 display:none（真实浏览器里点不到） */
  visibleButtons(out = []) {
    for (const c of this.children) {
      const hidden = c.style && (c.style.display === "none" || c.style.visibility === "hidden");
      if (!hidden) {
        if (c.__tag === "button") out.push(c);
        c.visibleButtons(out);
      }
    }
    return out;
  }
  byText(needle) {
    return this.visibleButtons()
      .filter((b) => String(b.label || b.textContent || "").includes(needle));
  }
}

const ctxStub = new Proxy({}, {
  get: (t, k) => {
    if (k === "canvas") return { width: 800, height: 600 };
    if (k === "measureText") return () => ({ width: 10 });
    return typeof k === "string" ? () => {} : undefined;
  },
  set: () => true,
});

const body = new El("body");
globalThis.document = {
  body,
  createElement: (t) => new El(t),
  createDocumentFragment: () => new El("fragment"),
  querySelector: (s) => body.querySelector(s),
  querySelectorAll: () => [],
  addEventListener() {},
  removeEventListener() {},
};
globalThis.window = globalThis;
globalThis.alert = (m) => info("ALERT " + m);
try {
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: LEGACY
      ? { language: "zh-CN" }                                  // 没有 clipboard
      : { clipboard: { writeText: async () => {} }, language: "zh-CN" },
  });
} catch (e) { /* ignore */ }

if (LEGACY) {
  delete globalThis.localStorage;                              // 老前端可能没有
  globalThis.requestAnimationFrame = undefined;                 // 也可能没有
  globalThis.cancelAnimationFrame = undefined;
  info("legacy: 已移除 localStorage / requestAnimationFrame / clipboard");
} else {
  globalThis.localStorage = {
    _d: {},
    getItem(k) { return this._d[k] ?? null; },
    setItem(k, v) { this._d[k] = String(v); },
    removeItem(k) { delete this._d[k]; },
  };
  globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);
}

// ---------------------------------------------------------------- fetch 桩
const PKG = PKG_ROOT;   // .../ComfyUI-Anima-NSFW-Panel
const FIXTURES = {};
try {
  FIXTURES.tags = JSON.parse(fs.readFileSync(path.join(HERE, "tags_fixture.json"), "utf8"));
  info("已载入 tags_fixture.json");
} catch (e) {
  info("缺少 tags_fixture.json（先跑 tools/animansfw_make_fixture.py）");
}
try {
  FIXTURES.chars = JSON.parse(fs.readFileSync(path.join(PKG, "web/characters.json"), "utf8"));
} catch (e) { /* ignore */ }
try {
  const sf = JSON.parse(fs.readFileSync(path.join(HERE, "story_fixture.json"), "utf8"));
  FIXTURES.story = sf.story;
  FIXTURES.storyScenes = sf.scenes;
  info(`已载入 story_fixture.json（${(sf.story.arcs || []).length} 条故事线 / `
    + `${Object.keys(sf.scenes || {}).length} 拍）`);
} catch (e) {
  info("缺少 story_fixture.json（先跑 tools/animansfw_make_fixture.py）");
}

let fetchCount = 0;
globalThis.fetch = async (url) => {
  fetchCount++;
  const u = String(url);
  let data = null;
  if (u.includes("anima_nsfw/tags")) data = FIXTURES.tags;
  else if (u.includes("anima_nsfw/characters")) data = FIXTURES.chars;
  else if (u.includes("anima_nsfw/custom")) {
    data = { ok: true, data: { trigger: [], character: [], outfit: [], pose: [] }, info: {} };
  } else if (u.includes("anima_nsfw/story/scene")) {
    const m = /[?&]arc=([^&]+)/.exec(u);
    const ms = /[?&]scene=(\d+)/.exec(u);
    const mc = /[?&]cast=([^&]*)/.exec(u);
    const key = (m && ms && mc)
      ? `${decodeURIComponent(m[1])}|${ms[1]}|${decodeURIComponent(mc[1])}` : "";
    const sc = FIXTURES.storyScenes?.[key];
    if (sc) data = { ok: true, scene: sc };
  } else if (u.includes("anima_nsfw/story")) {
    data = FIXTURES.story;
  } else if (u.includes("anima_nsfw/preview")) {
    data = { positive: "(stub)", negative: "(stub)", info: { tags: ["1girl"], caption: "" } };
  }
  if (data == null) return { ok: false, status: 404, json: async () => ({}) };
  return { ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data) };
};

// ---------------------------------------------------------------- app 桩
const graph = {
  links: {},
  _nodes: [],
  _nodes_by_id: {},
  setDirtyCanvas() {},
  getNodeById(id) {
    if (OLD_FE) return null;          // 老前端没有这个 API
    return this._nodes_by_id[id] || null;
  },
};

const registered = [];
globalThis.app = {
  registerExtension(ext) { registered.push(ext); },
  graph,
  canvas: { setDirtyCanvas() {}, draw() {}, setDirty() {} },
};

// ---------------------------------------------------------------- 节点桩
function makeNode(type, defs) {
  const node = {
    id: 1, type, size: [400, 320], widgets: [], properties: {},
    inputs: [], outputs: [],
    addWidget(kind, name, val, cb) {
      // 老前端契约：按钮类 widget 不带 options 字段
      const w = OLD_FE
        ? { type: kind, name, label: name, value: val, callback: cb }
        : { type: kind, name, label: name, value: val, callback: cb, options: {} };
      node.widgets.push(w);
      return w;
    },
    computeSize() { return [400, 320]; },
    setSize(s) { node.size = s; },
    setDirtyCanvas() {},
    graph,
  };
  if (!LEGACY) {
    if (OLD_FE) {
      // 老前端：第 4 个参数被忽略，widget 上没有 options
      node.addDOMWidget = (name, t, element) => {
        const w = { name, type: t, element, serialize: false, value: "" };
        node.widgets.push(w);
        return w;
      };
    } else {
      node.addDOMWidget = (name, t, element, options = {}) => {
        const w = { name, type: t, element, options, serialize: false, value: "" };
        node.widgets.push(w);
        return w;
      };
    }
  }
  for (const [n, v] of Object.entries(defs || {})) {
    node.widgets.push({ name: n, value: v, options: {}, callback: null });
  }
  return node;
}

// ---- 假图：提示词面板 → KSampler（输出连线 + 种子控件），用来验证种子推送 ----
const samplers = [];

function makeSampler(id, seed, control) {
  const w = { name: "seed", value: seed, options: {}, callback: null, linkedWidgets: [] };
  if (control) w.options.control_after_generate = control;
  const n = { id, type: "KSampler", title: "KSampler", widgets: [w],
    inputs: [], outputs: [], graph, setDirtyCanvas() {} };
  graph._nodes.push(n);
  graph._nodes_by_id[id] = n;
  samplers.push(n);
  return n;
}

/** 接上输出连线（真实 ComfyUI：slot.links=[linkId]，graph.links[linkId]={target_id}） */
function wireTo(node, targets, startLinkId = 100) {
  let lid = startLinkId;
  node.outputs = [{ name: "positive", links: [] }, { name: "info", links: [] }];
  for (const t of targets) {
    // 老前端的 link 对象用 target 字段（新的是 target_id）；两种都给上，
    // 面板的遍历逻辑要能兼容
    graph.links[lid] = OLD_FE
      ? { id: lid, origin_id: node.id, target: t.id, target_slot: 0 }
      : { id: lid, origin_id: node.id, target_id: t.id, target_slot: 0 };
    node.outputs[0].links.push(lid);
    lid++;
  }
  node.graph = graph;
  return node;
}

function readTagsOf(n) {
  const w = n.widgets.find((x) => x.name === "tags");
  return String(w?.value ?? "");
}

// ---------------------------------------------------------------- 跑
const code = fs.readFileSync(SRC, "utf8");
const COMFY_ROOT = process.env.COMFY_ROOT
  || path.dirname(path.dirname(path.dirname(PKG_ROOT)));   // 未用到也留着
const stubDir = path.join(process.env.TEMP || "/tmp", `animansfw_stub_${process.pid}`);
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, "app_stub.mjs"),
  "export const app = globalThis.app;\nexport default globalThis.app;\n", "utf8");
const stubUrl = "file:///" + path.join(stubDir, "app_stub.mjs").replace(/\\/g, "/");
let patched = code.replace(/(["'])\.\.\/\.\.\/scripts\/[a-zA-Z_.\/-]+\1/g, JSON.stringify(stubUrl));
if (patched === code) bad("没找到 ../../scripts/app.js 的 import");
const shadow = path.join(stubDir, "__panel_under_test__.mjs");
fs.writeFileSync(shadow, patched, "utf8");
const cleanup = () => { try { fs.rmSync(stubDir, { recursive: true, force: true }); } catch (e) {} };

const origWarn = console.warn;
console.warn = (...a) => info("console.warn: " + a.map(String).join(" ").slice(0, 140));

try {
  await import("file:///" + shadow.replace(/\\/g, "/"));
  ok("模块加载成功（顶层无异常）");
} catch (e) {
  bad("模块加载抛异常: " + e.message);
  console.warn = origWarn;
  console.log(notes.join("\n"));
  console.log(problems.join("\n"));
  cleanup();
  process.exit(1);
}

const ext = registered[0];
if (!ext) { bad("没有注册扩展（面板按钮必然点不动）"); cleanup(); process.exit(1); }
ok(`注册扩展: ${ext.name}`);

// 1. 提示词面板
const nodeType = { prototype: {} };
try {
  await ext.beforeRegisterNodeDef(nodeType, { name: "AnimaNsfwPromptBuilder" });
  ok("beforeRegisterNodeDef 执行成功");
} catch (e) {
  bad("beforeRegisterNodeDef 抛异常: " + e.message);
}

const node = makeNode("AnimaNsfwPromptBuilder", {
  mode: "NSFW（不限）",
  seed_mode: "固定（每次同图）", seed: 1234,
  tags: "1girl, solo", intensity: "hard", quality_preset: "无（自己写）",
  caption_enabled: true, caption_seed: 0, sort_tags: true, dedupe_tags: true,
  outfit_preset: "", pose_preset: "", caption_text: "", extra_front: "",
  extra_tail: "", upstream_prompt: "",
});
// 接两个下游 KSampler，用来验证种子推送
const s1 = makeSampler(9001, 111, null);
const s2 = makeSampler(9002, 222, null);
wireTo(node, [s1, s2]);
ok(`已接 ${samplers.length} 个假 KSampler 到面板节点`);

try {
  nodeType.prototype.onNodeCreated?.call(node);
  ok("onNodeCreated（setupBuilder）执行成功");
} catch (e) {
  bad("onNodeCreated 抛异常: " + e.message + " | " + String(e.stack || "").split("\n")[1]);
}

const btn = node.widgets.find((w) => w.type === "button" && String(w.label || "").includes("面板"));
if (!btn) {
  bad("找不到「打开面板」按钮（用户会表现为「点了没反应 / 没这个按钮」）");
} else {
  ok(`找到按钮: ${btn.label}`);
  try {
    btn.callback();
    await new Promise((r) => setTimeout(r, 80));
    const latestOverlay = () => body.children.filter(
      (c) => String(c.className || "").includes("animansfw-overlay")).pop() || null;

    /** 只保留最新面板（模拟真实 closePanel），并返回它 */
    const keepLatest = () => {
      const all = body.children.filter(
        (c) => String(c.className || "").includes("animansfw-overlay"));
      while (all.length > 1) body.removeChild(all.shift());
      return all[all.length - 1] || null;
    };

    /** 重新打开面板并返回全新的 overlay（每段断言前调用） */
    const panelBtn = () => node.widgets.find(
      (w) => w.type === "button" && String(w.label || "").includes("面板"));
    const openFresh = async (wait = 140) => {
      panelBtn()?.callback();
      await new Promise((r) => setTimeout(r, wait));
      return keepLatest();
    };

    /** 递归找含某段文字的任意元素（byText 只看按钮） */
    const anyWithText = (root, needle) => {
      const out = [];
      const walk = (n) => {
        for (const c of n.children) {
          if (String(c.textContent || "").includes(needle)) out.push(c);
          walk(c);
        }
      };
      walk(root);
      return out;
    };

    const overlay = latestOverlay();
    if (!overlay) {
      bad("点击后面板浮层没出现（body 子节点 " + body.children.length + " 个）");
    } else {
      ok("面板浮层已挂到 document.body");
      for (const kw of ["服装预设", "姿势参考", "我的", "角色", "应用", "关闭"]) {
        const hits = overlay.byText(kw);
        notes.push(`     ${hits.length ? "✓" : "✗"} 面板内「${kw}」按钮 ${hits.length} 个`);
        if (!hits.length) bad(`面板内找不到「${kw}」按钮`);
      }
      for (const kw of ["服装预设", "姿势参考", "我的", "角色"]) {
        const b = overlay.byText(kw)[0];
        if (!b) continue;
        try {
          b.onclick?.({ target: b, stopPropagation() {} });
          await new Promise((r) => setTimeout(r, 50));
          ok(`点击「${kw}」无异常`);
        } catch (e) {
          bad(`点击「${kw}」抛异常: ${e.message}`);
        }
      }
      // 分类
      for (const kw of ["服装", "游戏/作品", "角色/人数"]) {
        const c = overlay.byText(kw)[0];
        if (!c) { info(`（分类「${kw}」未渲染，跳过）`); continue; }
        try {
          c.onclick?.({ target: c });
          await new Promise((r) => setTimeout(r, 40));
          ok(`点击分类「${kw}」无异常`);
        } catch (e) {
          bad(`点击分类「${kw}」抛异常: ${e.message}`);
        }
      }

      // ---- SFW / NSFW 模式切换 ----
      // 先回到「标签」视图：前面的覆盖视图（角色/我的/服装/姿势）会把侧栏 display:none，
      // 那样分类按钮就点不到了。真实使用中用户也是先回到标签视图再切模式。
      for (let i = 0; i < 4; i++) {
        const back = overlay.byText("返回标签")[0];
        if (!back) break;
        back.onclick?.({ target: back });
        await new Promise((r) => setTimeout(r, 40));
      }
      if (!overlay.byText("性爱姿势")[0]) {
        info("（侧栏仍未显示，重新打开面板做模式测试）");
      }
      const modeBtn = overlay.byText("NSFW（不限）")[0] || overlay.byText("SFW（全年龄）")[0];
      if (!modeBtn) {
        bad("找不到 SFW/NSFW 模式切换按钮");
      } else {
        ok(`找到模式按钮: ${modeBtn.textContent}`);
        const modeWidget = node.widgets.find((w) => w.name === "mode");
        const catsBefore = overlay.visibleButtons().length;
        try {
          modeBtn.onclick?.({ target: modeBtn });
          await new Promise((r) => setTimeout(r, 60));
          if (modeWidget && String(modeWidget.value).includes("SFW")) {
            ok(`切到 SFW：节点 mode 控件同步为「${modeWidget.value}」`);
          } else {
            bad(`切到 SFW 后节点 mode 控件没同步（值=${modeWidget?.value}）`);
          }
          if (String(modeBtn.textContent).includes("SFW")) {
            ok("按钮文案已变成 SFW");
          } else {
            bad(`按钮文案没更新: ${modeBtn.textContent}`);
          }
          // SFW 下「性爱姿势」分类应被收起
          const actBtn = overlay.byText("性爱姿势")[0];
          if (actBtn) bad("SFW 模式下「性爱姿势」分类仍然可见");
          else ok("SFW 模式下「性爱姿势」分类已收起");
          // 切回 NSFW
          modeBtn.onclick?.({ target: modeBtn });
          await new Promise((r) => setTimeout(r, 60));
          if (modeWidget && String(modeWidget.value).includes("NSFW")) {
            ok("切回 NSFW：节点 mode 控件已还原");
          } else {
            bad(`切回 NSFW 失败（值=${modeWidget?.value}）`);
          }
          const actVis = overlay.byText("性爱姿势")[0];
          if (actVis) ok("NSFW 下「性爱姿势」分类恢复显示");
          else bad("NSFW 下「性爱姿势」分类没恢复");
          info(`可见按钮数 ${catsBefore} -> ${overlay.visibleButtons().length}`);
        } catch (e) {
          bad("模式切换抛异常: " + e.message);
        }
      }
      // 拖动/绘制：模拟画布回调，看有没有炸
      try {
        node.onDrawForeground?.(ctxStub);
        ok("onDrawForeground 无异常");
      } catch (e) {
        bad("onDrawForeground 抛异常: " + e.message);
      }
      try {
        node.onDrawBackground?.(ctxStub);
        ok("onDrawBackground 无异常");
      } catch (e) {
        bad("onDrawBackground 抛异常: " + e.message);
      }
    }

      // ---- 种子：固定 / 随机 都能推到下游 KSampler ----
      try {
        const seedSel = overlay.querySelector("select");
        const seedInput = overlay.querySelector('input[type="number"]');
        const dice = overlay.byText("抽一个")[0];
        if (!seedSel || !seedInput) {
          bad("面板里找不到种子控件");
        } else {
          ok(`找到种子控件（模式 ${seedSel.children?.length || "?"} 项，当前 ${seedInput.value}）`);

          // (1) 固定：seed 应该是输入框里的值
          seedInput.value = "777";
          seedInput.onchange?.({ target: seedInput });
          const before1 = samplers.map((s) => s.widgets[0].value);
          // 触发一次提交（点「应用」）
          const applyBtn = overlay.byText("应用")[0];
          applyBtn?.onclick?.({ target: applyBtn });
          await new Promise((r) => setTimeout(r, 80));
          const after1 = samplers.map((s) => s.widgets[0].value);
          if (after1.every((v) => v === 777)) {
            ok(`固定模式：seed 已写入 ${samplers.length} 个采样器`, String(after1));
          } else {
            bad(`固定模式 seed 没写对：${JSON.stringify(before1)} -> ${JSON.stringify(after1)}`);
          }
          const mw = node.widgets.find((w) => w.name === "seed");
          const mmw = node.widgets.find((w) => w.name === "seed_mode");
          if (mw?.value === 777 && String(mmw?.value).includes("固定")) {
            ok("节点上的 seed / seed_mode 控件同步了");
          } else {
            bad(`节点控件没同步：seed=${mw?.value} mode=${mmw?.value}`);
          }
          if (samplers.every((s) => s.widgets[0].options.control_after_generate === "fixed")) {
            ok("固定模式：采样器自动控制设为 fixed");
          } else {
            info("（采样器原本没有 control_after_generate，固定模式不强加）");
          }

          // (2) 随机：每次提交都应该换一个新值（每次都要重新打开面板）
          const openPanel2 = () => {
            const b = node.widgets.find((w) => w.type === "button"
              && String(w.label || "").includes("面板"));
            b?.callback();
          };
          const curOverlay = () => {
            const all = body.children.filter(
              (c) => String(c.className || "").includes("animansfw-overlay"));
            return all[all.length - 1] || null;   // 最新的那个
          };
          openPanel2();
          await new Promise((r) => setTimeout(r, 80));
          let ov = curOverlay();
          if (!ov) { bad("首次打开面板失败（curOverlay 为空）"); }
          const sels = ov ? ov.querySelector("select") : null;
          const inps = ov ? ov.querySelector('input[type="number"]') : null;
          let sel2 = sels;
          if (!sel2) { bad("找不到种子 select"); }
          else {
            sel2.value = "每次随机";
            sel2.onchange?.({ target: sel2 });
          }
          ov = curOverlay();
          ov.byText("应用")[0]?.onclick?.({ target: ov });
          await new Promise((r) => setTimeout(r, 80));

          const got = [samplers[0].widgets[0].value];
          for (let i = 0; i < 2; i++) {
            openPanel2();
            await new Promise((r) => setTimeout(r, 80));
            ov = curOverlay();
            if (!ov) { bad("面板没能重新打开"); break; }
            ov.byText("应用")[0]?.onclick?.({ target: ov });
            await new Promise((r) => setTimeout(r, 80));
            got.push(samplers[0].widgets[0].value);
          }
          const uniq = new Set(got);
          if (uniq.size === got.length && got.every((v) => Number.isFinite(v) && v > 0)) {
            ok("随机模式：每次抽新种子", got.join(", "));
          } else {
            bad(`随机模式种子重复或无效: ${JSON.stringify(got)}`);
          }
          const anyRandom = samplers.some(
            (s) => s.widgets[0].options.control_after_generate === "randomize");
          if (anyRandom) ok("随机模式：采样器自动控制设为 randomize");
          else bad("随机模式没设置 control_after_generate");
        }
      } catch (e) {
        bad("种子检查抛异常: " + e.message + " | " + String(e.stack || "").split("\n")[1]);
      }

      // ---- 老前端契约：DOM widget 没有 options 也不能崩 ----
      if (OLD_FE) {
        const dw = node.widgets.find((w) => w.type === "div");
        if (dw && !("options" in dw)) {
          ok("老前端契约：DOM widget 无 options，面板未崩");
        } else if (dw) {
          info("（本模式 DOM widget 仍带 options，契约模拟不完全）");
        } else {
          bad("老前端契约：找不到 DOM widget");
        }
      }

      // ---- 📖 剧情模式：每次都用刚打开的面板 ----
      try {
        let ov = await openFresh();
        const storyBtn = ov?.byText("剧情")[0];
        if (!storyBtn) {
          bad("找不到「📖 剧情」按钮");
        } else {
          storyBtn.onclick?.({ target: storyBtn });
          await new Promise((r) => setTimeout(r, 300));
          ov = keepLatest();

          const arcs = FIXTURES.story?.arcs || [];
          ok(`剧情视图打开，${arcs.length} 条故事线`,
            arcs.map((a) => a.title).join("/"));

          const useBtns = ov.byText("套用这一拍");
          if (useBtns.length === 6) ok("渲染出 6 拍分镜卡片");
          else bad(`分镜卡片数量不对: ${useBtns.length}`);

          const firstArc = arcs[0];
          if (firstArc && anyWithText(ov, firstArc.scenes[0].dialogue).length) {
            ok("分镜卡片显示中文台词", firstArc.scenes[0].dialogue.slice(0, 22));
          } else {
            bad("分镜卡片没显示中文台词");
          }

          const castKeys = firstArc?.cast || [];
          const castShown = castKeys.filter(
            (k) => ov.byText(FIXTURES.story.cast[k].zh).length).length;
          if (castShown === castKeys.length) ok(`主角候选都渲染了（${castShown} 个）`);
          else bad(`主角候选渲染不全 ${castShown}/${castKeys.length}`);

          // 套用第 2 拍（用同一个 ov 上的按钮）
          const before = readTagsOf(node);
          ov.byText("套用这一拍")[1]?.onclick?.({ target: ov });
          await new Promise((r) => setTimeout(r, 260));
          const after = readTagsOf(node);
          if (after && after !== before) ok("套用后 tags 已写入节点", after.slice(0, 56) + "…");
          else bad("套用后 tags 没变化");
          if (after.includes("char_lock:")) ok("套用结果带 char_lock（主角跨图锁定）");
          else bad("没有 char_lock: " + after.slice(0, 70));

          // 台词**不应该**写进 caption_text（会被模型当字幕画到图上）
          const cw = node.widgets.find((w) => w.name === "caption_text");
          if (cw && String(cw.value) === "") {
            ok("台词未写入 caption_text（避免被画成字幕）");
          } else {
            bad(`caption_text 应为空，实际: ${JSON.stringify(String(cw?.value).slice(0, 40))}`);
          }
          const pw2 = node.widgets.find((w) => w.name === "outfit_preset");
          if (pw2 && String(pw2.value).includes("[L]")) {
            ok("主角服装以「锁定角色」预设写入", String(pw2.value).slice(0, 40));
          } else {
            bad("outfit_preset 没写成锁定预设: " + pw2?.value);
          }
          const smw2 = node.widgets.find((w) => w.name === "seed_mode");
          if (String(smw2?.value).includes("递增")) ok("套用后种子自动切到「递增 +1」");
          else bad(`种子模式没切到递增: ${smw2?.value}`);

          // 换主角后标签里应该是另一个角色
          ov = await openFresh();
          ov.byText("剧情")[0]?.onclick?.({ target: ov });
          await new Promise((r) => setTimeout(r, 300));
          ov = keepLatest();
          const otherKey = castKeys[1];
          const otherCast = otherKey ? FIXTURES.story.cast[otherKey] : null;
          if (otherCast) {
            const cbtn = ov.byText(otherCast.zh)[0];
            cbtn?.onclick?.({ target: cbtn });
            await new Promise((r) => setTimeout(r, 200));
            ov = keepLatest();
            ov.byText("套用这一拍")[0]?.onclick?.({ target: ov });
            await new Promise((r) => setTimeout(r, 260));
            const after2 = readTagsOf(node);
            if (after2.includes(otherCast.name)) {
              ok(`换主角生效：主角换成 ${otherCast.zh}（${otherCast.name}）`);
            } else {
              bad(`换主角没生效，tags 里没有 ${otherCast.name}`);
            }
          }
        }
      } catch (e) {
        bad("剧情检查抛异常: " + e.message + " | " + String(e.stack || "").split("\n")[1]);
      }

      // ---- 角色立绘：URL 拼接 + 卡片真的带 <img> ----
      try {
        const urls = [];
        const grabImgs = (n, out = []) => {
          for (const c of n.children) {
            if (c.__tag === "img") out.push(c);
            grabImgs(c, out);
          }
          return out;
        };
        // 打开「角色」视图（前面模式测试已回到标签视图）
        const charBtn2 = overlay.byText("角色")[0];
        if (charBtn2) {
          charBtn2.onclick?.({ target: charBtn2 });
          await new Promise((r) => setTimeout(r, 120));
          const imgs = grabImgs(overlay);
          if (imgs.length) {
            ok(`角色卡片带立绘 <img> ${imgs.length} 张`);
            const u = String(imgs[0].src || "");
            // ⚠️ v1.11.0 起缩略图走**本地缓存代理**（为了不挂 VPN 也能看）：
            //    src = anima_nsfw/thumb?u=<编码后的原始 URL>
            //    所以断言要拆成"确实经过代理" + "原始地址仍是 animadex 立绘"。
            const viaProxy = u.includes("anima_nsfw/thumb?u=");
            let raw = u;
            try {
              const q = u.slice(u.indexOf("u=") + 2);
              raw = decodeURIComponent(q);
            } catch (e) { /* ignore */ }
            const okRaw = raw.startsWith("https://blobs.animadex.net/Outputs/thumbs/")
              && raw.endsWith(".webp");
            if (viaProxy && okRaw) {
              ok("立绘 URL 经本地代理且原始地址正确", raw.slice(0, 58));
            } else if (!viaProxy && okRaw) {
              // 代理不可用时前端会退回直连，也算对
              ok("立绘 URL 直连（代理不可用时的兜底）", raw.slice(0, 58));
            } else {
              bad("立绘 URL 格式不对: " + u.slice(0, 90));
            }
            if (u.includes("%2C%20") || u.includes(", ")) {
              ok("立绘 URL 用了 `角色名, 作品名`");
            } else {
              info("（该角色没有作品字段，URL 里只有名字）");
            }
          } else {
            bad("角色卡片里没有 <img>（立绘没渲染出来）");
          }
          // 分页哨兵
          const sentinel = overlay.byText("往下滚自动加载更多")[0]
            || overlay.byText("已显示")[0];
          if (sentinel) ok("有分页哨兵（懒加载更多）");
          else info("（当前结果不足一批，没有分页哨兵）");
        } else {
          info("（找不到「角色」按钮，跳过立绘检查）");
        }
      } catch (e) {
        bad("立绘检查抛异常: " + e.message);
      }


  } catch (e) {
    bad("点击「打开面板」抛异常: " + e.message + " | " + String(e.stack || "").split("\n")[1]);
  }
}

// 2. 负面构建器
try {
  const nt2 = { prototype: {} };
  await ext.beforeRegisterNodeDef(nt2, { name: "AnimaNsfwNegativeBuilder" });
  const n2 = makeNode("AnimaNsfwNegativeBuilder", {
    base_enabled: true, 手部修复: true, 面部修复: true, 人体结构: false,
    NSFW安全: false, 画面干净: false, 防伪影: false, extra_text: "",
  });
  nt2.prototype.onNodeCreated?.call(n2);
  ok("负面构建器 onNodeCreated 执行成功");
} catch (e) {
  bad("负面构建器抛异常: " + e.message);
}

console.warn = origWarn;
console.log("\n=== 结果 ===");
console.log(notes.join("\n"));
cleanup();
if (problems.length) {
  console.log("\n!!! 发现问题:");
  console.log(problems.join("\n"));
  process.exit(1);
}
console.log(`\n全部通过（fetch ${fetchCount} 次，全部走桩；未启动 ComfyUI）`);
