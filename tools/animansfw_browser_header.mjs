/**
 * 真浏览器：测 v1.9.7 的两处改动。
 *
 *   node tools/animansfw_browser_header.mjs [http://127.0.0.1:8188]
 *
 * 1. 头部「🎲 随机服装」按钮 —— 任何视图都能点，自动切到服装视图并随机
 * 2. Closers（封印者）角色进了角色库，能搜到、能用
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

const PORT = 9339;
const PROFILE = path.join(os.tmpdir(), `animansfw_hdr_${process.pid}`);
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
      logs.push((m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 240));
    }
    if (m.method === "Runtime.exceptionThrown") {
      logs.push("[exc] " + (m.params.exceptionDetails?.exception?.description || "").slice(0, 240));
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
  ok("ComfyUI 就绪");

  await ev(`
    const lg = window.LiteGraph || window.LiteGraphJS;
    const n = lg.createNode("AnimaNsfwPromptBuilder");
    window.app.graph.add(n); window.__n = n;
    n.widgets.find(w => w.type === "button" && String(w.label||w.name||"").includes("面板")).callback();
    return 1;
  `);
  for (let i = 0; i < 140; i++) {
    await sleep(300);
    const r = await ev(`${OV} return !!(ov && ov.querySelectorAll("button").length > 15);`);
    if (r) break;
  }
  ok("面板已打开");

  // ---- 1. 头部是否有 🎲 随机服装 ----
  const hdr = await ev(`
    ${OV}
    // 头部 = overlay 里那个「直接子按钮 ≥ 6 个」的 div
    const cands=[...ov.querySelectorAll("div")].filter(d=>d.querySelectorAll(":scope > button").length>=6);
    const h=cands[0];
    if (!h) return { ok:false };
    const btns=[...h.querySelectorAll(":scope > button")];
    return { ok:true, labels: btns.map(b=>String(b.textContent).replace(/\\s+/g," ").trim()),
             hasDice: btns.some(b=>String(b.textContent).includes("随机服装")) };
  `);
  hdr?.hasDice
    ? ok("头部有「🎲 随机服装」", (hdr.labels || []).join(" | "))
    : bad("头部有「🎲 随机服装」", (hdr?.labels || []).join(" | ") || "(没找到头部)");

  // ---- 2. 在「标签视图」点头部随机：应自动切到服装视图并抽出一套 ----
  const fromTags = await ev(`
    ${OV}
    const h=[...ov.querySelectorAll("div")].filter(d=>d.querySelectorAll(":scope > button").length>=6)[0];
    const dice=[...h.querySelectorAll(":scope > button")].find(b=>String(b.textContent).includes("随机服装"));
    if (!dice) return { ok:false, why:"no dice" };
    // 先确认当前不在服装视图
    const outfitBtn=[...h.querySelectorAll(":scope > button")].find(b=>String(b.textContent).includes("服装预设"));
    const beforeView = String(outfitBtn.textContent).trim();
    dice.click();
    await new Promise(r=>setTimeout(r,900));
    const w=window.__n.widgets.find(w=>w.name==="outfit_preset");
    const rec=window.__n.__animansfwLastPreset;
    const afterView = String(outfitBtn.textContent).trim();
    return { ok:true, beforeView, afterView,
             wrote: String(w.value||"").length>0,
             preset: rec ? {zh:rec.zh, g:rec.g, random:rec.random} : null,
             onOutfitView: afterView.includes("返回标签") };
  `);
  if (fromTags?.ok) {
    fromTags.onOutfitView
      ? ok("点头部随机自动切到服装视图", `${fromTags.beforeView} → ${fromTags.afterView}`)
      : bad("点头部随机自动切到服装视图", `视图没变（${fromTags.afterView}）`);
    fromTags.wrote ? ok("头部随机写出了服装", fromTags.preset ? `${fromTags.preset.zh}（${fromTags.preset.g}）` : "")
      : bad("头部随机写出了服装", "outfit_preset 为空");
    fromTags.preset?.random ? ok("记录标记为随机") : bad("记录标记为随机");
  } else {
    bad("头部随机按钮", JSON.stringify(fromTags).slice(0, 200));
  }

  // ---- 3. 在服装视图再点：应尊重筛选 ----
  const inOutfit = await ev(`
    ${OV}
    const h=[...ov.querySelectorAll("div")].filter(d=>d.querySelectorAll(":scope > button").length>=6)[0];
    const dice=[...h.querySelectorAll(":scope > button")].find(b=>String(b.textContent).includes("随机服装"));
    // 点一个游戏分组
    const isGame=(s)=>{const t=String(s||"").replace(/\\s+/g," ").trim();
      return /^(\\u{1F451}|\\u{1F985}|\\u2699|\\u{1F338}|\\u26F5|\\u2693|\\u{1F694}|\\u{1F6E1}|\\u{1F3AD})/.test(t) && /\\d+$/.test(t);};
    const g=[...ov.querySelectorAll("button")].find(b=>isGame(String(b.textContent||"")));
    if (g) { g.click(); await new Promise(r=>setTimeout(r,350)); }
    const gsel = g ? String(g.textContent).replace(/\\s+/g," ").trim() : "(无)";
    const groups=new Set(); const names=[];
    for (let i=0;i<12;i++){
      dice.click();
      await new Promise(r=>setTimeout(r,30));
      const rec=window.__n.__animansfwLastPreset;
      if (rec) { groups.add(rec.g); names.push(rec.zh); }
    }
    return { ok:true, gsel, groups:[...groups], sample:names.slice(0,3) };
  `);
  if (inOutfit?.ok) {
    inOutfit.groups.length === 1
      ? ok("服装视图内点随机尊重分组筛选", `筛「${inOutfit.gsel}」→ 12 次全在 ${inOutfit.groups[0]}`)
      : bad("服装视图内点随机尊重分组筛选", `筛「${inOutfit.gsel}」却抽到 [${inOutfit.groups.join(",")}]`);
  } else {
    bad("服装视图内随机", JSON.stringify(inOutfit).slice(0, 180));
  }

  // ---- 4. Closers 角色 ----
  const cl = await ev(`
    ${OV}
    const h=[...ov.querySelectorAll("div")].filter(d=>d.querySelectorAll(":scope > button").length>=6)[0];
    const charBtn=[...ov.querySelectorAll("button")].find(b=>/角色\\s*\\(/.test(String(b.textContent)));
    if (!charBtn) return { ok:false, why:"no char button" };
    charBtn.click();
    await new Promise(r=>setTimeout(r,1200));
    const inp=[...ov.querySelectorAll("input")].find(i=>String(i.placeholder||"").includes("搜索角色"));
    if (!inp) return { ok:false, why:"no char search" };
    const found={};
    for (const q of ["封印者","closers","未来","米斯特汀"]) {
      inp.value=q; inp.dispatchEvent(new Event("input"));
      await new Promise(r=>setTimeout(r,600));
      const cards=[...ov.querySelectorAll("button")].filter(b=>b.children.length===2 && b.title && String(b.title).length>3);
      found[q]={n:cards.length, sample:cards.slice(0,2).map(c=>String(c.textContent).replace(/\\s+/g," ").trim().slice(0,24))};
    }
    return { ok:true, found, label:String(charBtn.textContent).trim() };
  `);
  if (cl?.ok) {
    ok("角色视图可打开", cl.label);
    const f = cl.found || {};
    f["封印者"]?.n > 0
      ? ok("搜「封印者」命中角色", `${f["封印者"].n} 张  例: ${f["封印者"].sample.join(" / ")}`)
      : bad("搜「封印者」命中角色", "0 张");
    f["closers"]?.n > 0
      ? ok("搜「closers」命中角色", `${f["closers"].n} 张`)
      : bad("搜「closers」命中角色", "0 张");
    f["米斯特汀"]?.n > 0
      ? ok("搜中文名「米斯特汀」命中", `${f["米斯特汀"].n} 张  例: ${f["米斯特汀"].sample.join(" / ")}`)
      : bad("搜中文名「米斯特汀」命中", "0 张");
  } else {
    bad("Closers 角色搜索", JSON.stringify(cl).slice(0, 200));
  }

  // 截图（角色视图）
  const shot = await send("Page.captureScreenshot", { format: "png" });
  const out = path.join(process.cwd(), "animansfw_closers_chars.png");
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  ok("截图", path.basename(out));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW|randomOutfit|diceBtn/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错") : bad("控制台有报错", errs.slice(0, 2).join(" | "));

  console.log("\n=== 头部随机按钮 + Closers 角色（真浏览器）===");
  for (const [t, l, e] of results) console.log(`  ${t} ${l}${e ? "  " + e : ""}`);
  const n = results.filter((r) => r[0] === "ERR ").length;
  console.log(`\n${n === 0 ? "全部通过" : n + " 项失败"}`);
  if (logs.length) { console.log("\n--- 浏览器报错 ---"); logs.slice(0, 6).forEach((l) => console.log("  " + l)); }
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
