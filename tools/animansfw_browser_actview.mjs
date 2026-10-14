/**
 * 真浏览器：动作/视角快速选择条。
 *   node tools/animansfw_browser_actview.mjs
 *
 * 覆盖：
 *   1. 快速条存在，三行（动作 / 腿·手 / 视角）都在
 *   2. 点「坐着」→ 标签进节点
 *   3. 再点「站立」→ 组内互斥，只留站立
 *   4. 点「翘腿」（不同组）→ 和主姿态叠加，两个都在
 *   5. 点「侧面」「特写」（不同组）→ 都能叠加
 *   6. chip 的亮/暗和实际选中一致
 *   7. 覆盖视图（服装/角色）里快速条要隐藏
 *   8. 侧栏有「动作/姿势」「镜头/视角」两个新分类
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
].find((p) => fs.existsSync(p));
if (!CHROME) { console.error("找不到 Chrome"); process.exit(2); }

const PORT = 9346;
const PROFILE = path.join(os.tmpdir(), `animansfw_av_${process.pid}`);
fs.rmSync(PROFILE, { recursive: true, force: true });
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, "--no-first-run", "--disable-gpu",
  "--window-size=1600,1000", "about:blank"], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws = null, msgId = 0;
const pending = new Map();
const logs = [], results = [];
const ok = (l, e = "") => results.push(["OK  ", l, e]);
const bad = (l, e = "") => results.push(["ERR ", l, e]);

function send(m, p = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method: m, params: p }));
  return new Promise((res, rej) => {
    pending.set(id, { resolve: res, reject: rej });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error("超时 " + m)); } }, 90000);
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
// 快速条：那个 `padding: 6px 10px` 的行。
// ⚠️ 不能只靠「文字里含 腿/手 + 按钮够多」—— querySelectorAll 返回文档顺序，
//    overlay 的祖先节点文字里也含「腿/手」，会抓到最外层（305 个按钮）而不是
//    真正那一行（43 个 chip），于是"隐藏了吗"永远测成 flex。
const QROW = `[...ov.querySelectorAll("div")].find(function(d){
  return d.style.padding === "6px 10px" && String(d.textContent||"").indexOf("腿/手") >= 0;
})`;
const TAGS = `(window.__n.widgets.find(w=>w.name==="tags")||{}).value || ""`;

async function readTags() { return await ev(`${OV} return { tags: ${TAGS} };`).then((r) => r?.tags || ""); }

async function clickChip(zh) {
  return await ev(`
    ${OV}
    const row=${QROW};
    if(!row) return { ok:false, why:"找不到快速条" };
    const b=[...row.querySelectorAll("button")].find(x=>String(x.textContent||"").trim()===${JSON.stringify(zh)});
    if(!b) return { ok:false, why:"找不到 chip " + ${JSON.stringify(zh)} };
    b.click(); await new Promise(r=>setTimeout(r,420));
    return { ok:true };
  `);
}

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
      return;
    }
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      logs.push((m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 200));
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
    n.widgets.find(w=>w.type==="button"&&String(w.label||w.name||"").includes("面板")).callback(); return 1;`);
  for (let i = 0; i < 140; i++) {
    await sleep(300);
    const r = await ev(`${OV} return !!(ov && ov.querySelectorAll("button").length > 15);`);
    if (r) break;
  }
  await sleep(2000);
  ok("面板已打开");

  // ---- 1. 快速条结构 ----
  const shape = await ev(`
    ${OV}
    const row=${QROW};
    if(!row) return { ok:false };
    const btns=[...row.querySelectorAll("button")].map(b=>String(b.textContent||"").trim());
    return { ok:true, n:btns.length, hasAction:btns.includes("站立")&&btns.includes("坐着"),
             hasView:btns.includes("正面")&&btns.includes("侧面")&&btns.includes("全身"),
             hasLimb:btns.includes("翘腿"),
             disp:getComputedStyle(row).display,
             sample:btns.slice(0,14),
             // 43 = 15 动作 + 10 腿手 + 18 视角（不含「更多…」按钮）
             chips: btns.filter(x=>x!=="更多…").length };
  `);
  shape?.ok && shape.hasAction && shape.hasView && shape.hasLimb
    ? ok("动作/视角快速条存在", `${shape.n} 个 chip（动作/腿手/视角三行）`)
    : bad("动作/视角快速条存在", JSON.stringify(shape).slice(0, 220));
  shape?.disp === "flex" ? ok("标签视图里显示") : bad("标签视图里显示", `display=${shape?.disp}`);

  // ---- 2. 点「坐着」 ----
  await clickChip("坐着");
  let t = await readTags();
  /sitting/.test(t) ? ok("点「坐着」写入节点", t.slice(0, 80)) : bad("点「坐着」写入节点", t.slice(0, 80));

  // ---- 3. 点「站立」→ 互斥 ----
  await clickChip("站立");
  t = await readTags();
  /standing/.test(t) && !/(^|[,\s])sitting([,\s]|$)/.test(t)
    ? ok("组内互斥：站立顶掉坐着", t.slice(0, 80))
    : bad("组内互斥：站立顶掉坐着", t.slice(0, 90));

  // ---- 4. 点「翘腿」→ 叠加 ----
  await clickChip("翘腿");
  t = await readTags();
  /standing/.test(t) && /crossed legs/.test(t)
    ? ok("不同组可叠加：站立 + 翘腿", t.slice(0, 90))
    : bad("不同组可叠加：站立 + 翘腿", t.slice(0, 90));

  // ---- 5. 视角叠加：侧面 + 特写 ----
  await clickChip("侧面");
  await clickChip("特写");
  t = await readTags();
  /from side/.test(t) && /close-up/.test(t)
    ? ok("视角可叠加：侧面 + 特写", t.slice(0, 110))
    : bad("视角可叠加：侧面 + 特写", t.slice(0, 110));

  // ---- 5b. 视角互斥：点「俯视」应顶掉「侧面」 ----
  await clickChip("俯视");
  t = await readTags();
  /from above/.test(t) && !/from side/.test(t) && /close-up/.test(t)
    ? ok("视角组内互斥：俯视顶掉侧面，特写保留", t.slice(0, 110))
    : bad("视角组内互斥", t.slice(0, 120));

  // ---- 6. chip 选中态和实际一致 ----
  // 选中态用 **border 颜色** 判：选中时是彩色（#4ade80 / #5eead4 之类），
  // 未选中是 THEME.line（#33334a → rgb(51, 51, 74)）。
  // 别用 background 反推 —— 未选中的 panel2 也是有色值，容易判反。
  const paint = await ev(`
    ${OV}
    const row=${QROW};
    if (!row) return { __noRow: true };
    const want={"站立":true,"坐着":false,"俯视":true,"侧面":false,"特写":true,"翘腿":true,"全身":false};
    const out={};
    for (const b of row.querySelectorAll("button")) {
      const zh=String(b.textContent||"").trim();
      if (!(zh in want)) continue;
      const bd=String(b.style.border||"") || String(b.style.borderTop||"");
      // 未选中的边框：THEME.line = #33334a → rgb(51, 51, 74)，也可能是 33334a
      const dim = bd.indexOf("51, 51, 74") >= 0 || bd.indexOf("33334a") >= 0;
      out[zh]={ on: !dim, want:want[zh], border: bd.slice(0,44) };
    }
    return out;
  `);
  const mism = Object.entries(paint || {}).filter(([, v]) => v.on !== v.want);
  mism.length === 0
    ? ok("chip 选中态和实际选中一致", Object.keys(paint || {}).length + " 个 chip 核对通过")
    : bad("chip 选中态和实际选中一致", JSON.stringify(mism).slice(0, 200));

  // ---- 7. 覆盖视图里隐藏 ----
  const hidden = await ev(`
    ${OV}
    [...ov.querySelectorAll("button")].find(x=>/服装预设/.test(String(x.textContent||""))).click();
    await new Promise(r=>setTimeout(r,800));
    const row=${QROW};
    return { disp: row ? getComputedStyle(row).display : "(没了)" };
  `);
  hidden?.disp === "none"
    ? ok("服装视图里快速条隐藏")
    : bad("服装视图里快速条隐藏", `display=${hidden?.disp}`);
  await ev(`${OV} [...ov.querySelectorAll("button")].find(x=>/返回标签/.test(String(x.textContent||""))).click();
    await new Promise(r=>setTimeout(r,600)); return 1;`);

  // ---- 8. 侧栏新分类 ----
  const cats = await ev(`
    ${OV}
    const side=[...ov.querySelectorAll("div")].find(d=>getComputedStyle(d).width==="186px");
    const txt=[...side.querySelectorAll("button")].map(b=>String(b.textContent||"").replace(/\\s+/g," ").trim());
    return { hasAction: txt.filter(x=>/动作\\/姿势/.test(x)), hasView: txt.filter(x=>/镜头\\/视角/.test(x)) };
  `);
  cats?.hasAction?.length && cats?.hasView?.length
    ? ok("侧栏有「动作/姿势」「镜头/视角」分类", `${cats.hasAction[0]} / ${cats.hasView[0]}`)
    : bad("侧栏新分类", JSON.stringify(cats));

  const shot = await send("Page.captureScreenshot", { format: "png" });
  const out = path.join(process.cwd(), "animansfw_actview.png");
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  ok("截图", path.basename(out));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW|paintQuickRow|renderActViewRow/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错") : bad("控制台有报错", errs.slice(0, 2).join(" | "));

  console.log("\n=== 动作/视角快速条（真浏览器）===");
  for (const [t2, l, e] of results) console.log(`  ${t2} ${l}${e ? "  " + e : ""}`);
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
