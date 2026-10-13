/**
 * 真浏览器：测「作品」点击流程（v1.9.8 修的两个问题）。
 *
 *   node tools/animansfw_browser_works.mjs [http://127.0.0.1:8188]
 *
 * 覆盖：
 *   1. 侧栏作品列表要**合并角色库的 copies** —— 「封印者」这类只在角色库里、
 *      不是版权标签的作品也必须能点到（原来 138 个作品点不到）
 *   2. 点作品后**左侧栏不能消失** —— 原来 renderGrid 的 isWork 只认版权标签，
 *      closers 会被判成"不是作品"，网格全空 + 作品列表清空
 *   3. 点作品后网格要铺出该作品的角色卡（带立绘）
 *   4. 作品数超过一页时有「显示更多」
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

const PORT = 9345;
const PROFILE = path.join(os.tmpdir(), `animansfw_works_${process.pid}`);
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
const SIDE = `[...ov.querySelectorAll("div")].find(d=>getComputedStyle(d).width==="186px")`;
const GRID = `[...ov.querySelectorAll("div")].find(d=>d.style.padding==="10px 12px" && getComputedStyle(d).display==="flex")`;
const ST = `
  ${OV}
  const s=${SIDE}; const g=${GRID};
  return {
    sideVisible: s ? (s.offsetParent !== null) : null,
    sideDisplay: s ? getComputedStyle(s).display : null,
    sideBtns: s ? s.querySelectorAll("button").length : -1,
    gridBtns: g ? g.querySelectorAll("button").length : -1,
    gridImgs: g ? g.querySelectorAll("img").length : -1,
    gridHead: g ? String(g.textContent).replace(/\\s+/g," ").trim().slice(0,60) : "",
  };
`;

async function main() {
  let ver = null;
  for (let i = 0; i < 100; i++) {
    try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); break; }
    catch (e) { await sleep(300); }
  }
  if (!ver) throw new Error("DevTools 没起来");
  console.log("浏览器:", ver.Browser);

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
  await send("Runtime.enable");
  await send("Page.enable");
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
  await sleep(1800);
  ok("面板已打开");

  // ---- 1. 进「游戏/作品」分类，看侧栏作品列表 ----
  const cat = await ev(`
    ${OV}
    const s=${SIDE};
    const b=[...s.querySelectorAll("button")].find(x=>/游戏\\/作品/.test(String(x.textContent||"")));
    if (!b) return { ok:false, why:"找不到分类按钮" };
    b.click(); await new Promise(r=>setTimeout(r,1200));
    const side=[...s.querySelectorAll("button")].map(x=>String(x.textContent||"").replace(/\\s+/g," ").trim());
    const works=side.filter(x=>/\\d+$/.test(x));
    return { ok:true, clicked:String(b.textContent).trim(), worksN:works.length,
             hasClosers: side.filter(x=>/^封印者\\s*\\d+$/.test(x)),
             hasAzur: side.filter(x=>/^碧蓝航线\\s*\\d+$/.test(x)),
             hasMore: side.filter(x=>/显示更多/.test(x)) };
  `);
  if (cat?.ok) {
    ok("进「游戏/作品」分类", cat.clicked);
    cat.hasClosers?.length
      ? ok("侧栏作品列表含「封印者」（合并了角色库 copies）", cat.hasClosers.join(" "))
      : bad("侧栏作品列表含「封印者」", `没找到；共 ${cat.worksN} 个作品按钮`);
    cat.hasAzur?.length ? ok("侧栏作品列表含「碧蓝航线」", cat.hasAzur.join(" ")) : bad("含「碧蓝航线」");
    cat.hasMore?.length ? ok("作品超一页时有「显示更多」", cat.hasMore[0])
      : bad("作品超一页时有「显示更多」", "没找到");
  } else {
    bad("进「游戏/作品」分类", JSON.stringify(cat).slice(0, 200));
  }

  // ---- 2. 点「封印者」→ 网格要出角色、侧栏不能塌 ----
  const before = await ev(ST);
  const cl = await ev(`
    ${OV}
    const s=${SIDE};
    const b=[...s.querySelectorAll("button")].find(x=>/^封印者\\s*\\d+$/.test(String(x.textContent||"").replace(/\\s+/g," ").trim()));
    if (!b) return { ok:false, why:"侧栏找不到封印者" };
    const label=String(b.textContent).replace(/\\s+/g," ").trim();
    b.click(); await new Promise(r=>setTimeout(r,1300));
    return { ok:true, clicked:label };
  `);
  if (cl?.ok) {
    const after = await ev(ST);
    ok("点侧栏「封印者」", cl.clicked);
    after.sideDisplay !== "none" && after.sideVisible
      ? ok("点作品后左侧栏仍在", `display=${after.sideDisplay} 宽=186px`)
      : bad("点作品后左侧栏仍在", JSON.stringify(after));
    after.sideBtns >= before.sideBtns * 0.8
      ? ok("作品列表没被清空", `${before.sideBtns} → ${after.sideBtns} 个按钮`)
      : bad("作品列表没被清空", `${before.sideBtns} → ${after.sideBtns}（塌了）`);
    after.gridBtns > 0
      ? ok("网格铺出了封印者角色", `${after.gridBtns} 张卡 / ${after.gridImgs} 张立绘  ${after.gridHead.slice(0, 28)}`)
      : bad("网格铺出了封印者角色", `0 张卡  ${after.gridHead}`);
    /封印者/.test(after.gridHead)
      ? ok("网格标题是「封印者 · N 个角色」", after.gridHead.slice(0, 30))
      : bad("网格标题", after.gridHead.slice(0, 50));
  } else {
    bad("点侧栏「封印者」", JSON.stringify(cl).slice(0, 220));
  }

  // ---- 3. 再点一个版权标签作品（原神），确认没回归 ----
  const ys = await ev(`
    ${OV}
    const s=${SIDE};
    const b=[...s.querySelectorAll("button")].find(x=>/^原神\\s*\\d+$/.test(String(x.textContent||"").replace(/\\s+/g," ").trim()))
      || [...ov.querySelectorAll("button")].find(x=>/^原神/.test(String(x.textContent||"").replace(/\\s+/g," ").trim()) && x.children.length===2);
    if (!b) return { ok:false };
    b.click(); await new Promise(r=>setTimeout(r,1300));
    return { ok:true };
  `);
  if (ys?.ok) {
    const a2 = await ev(ST);
    a2.gridBtns > 50 && a2.gridImgs > 10
      ? ok("版权标签作品仍正常（原神）", `${a2.gridBtns} 张卡 / ${a2.gridImgs} 张立绘`)
      : bad("版权标签作品（原神）", JSON.stringify(a2));
    a2.sideDisplay !== "none" ? ok("原神页左侧栏仍在") : bad("原神页左侧栏仍在");
  } else {
    bad("点原神", "找不到按钮");
  }

  // ---- 4. 显示更多 ----
  const more = await ev(`
    ${OV}
    const b=[...ov.querySelectorAll("button")].find(x=>/显示更多/.test(String(x.textContent||"")));
    if (!b) return { ok:false, why:"没有显示更多按钮" };
    const label=String(b.textContent).trim();
    const s=${SIDE};
    const n0=s.querySelectorAll("button").length;
    b.click(); await new Promise(r=>setTimeout(r,900));
    return { ok:true, label, before:n0, after:s.querySelectorAll("button").length };
  `);
  if (more?.ok) {
    more.after > more.before
      ? ok("「显示更多」能展开作品", `${more.before} → ${more.after} 个按钮  （${more.label}）`)
      : bad("「显示更多」能展开作品", JSON.stringify(more));
  } else {
    bad("「显示更多」", JSON.stringify(more).slice(0, 160));
  }

  const shot = await send("Page.captureScreenshot", { format: "png" });
  const out = path.join(process.cwd(), "animansfw_works_view.png");
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  ok("截图", path.basename(out));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW|renderWorkList|inWorkContext/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错") : bad("控制台有报错", errs.slice(0, 2).join(" | "));

  console.log("\n=== 作品点击流程（真浏览器）===");
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
