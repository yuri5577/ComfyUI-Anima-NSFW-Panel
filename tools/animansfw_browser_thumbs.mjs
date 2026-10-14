/** 真浏览器：缩略图本地缓存。
 *   node tools/animansfw_browser_thumbs.mjs
 *
 * 覆盖：
 *   1. 面板里的缩略图 img.src 全部指向本地代理（不是境外 CDN）
 *   2. 代理请求确实返回了图片（naturalWidth > 0）
 *   3. 第二次加载走缓存（后端 X-Anima-Cache: hit）
 *   4. 头部有「缓存缩略图」按钮，统计能读出来
 *   5. 批量预热接口可用
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

const PORT = 9349;
const PROFILE = path.join(os.tmpdir(), `animansfw_th_${process.pid}`);
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

// ⚠️ 两个坑：
//  1. 代理 URL 里**带原始 CDN 地址**（?u=...），所以不能拿 src 里有没有
//     "jsdelivr" 来判断"是不是直连" —— 要解析 u 参数、看 pathname。
//  2. `loading="lazy"` 的图片在视口外**不会加载**（这是对的行为，不然一次几百
//     个请求）。所以只能统计视口内的图。
const IMG_PROBE = `
  ${OV}
  const imgs=[...ov.querySelectorAll("img")];
  function direct(x){ return x.src.indexOf("anima_nsfw/thumb") < 0; }
  function inView(x){ const r=x.getBoundingClientRect();
    return r.top < window.innerHeight && r.bottom > 0 && r.width > 0; }
  const vis=imgs.filter(inView);
  const decoded=imgs.filter(function(x){ return x.naturalWidth>0; });
  const visDecoded=vis.filter(function(x){ return x.naturalWidth>0; });
  return { total: imgs.length, direct: imgs.filter(direct).length,
           visible: vis.length, decoded: decoded.length,
           visibleDecoded: visDecoded.length,
           placeholder: [...ov.querySelectorAll("span")].filter(function(s){
             return String(s.textContent||"").trim()==="无图"; }).length,
           sample: (decoded[0]||{}).src ? decoded[0].src.slice(0,120) : null };
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
    n.widgets.find(function(w){return w.type==="button" && String(w.label||w.name||"").indexOf("面板")>=0;}).callback(); return 1;`);
  for (let i = 0; i < 140; i++) {
    await sleep(300);
    const r = await ev(`${OV} return !!(ov && ov.querySelectorAll("button").length > 15);`);
    if (r) break;
  }
  await sleep(2000);
  ok("面板已打开");

  // ---- 1. 进服装视图，看 img.src ----
  await ev(`${OV}
    [...ov.querySelectorAll("button")].find(function(x){return String(x.textContent||"").indexOf("服装预设")>=0;}).click();
    await new Promise(function(r){setTimeout(r,1500);}); return 1;`);

  // ⚠️ 不要等"所有 img 都解码"：`loading="lazy"` 的图在视口外**不会被加载**，
  //    而 headless Chrome 对"接近视口"的判定更严，所以这个断言永远等不到。
  //    实测同一 src 用 new Image() 手动加载立刻成功 —— 是断言不可靠，不是产品问题。
  //    改成：① 所有 src 都走本地代理 ② 主动加载一张，必须真的解码出来。
  let srcInfo = null;
  for (let i = 0; i < 10; i++) {
    srcInfo = await ev(IMG_PROBE);
    if ((srcInfo?.total || 0) > 0) break;
    await sleep(500);
  }
  srcInfo && srcInfo.total > 0 && srcInfo.direct === 0
    ? ok("缩略图全部走本地代理", `${srcInfo.total} 张 img 无一直连 CDN`)
    : bad("缩略图全部走本地代理", JSON.stringify(srcInfo).slice(0, 260));

  // 主动加载第一张（不依赖 lazy 的触发时机）
  const probe = await ev(`
    ${OV}
    const im = ov.querySelector("img");
    if (!im) return { ok:false, why:"视图里没有 img" };
    const src = im.src;
    const r = await fetch(src, {cache:"no-store"});
    const blob = await r.blob();
    const p = new Image();
    const done = await new Promise(function(res){
      p.onload = function(){ res("load"); };
      p.onerror = function(){ res("error"); };
      setTimeout(function(){ res("timeout"); }, 20000);
      p.src = src;
    });
    return { ok:true, event: done, naturalWidth: p.naturalWidth,
             status: r.status, type: r.headers.get("Content-Type"),
             cache: r.headers.get("X-Anima-Cache"), size: blob.size,
             src: src.slice(0, 100) };
  `);
  probe?.ok && probe.event === "load" && probe.naturalWidth > 0
    ? ok("缩略图能通过本地代理解码",
        `${probe.status} ${probe.type} ${probe.size}B [${probe.cache}] → ${probe.naturalWidth}px`)
    : bad("缩略图能通过本地代理解码", JSON.stringify(probe).slice(0, 260));
  srcInfo && srcInfo.placeholder === 0
    ? ok("没有「无图」占位（说明代理都成功了）")
    : bad("没有「无图」占位", `${srcInfo?.placeholder} 个占位`);

  // ---- 2. 缓存命中：同一个 URL 再取一次应是 hit ----
  const hitTest = await ev(`
    const url = "https://cdn.jsdelivr.net/gh/nregret/Dressing-doll@main/images/1741118591102.webp";
    const r1 = await fetch("/anima_nsfw/thumb?u=" + encodeURIComponent(url), {cache:"no-store"});
    const m1 = r1.headers.get("X-Anima-Cache");
    const r2 = await fetch("/anima_nsfw/thumb?u=" + encodeURIComponent(url), {cache:"no-store"});
    const m2 = r2.headers.get("X-Anima-Cache");
    return { first: m1, second: m2, ok: r2.ok, bytes: (await r2.blob()).size };
  `);
  ["hit", "stored"].includes(hitTest?.second) && hitTest?.ok
    ? ok("重复请求命中本地缓存", `第一次=${hitTest.first} → 第二次=${hitTest.second}  ${hitTest.bytes} 字节`)
    : bad("重复请求命中本地缓存", JSON.stringify(hitTest));

  // ---- 3. 缓存按钮 ----
  const btn = await ev(`
    ${OV}
    const b=[...ov.querySelectorAll("button")].find(function(x){
      const t=String(x.textContent||""); return t.indexOf("缓存缩略图")>=0 || t.indexOf("已缓存")>=0; });
    return b ? { text: String(b.textContent).trim(),
                 title: String(b.title||"").split("\\n")[0] } : null;
  `);
  btn ? ok("头部有缓存按钮", `${btn.text}  ｜ ${btn.title}`) : bad("头部有缓存按钮", "找不到");

  // ---- 4. 统计接口 ----
  const stats = await ev(`
    const r = await fetch("/anima_nsfw/thumb_cache/stats", {cache:"no-store"});
    return await r.json();
  `);
  stats && typeof stats.files === "number"
    ? ok("缓存统计接口可用", `文件 ${stats.files} 个 / ${stats.mb} MB，命中 ${stats.hit} 次，下载 ${stats.download} 次`)
    : bad("缓存统计接口可用", JSON.stringify(stats).slice(0, 160));

  // ---- 5. 批量预热（小批量）----
  const warm = await ev(`
    const urls = [
      "https://cdn.jsdelivr.net/gh/nregret/Dressing-doll@main/images/1741118591102.webp",
      "https://cdn.jsdelivr.net/gh/nregret/AnimaTags-DB@main/images/pose/pose_1792200000000.webp",
      "https://evil.example.com/blocked.webp"
    ];
    const r = await fetch("/anima_nsfw/thumb_cache/warm", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({urls: urls}) });
    return await r.json();
  `);
  warm && warm.ok && warm.rejected === 1
    ? ok("批量预热可用（非白名单被拒）",
        `下载 ${warm.downloaded} / 已有 ${warm.already} / 失败 ${warm.failed} / 拒绝 ${warm.rejected}`)
    : bad("批量预热可用（非白名单被拒）", JSON.stringify(warm).slice(0, 220));

  // ---- 6. 角色立绘也走代理 ----
  await ev(`${OV}
    [...ov.querySelectorAll("button")].find(function(x){return String(x.textContent||"").indexOf("返回标签")>=0;}).click();
    await new Promise(function(r){setTimeout(r,500);});
    [...ov.querySelectorAll("button")].find(function(x){return String(x.textContent||"").indexOf("角色")>=0;}).click();
    await new Promise(function(r){setTimeout(r,4000);}); return 1;`);
  let charImgs = null;
  for (let i = 0; i < 20; i++) {
    charImgs = await ev(IMG_PROBE);
    if ((charImgs?.decoded || 0) > 0) break;
    await sleep(1000);
  }
  charImgs && charImgs.total > 0 && charImgs.direct === 0
    ? ok("角色立绘也走本地代理", `${charImgs.total} 张 img 无一直连 CDN`)
    : bad("角色立绘也走本地代理", JSON.stringify(charImgs).slice(0, 220));
  charImgs && charImgs.decoded > 0
    ? ok("角色立绘能解码出来", `${charImgs.decoded}/${charImgs.total} 张已解码`)
    : bad("角色立绘能解码出来", JSON.stringify(charImgs).slice(0, 200));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW|thumb/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错") : bad("控制台有报错", errs.slice(0, 2).join(" | "));

  console.log("\n=== 缩略图本地缓存（真浏览器）===");
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
