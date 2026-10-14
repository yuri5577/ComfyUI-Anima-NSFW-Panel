/**
 * 真浏览器：左侧栏在窄视口下是否完整。
 *   node tools/animansfw_browser_sidebar.mjs [http://127.0.0.1:8188]
 *
 * ## 这个 bug 的真实根因（值得记住）
 *
 * 用户反馈「左边的选项显示不完整」。查了很久才定位到：**不是侧栏太窄**，
 * 而是面板子树里有元素横向溢出：
 *
 *   panel.clientWidth = 1178，但 panel.scrollWidth = 1373（溢出 195px）
 *   唯一溢出的元素是 **header** —— `flexWrap` 默认 `nowrap`，
 *   10 个按钮 + 搜索框排一行需要 1373px，不肯折行。
 *
 * 溢出把面板内容整体**居中推左 91px**，面板又是 `overflow: hidden`，
 * 于是左边 91px 被直接裁掉 —— 侧栏的「全部标签」「露骨 / 强度」就是这么被切的。
 * 关键特征：**偏移量与视口宽度无关，恒定 91px**（这也是最终定位它的线索：
 * offsetLeft 说元素在面板内，getBoundingClientRect 说在外面，差一个定值）。
 *
 * 修法：header 加 flexWrap + minWidth:0；窄面板时侧栏改为顶部横向条。
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:8188";
const CHROME = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((p) => fs.existsSync(p));
if (!CHROME) { console.error("找不到 Chrome"); process.exit(2); }

const PORT = 9356;
const PROFILE = path.join(os.tmpdir(), `animansfw_sbw_${process.pid}`);
fs.rmSync(PROFILE, { recursive: true, force: true });
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, "--no-first-run", "--disable-gpu",
  "--window-size=1600,1000", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws = null, msgId = 0;
const pending = new Map();
const results = [];
const ok = (l, e = "") => results.push(["OK  ", l, e]);
const bad = (l, e = "") => results.push(["ERR ", l, e]);
function send(m, p = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method: m, params: p }));
  return new Promise((res, rej) => {
    pending.set(id, { resolve: res, reject: rej });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error("超时 " + m)); } }, 120000);
  });
}
async function ev(expr) {
  const r = await send("Runtime.evaluate", {
    expression: `(async () => JSON.stringify(await (async () => { ${expr} })()))()`,
    awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) return { __error: r.exceptionDetails.text };
  try { return JSON.parse(r.result?.value ?? "null"); } catch (e) { return r.result?.value ?? null; }
}
const OV = `const ov=[...document.body.children].find(c=>String(c.className||"").includes("animansfw-overlay"));`;

// 一次 evaluate 内测完所有几何（跨次查询会拿到残留元素，之前踩过）
const PROBE = `
  ${OV}
  const panel = ov.firstElementChild;
  const pr = panel.getBoundingClientRect();
  const marker = [...panel.querySelectorAll("div")].find(function(d){
    return String(d.textContent||"").indexOf("强度档位（自动全选一套）") >= 0 && d.children.length === 0;
  });
  const side = marker ? marker.parentElement : null;
  const row = side ? side.parentElement : null;
  const grid = [...panel.querySelectorAll("div")].find(function(d){
    return d.style.padding === "10px 12px"; });
  const sr = side ? side.getBoundingClientRect() : null;
  const gr = grid ? grid.getBoundingClientRect() : null;
  const out = {
    win: innerWidth,
    panel: { l: Math.round(pr.left), r: Math.round(pr.right), w: Math.round(pr.width),
             scrollW: panel.scrollWidth, clientW: panel.clientWidth,
             overflowX: panel.scrollWidth - panel.clientWidth },
    side: sr ? { l: Math.round(sr.left), r: Math.round(sr.right), w: Math.round(sr.width),
                 top: Math.round(sr.top), bot: Math.round(sr.bottom) } : null,
    grid: gr ? { l: Math.round(gr.left), w: Math.round(gr.width), top: Math.round(gr.top) } : null,
    rowDir: row ? getComputedStyle(row).flexDirection : null,
    truncated: [],
    outOfPanel: [],
  };
  // 分类名有没有被省略号裁掉
  for (const b of panel.querySelectorAll("button")) {
    if (!b.__catId) continue;
    const s = b.querySelector("span");
    if (s && s.scrollWidth > s.clientWidth + 1) {
      out.truncated.push({ id: b.__catId, text: String(s.textContent||"") });
    }
  }
  out.truncated = out.truncated.slice(0, 8);
  // 有没有控件超出面板左右边界（= 会被裁掉）
  for (const el of panel.querySelectorAll("button,span,input,textarea")) {
    const r2 = el.getBoundingClientRect();
    if (r2.width === 0) continue;
    if (r2.left < pr.left - 1 || r2.right > pr.right + 1) {
      out.outOfPanel.push({ tag: el.tagName,
        text: String(el.textContent||"").replace(/\s+/g," ").trim().slice(0, 16),
        l: Math.round(r2.left), r: Math.round(r2.right) });
    }
  }
  out.outOfPanel = out.outOfPanel.slice(0, 6);
  return out;
`;

async function main() {
  let ver = null;
  for (let i = 0; i < 100; i++) {
    try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); break; }
    catch (e) { await sleep(300); }
  }
  if (!ver) throw new Error("DevTools 没起来");
  const tg = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
  ws = new WebSocket(tg.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id); pending.delete(m.id);
      m.error ? reject(new Error(m.error.message)) : resolve(m.result);
    }
  };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: BASE });
  for (let i = 0; i < 140; i++) {
    await sleep(500);
    const r = await send("Runtime.evaluate", { expression: "!!(window.app&&window.app.graph)", returnByValue: true });
    if (r.result?.value) break;
  }
  await ev(`const lg=window.LiteGraph||window.LiteGraphJS; const n=lg.createNode("AnimaNsfwPromptBuilder");
    window.app.graph.add(n); window.__n=n;
    n.widgets.find(function(w){return w.type==="button" && String(w.label||w.name||"").indexOf("面板")>=0;}).callback(); return 1;`);
  for (let i = 0; i < 140; i++) {
    await sleep(300);
    const r = await ev(`${OV} return !!(ov && ov.querySelectorAll("button").length > 15);`);
    if (r) break;
  }
  await sleep(1800);
  ok("面板已打开");

  console.log("\n=== 各视口宽度 ===");
  const seen = {};
  for (const w of [1600, 1280, 1100, 960, 820, 700, 600, 480, 420, 320]) {
    await send("Emulation.setDeviceMetricsOverride", {
      width: w, height: 950, deviceScaleFactor: 1, mobile: false });
    await sleep(600);
    const r = await ev(PROBE);
    seen[w] = r;
    const dir = r?.rowDir === "column" ? "上下" : "左右";
    console.log(`  ${String(w).padStart(4)}px  面板 ${String(r?.panel?.w).padStart(4)}px  ` +
      `溢出 ${String(r?.panel?.overflowX).padStart(3)}px  布局 ${dir}  ` +
      `侧栏 ${String(r?.side?.w).padStart(3)}px  ` +
      `越界 ${r?.outOfPanel?.length ?? "?"}  裁字 ${r?.truncated?.length ?? "?"}`);
    if (r?.outOfPanel?.length) {
      for (const o of r.outOfPanel.slice(0, 3)) {
        console.log(`        越界: ${o.tag} "${o.text}" ${o.l}~${o.r}（面板 ${r.panel.l}~${r.panel.r}）`);
      }
    }
  }

  // ---- 全局断言：所有宽度下面板都不能有横向溢出 ----
  const overflow = Object.entries(seen).filter(([, r]) => (r?.panel?.overflowX ?? 0) > 1);
  overflow.length === 0
    ? ok("所有宽度下面板子树无横向溢出",
        `最大溢出 ${Math.max(...Object.values(seen).map((r) => r?.panel?.overflowX ?? 0))}px`)
    : bad("所有宽度下面板子树无横向溢出",
        overflow.map(([w, r]) => `${w}px:${r.panel.overflowX}px`).join(" "));

  const oor = Object.entries(seen).filter(([, r]) => (r?.outOfPanel?.length ?? 0) > 0);
  oor.length === 0
    ? ok("所有宽度下没有控件超出面板边界")
    : bad("所有宽度下没有控件超出面板边界",
        oor.map(([w, r]) => `${w}px:${r.outOfPanel.length}个(${r.outOfPanel[0].text})`).join(" "));

  const trunc = Object.entries(seen).filter(([, r]) => (r?.truncated?.length ?? 0) > 0);
  trunc.length === 0
    ? ok("所有宽度下分类名都没被裁")
    : bad("所有宽度下分类名都没被裁",
        trunc.map(([w, r]) => `${w}px:${r.truncated.map((t) => t.text).join("/")}`).join(" "));

  // ---- 侧栏左边界必须落在面板内（这就是"显示不完整"的几何判据）----
  const pushed = Object.entries(seen).filter(([, r]) =>
    r?.side && r?.panel && (r.panel.l - r.side.l) > 2);
  pushed.length === 0
    ? ok("所有宽度下侧栏都在面板内（没被推出去）",
        Object.entries(seen).map(([w, r]) => `${w}:${r.panel.l - r.side.l}`).join(" "))
    : bad("所有宽度下侧栏都在面板内（没被推出去）",
        pushed.map(([w, r]) => `${w}px 偏移 ${r.panel.l - r.side.l}px`).join(" "));

  // ---- 窄面板：侧栏在网格上方，两者都占满面板宽度 ----
  const n420 = seen[420];
  n420?.rowDir === "column"
    ? ok("窄面板（420px）侧栏改为上下布局", `flexDirection=${n420.rowDir}`)
    : bad("窄面板（420px）侧栏改为上下布局", `flexDirection=${n420?.rowDir}`);
  n420?.side && n420?.grid && n420.side.top < n420.grid.top
    ? ok("窄面板下侧栏在网格上方", `侧栏 top=${n420.side.top} < 网格 top=${n420.grid.top}`)
    : bad("窄面板下侧栏在网格上方",
        `侧栏 top=${n420?.side?.top} 网格 top=${n420?.grid?.top}`);
  n420?.grid?.w >= 260
    ? ok("窄面板下网格有可读宽度", `${n420.grid.w}px（面板 ${n420.panel.w}px）`)
    : bad("窄面板下网格有可读宽度", `只有 ${n420?.grid?.w}px`);

  // ---- 宽面板：侧栏回到左侧竖列（观感不变）----
  const n1600 = seen[1600];
  n1600?.rowDir === "row"
    ? ok("宽面板（1600px）侧栏回到左侧竖列", `flexDirection=${n1600.rowDir}`)
    : bad("宽面板（1600px）侧栏回到左侧竖列", `flexDirection=${n1600?.rowDir}`);
  n1600?.side?.w === 186 && n1600?.grid?.l > n1600?.side?.l
    ? ok("宽面板下侧栏 186px 在网格左侧",
        `侧栏 ${n1600.side.w}px @${n1600.side.l}，网格 @${n1600.grid.l}`)
    : bad("宽面板下侧栏 186px 在网格左侧", JSON.stringify(n1600?.side));
  n1600?.panel?.w === 1180
    ? ok("宽面板仍是 1180px")
    : bad("宽面板仍是 1180px", `实际 ${n1600?.panel?.w}px`);

  await send("Emulation.setDeviceMetricsOverride", {
    width: 420, height: 950, deviceScaleFactor: 1, mobile: false });
  await sleep(600);
  const shot = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(process.cwd(), "animansfw_sidebar_420.png"),
    Buffer.from(shot.data, "base64"));
  ok("截图 420px", "animansfw_sidebar_420.png");
  await send("Emulation.clearDeviceMetricsOverride");

  console.log("\n=== 窄视口左侧栏（真浏览器）===");
  for (const [t, l, e] of results) console.log(`  ${t} ${l}${e ? "  " + e : ""}`);
  const n = results.filter((r) => r[0] === "ERR ").length;
  console.log(`\n${n === 0 ? "全部通过" : n + " 项失败"}`);
}

const cleanup = () => {
  try { ws?.close(); } catch (e) { /* ignore */ }
  try { proc.kill(); } catch (e) { /* ignore */ }
  try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch (e) { /* ignore */ }
};
try {
  await main(); cleanup();
  process.exit(results.some((r) => r[0] === "ERR ") ? 1 : 0);
} catch (e) {
  console.error("崩了:", e.message);
  cleanup(); process.exit(2);
}
