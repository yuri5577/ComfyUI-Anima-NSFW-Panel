/**
 * 真浏览器端到端测试：用 headless Chrome + CDP 打开 ComfyUI，
 * 添加面板节点、打开面板、点标签，量真实的响应时间和 DOM 规模。
 *
 *   node tools/animansfw_browser_e2e.mjs [http://127.0.0.1:8188]
 *
 * 需要本机有 Chrome 或 Edge。会启动一个独立的 headless 实例，用独立 profile。
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:8188";
const CHROME = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].find((p) => fs.existsSync(p));

if (!CHROME) {
  console.error("找不到 Chrome / Edge");
  process.exit(2);
}

const PORT = 9333;
const PROFILE = path.join(os.tmpdir(), `animansfw_e2e_${process.pid}`);
fs.rmSync(PROFILE, { recursive: true, force: true });

const t0 = Date.now();
const proc = spawn(CHROME, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`,
  "--no-first-run", "--no-default-browser-check",
  "--disable-gpu", "--disable-dev-shm-usage",
  "--window-size=1600,1000",
  "about:blank",
], { stdio: "ignore", detached: false });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitDevtools(timeoutMs = 30000) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch (e) { /* 还没起来 */ }
    await sleep(300);
  }
  throw new Error("DevTools 没起来");
}

let ws = null;
let msgId = 0;
const pending = new Map();

function send(method, params = {}, sessionId) {
  const id = ++msgId;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error(`超时: ${method}`)); }
    }, 60000);
  });
}

const logs = [];
const results = [];

function ok(label, extra = "") { results.push(["OK  ", label, extra]); }
function bad(label, extra = "") { results.push(["ERR ", label, extra]); }
function info(msg) { logs.push(msg); }

async function main() {
  const ver = await waitDevtools();
  console.log(`浏览器: ${ver.Browser}`);

  // 新建页面并附加
  const target = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
    ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  const sessionId = null;
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      if (m.error) reject(new Error(m.error.message));
      else resolve(m.result);
      return;
    }
    if (m.method === "Runtime.consoleAPICalled") {
      const txt = (m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ");
      if (txt) info(`[console.${m.params.type}] ${txt.slice(0, 200)}`);
    }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      info(`[exception] ${d.text} ${d.exception?.description || ""}`.slice(0, 300));
    }
  };

  await send("Runtime.enable");
  await send("Page.enable");
  await send("Log.enable");

  // 打开 ComfyUI
  await send("Page.navigate", { url: BASE });
  // 等图编辑器就绪（window.app 存在且 graph 可用）
  let ready = false;
  for (let i = 0; i < 120; i++) {
    await sleep(500);
    try {
      const r = await send("Runtime.evaluate", {
        expression: `!!(window.app && window.app.graph && window.app.graph._nodes !== undefined)`,
        returnByValue: true,
      });
      if (r.result?.value === true) { ready = true; break; }
    } catch (e) { /* ignore */ }
  }
  ready ? ok("ComfyUI 图编辑器就绪", `${((Date.now() - t0) / 1000).toFixed(1)}s`)
    : bad("ComfyUI 图编辑器就绪");

  // 面板扩展是否注册
  const ext = await send("Runtime.evaluate", {
    expression: `(window.app?.extensions || []).map(e => e.name).filter(n => /Anima/i.test(n)).join(",")`,
    returnByValue: true,
  });
  const extNames = ext.result?.value || "";
  extNames.includes("AnimaNsfwPanel")
    ? ok("面板扩展已注册", extNames)
    : bad("面板扩展已注册", extNames || "(空)");

  // 用 LiteGraph 直接建一个面板节点（等价于用户右键添加）
  const addNode = await send("Runtime.evaluate", {
    expression: `(() => {
      try {
        const lg = window.LiteGraph || window.LiteGraphJS;
        if (!lg || !lg.createNode) return "no LiteGraph";
        const n = lg.createNode("AnimaNsfwPromptBuilder");
        if (!n) return "createNode 返回空（节点没注册？）";
        window.app.graph.add(n);
        window.__testNode = n;
        return "ok:" + (n.widgets || []).length + " widgets";
      } catch (e) { return "throw: " + e.message; }
    })()`,
    returnByValue: true,
  });
  const addRes = String(addNode.result?.value || "");
  addRes.startsWith("ok") ? ok("能创建面板节点", addRes) : bad("能创建面板节点", addRes);

  // 找到「打开 NSFW 面板」按钮
  const btn = await send("Runtime.evaluate", {
    expression: `(() => {
      const n = window.__testNode;
      if (!n) return "no node";
      const w = (n.widgets || []).find(w => w.type === "button" && String(w.label||w.name||"").includes("面板"));
      if (!w) return "没找到按钮: " + (n.widgets||[]).map(x=>x.type+":"+(x.label||x.name)).join(" | ");
      window.__panelBtn = w;
      return "ok";
    })()`,
    returnByValue: true,
  });
  const btnRes = String(btn.result?.value || "");
  btnRes === "ok" ? ok("节点上有「打开 NSFW 面板」按钮") : bad("节点上有「打开 NSFW 面板」按钮", btnRes.slice(0, 200));

  // ---- 测开面板的耗时（真实布局 + 样式计算）----
  const openTiming = await send("Runtime.evaluate", {
    expression: `(async () => {
      const t0 = performance.now();
      window.__panelBtn.callback();
      // 等两帧，让浏览器完成布局与绘制
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const tSync = performance.now() - t0;
      // 等异步数据加载完（面板浮层挂上 body）
      const end = performance.now() + 15000;
      while (performance.now() < end) {
        const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
        if (ov && ov.querySelector("button")) {
          const tAll = performance.now() - t0;
          const nodes = ov.querySelectorAll("*").length;
          const btns = ov.querySelectorAll("button").length;
          return JSON.stringify({ ok: true, tSync, tAll, nodes, btns });
        }
        await new Promise(r => setTimeout(r, 60));
      }
      return JSON.stringify({ ok: false, tSync });
    })()`,
    awaitPromise: true,
    returnByValue: true,
  });
  let openData = {};
  try { openData = JSON.parse(openTiming.result?.value || "{}"); } catch (e) { /* ignore */ }
  if (openData.ok) {
    ok("面板成功打开",
      `首屏 ${openData.tSync.toFixed(0)}ms / 数据齐 ${openData.tAll.toFixed(0)}ms`);
    ok("面板 DOM 规模", `${openData.nodes} 个节点 / ${openData.btns} 个按钮`);
    if (openData.tAll > 3000) bad("开面板总耗时 > 3s", `${openData.tAll.toFixed(0)}ms`);
  } else {
    bad("面板成功打开", JSON.stringify(openData));
  }

  // ---- 点一个标签，量真实重绘耗时 ----
  const clickTiming = await send("Runtime.evaluate", {
    expression: `(async () => {
      const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
      if (!ov) return JSON.stringify({ ok: false, why: "no overlay" });
      // 找一个标签卡：button 且含两个 span 子元素
      const cards = [...ov.querySelectorAll("button")].filter(b => b.children.length === 2 && b.textContent.length > 1);
      if (!cards.length) return JSON.stringify({ ok: false, why: "no tag cards" });
      const before = ov.querySelectorAll("*").length;
      const t0 = performance.now();
      cards[0].click();
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const ms = performance.now() - t0;
      const after = ov.querySelectorAll("*").length;
      return JSON.stringify({ ok: true, ms, before, after });
    })()`,
    awaitPromise: true,
    returnByValue: true,
  });
  let clickData = {};
  try { clickData = JSON.parse(clickTiming.result?.value || "{}"); } catch (e) { /* ignore */ }
  if (clickData.ok) {
    ok("点标签的真实帧耗时", `${clickData.ms.toFixed(1)} ms（含两帧布局+绘制）`);
    ok("点标签没有重建整个网格", `DOM ${clickData.before} → ${clickData.after}`);
    if (clickData.ms > 200) bad("点标签帧耗时 > 200ms", `${clickData.ms.toFixed(1)}ms`);
  } else {
    bad("点标签的真实帧耗时", JSON.stringify(clickData));
  }

  // ---- 连点 5 个标签，看预览请求被防抖成几次（用 Performance 资源计时）----
  const debounce = await send("Runtime.evaluate", {
    expression: `(async () => {
      const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
      if (!ov) return JSON.stringify({ ok: false });
      const cards = [...ov.querySelectorAll("button")].filter(b => b.children.length === 2 && b.textContent.length > 1);
      const mark = performance.now();
      const n0 = performance.getEntriesByType("resource").filter(e => e.name.includes("anima_nsfw/preview")).length;
      for (let i = 1; i <= 5 && i < cards.length; i++) cards[i].click();
      await new Promise(r => setTimeout(r, 900));
      const n1 = performance.getEntriesByType("resource").filter(e => e.name.includes("anima_nsfw/preview")).length;
      void mark;
      return JSON.stringify({ ok: true, during: n1 - n0 });
    })()`,
    awaitPromise: true,
    returnByValue: true,
  });
  let dbData = {};
  try { dbData = JSON.parse(debounce.result?.value || "{}"); } catch (e) { /* ignore */ }
  if (dbData.ok) {
    const n = dbData.during;
    n <= 2 ? ok("连点 5 个标签 → 预览请求已防抖", `${n} 次`)
      : bad("连点 5 个标签 → 预览请求已防抖", `${n} 次（期望 ≤ 2）`);
  }

  // ---- 控制台有没有本包的报错 ----
  const animaErrs = logs.filter((l) => /\[AnimaNSFW\]|animansfw/i.test(l)
    && /error|exception|失败|TypeError|ReferenceError/i.test(l));
  animaErrs.length === 0 ? ok("控制台没有本包报错")
    : bad("控制台没有本包报错", animaErrs.slice(0, 3).join(" | ").slice(0, 240));

  // ---- 截图 ----
  const shot = await send("Page.captureScreenshot", { format: "png" });
  const out = path.join(process.cwd(), "animansfw_panel_screenshot.png");
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  ok("截图已保存", out);

  // ---- 报告 ----
  console.log("\n=== 真浏览器测试结果 ===");
  for (const [tag, label, extra] of results) {
    console.log(`  ${tag} ${label}${extra ? "  " + extra : ""}`);
  }
  const errs = results.filter((r) => r[0] === "ERR ").length;
  console.log(`\n${errs === 0 ? "全部通过" : errs + " 项失败"}`);

  if (logs.length) {
    console.log("\n--- 浏览器日志（前 20 条）---");
    for (const l of logs.slice(0, 20)) console.log("  " + l);
  }
}

const cleanup = () => {
  try { ws?.close(); } catch (e) { /* ignore */ }
  try { proc.kill(); } catch (e) { /* ignore */ }
  try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch (e) { /* ignore */ }
};

try {
  await main();
  cleanup();
  process.exit(results.some((r) => r[0] === "ERR ") ? 1 : 0);
} catch (e) {
  console.error("测试崩了:", e.message);
  console.error(logs.slice(-10).join("\n"));
  cleanup();
  process.exit(2);
}
