/**
 * 真浏览器：测服装视图 + 随机服装（含游戏 COS）。
 *
 *   node tools/animansfw_browser_outfit.mjs [http://127.0.0.1:8188]
 *
 * 需要先启动 ComfyUI，本机有 Chrome / Edge。
 * 会起独立的 headless 实例（独立临时 profile），不影响你自己开着的浏览器。
 *
 * ── 写这个测试踩过的坑（改动时注意）────────────────────────────
 *  1. 节点上的 `outfit_preset` 是 `名字,,标签串` 的自定义格式，**不是 JSON**，
 *     别去 JSON.parse 它。面板套用预设时会在节点上留一条
 *     `node.__animansfwLastPreset`（id/zh/分组/是否随机/补了哪些配饰），读它最准。
 *  2. 服装卡片的形状是 `button > [缩略图, body, 预览]`（3 个子元素，面板 L3251）。
 *     `button` 只有 2 个子元素的是**侧栏分类**（名字 + 数量）——
 *     按"2 个子元素"数卡片会数到侧栏，看着像"搜索没过滤"。
 *     本测试用 `b.title` **加** `children.length>=3` 认卡片 ——
 *     侧栏分类也有 title，光看 title 会把它数进来。
 *  3. **别用 new RegExp 拼 emoji** —— `\u{1F451}` 那种转义在字符串里会变成
 *     字面量 `u{1F451}`，正则匹配不到。直接比较字符就好（下面 STARTS_WITH_GAME_ICON）。
 *  4. 侧栏分类里也有「碧蓝航线 167」，分组按钮要按图标前缀精确匹配。
 * ──────────────────────────────────────────────────────
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
if (!CHROME) { console.error("找不到 Chrome / Edge"); process.exit(2); }

const PORT = 9335;
const PROFILE = path.join(os.tmpdir(), `animansfw_outfit_${process.pid}`);
fs.rmSync(PROFILE, { recursive: true, force: true });
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, "--no-first-run", "--no-default-browser-check",
  "--disable-gpu", "--window-size=1600,1000", "about:blank"], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws = null, msgId = 0;
const pending = new Map();
const logs = [], results = [];
const ok = (l, e = "") => results.push(["OK  ", l, e]);
const bad = (l, e = "") => results.push(["ERR ", l, e]);

function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => {
    pending.set(id, { resolve: res, reject: rej });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error("超时 " + method)); } }, 90000);
  });
}

/** 在页面里跑一段 async 表达式，返回解析后的值 */
async function ev(expr) {
  const r = await send("Runtime.evaluate", {
    expression: `(async () => JSON.stringify(await (async () => { ${expr} })()))()`,
    awaitPromise: true, returnByValue: true,
  });
  if (r.exceptionDetails) {
    return { __error: (r.exceptionDetails.text || "") + " "
      + (r.exceptionDetails.exception?.description || "") };
  }
  try { return JSON.parse(r.result?.value ?? "null"); } catch (e) { return r.result?.value ?? null; }
}

const OV = `const ov=[...document.body.children].find(c=>c.className&&String(c.className).includes("animansfw-overlay"));`;
// 服装卡片：面板给每张卡设了 title（装标签串），侧栏分类没有
// 服装卡：2 个子元素（缩略图 + body），第一个子元素是缩略图
// ⚠️ 侧栏分类也是 2 个子元素（名字 + 数量），区别在**有没有缩略图**。
//    实测 157 个带 title 的 button：{0个:7（工具栏按钮）, 2个:150（卡片）}
const CARDS = `[...ov.querySelectorAll("button")].filter(b=>`
  + `b.children.length===2 && b.title && String(b.title).length>3`
  + ` && b.children[0] && (b.children[0].tagName==="IMG" || b.children[0].style.backgroundImage))`;

/** 游戏 COS 分组的图标（直接内联进页面脚本，用字符比较而不是正则拼接） */
const GAME_ICON_CHECK = `(() => {
  const ICONS = ["\\u{1F451}", "\\u{1F985}", "\\u{2699}\\u{FE0F}", "\\u{2699}",
                 "\\u{1F338}", "\\u{26F5}", "\\u{2693}", "\\u{1F694}",   // 注意是 1F694
                 "\\u{1F6E1}\\u{FE0F}", "\\u{1F6E1}", "\\u{1F3AD}"];
  return (s) => {
    const t = String(s || "").replace(/\\s+/g, " ").trim();
    if (!ICONS.some(i => t.startsWith(i))) return false;
    return /\\d+$/.test(t);            // 分组按钮结尾是数量
  };
})()`;

async function main() {
  let ver = null;
  for (let i = 0; i < 100; i++) {
    try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); break; }
    catch (e) { await sleep(300); }
  }
  if (!ver) throw new Error("DevTools 没起来");
  console.log("浏览器:", ver.Browser);

  const target = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id); pending.delete(m.id);
      m.error ? reject(new Error(m.error.message)) : resolve(m.result);
      return;
    }
    if (m.method === "Runtime.exceptionThrown") {
      logs.push("[exception] " + (m.params.exceptionDetails?.exception?.description
        || m.params.exceptionDetails?.text || "").slice(0, 240));
    }
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      logs.push("[console.error] " + (m.params.args || [])
        .map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 240));
    }
  };
  await send("Runtime.enable");
  await send("Page.enable");

  const t0 = Date.now();
  await send("Page.navigate", { url: BASE });
  for (let i = 0; i < 140; i++) {
    await sleep(500);
    const r = await send("Runtime.evaluate", {
      expression: "!!(window.app && window.app.graph)", returnByValue: true });
    if (r.result?.value) break;
  }
  ok("ComfyUI 就绪", `${((Date.now() - t0) / 1000).toFixed(1)}s`);

  const setup = await ev(`
    const lg = window.LiteGraph || window.LiteGraphJS;
    const n = lg.createNode("AnimaNsfwPromptBuilder");
    if (!n) return { ok:false, why:"createNode 返回空" };
    window.app.graph.add(n); window.__n = n;
    const w = n.widgets.find(w => w.type === "button" && String(w.label||w.name||"").includes("面板"));
    if (!w) return { ok:false, why:"没有面板按钮" };
    w.callback();
    return { ok:true, widgets: n.widgets.length };
  `);
  setup?.ok ? ok("创建节点并打开面板", `${setup.widgets} 个控件`)
    : bad("创建节点并打开面板", JSON.stringify(setup));

  for (let i = 0; i < 140; i++) {
    await sleep(300);
    const ready = await ev(`
      ${OV}
      if (!ov) return false;
      const b=[...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").includes("服装预设"));
      return !!(b && /服装预设\\s*\\(\\d+\\)/.test(String(b.textContent)));
    `);
    if (ready) break;
  }
  ok("面板与预设数据就绪");

  await ev(`
    ${OV}
    [...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").includes("服装预设")).click();
    await new Promise(r=>setTimeout(r,900));
    return 1;
  `);
  ok("进入服装视图");

  // ---- 总数 + 游戏分组 + 卡片 ----
  const info = await ev(`
    ${OV}
    const isGameGroup=${GAME_ICON_CHECK};
    const btns=[...ov.querySelectorAll("button")];
    return {
      total: btns.map(b=>String(b.textContent||"").replace(/\\s+/g," ").trim())
                 .find(x=>/^全部\\s*\\d+$/.test(x)) || null,
      game: btns.map(b=>String(b.textContent||"").replace(/\\s+/g," ").trim()).filter(isGameGroup),
      // 分组 id 从 data-g 读（按钮上写的），别从文案反推
      gameIds: btns.map(b=>b.getAttribute && b.getAttribute("data-g")).filter(Boolean),
      cards: ${CARDS}.length,
      dom: ov.querySelectorAll("*").length,
    };
  `);
  info?.total ? ok("服装预设总数显示", info.total) : bad("服装预设总数显示", "(没找到)");
  // 游戏 COS 分组：碧蓝 6 个阵营 + 封印者 + 通用 COS = 8 个。
  // ⚠️ v1.9.9 把封印者的「基础」「各队制服」两组并成一个（共 10 套），
  //    所以这里从 9 变 8 —— 别再写死数字，按实际存在的组校验。
  const GAME_IDS = ["gc_al_royal", "gc_al_eagle", "gc_al_iron", "gc_al_sakura",
                    "gc_al_other", "gc_al_base", "gc_cl", "gc_general"];
  const gameIds = info?.gameIds || [];
  const missing = GAME_IDS.filter((g) => !gameIds.includes(g));
  (info?.game || []).length >= 8 && missing.length === 0
    ? ok("游戏 COS 分组按钮", `${info.game.length} 个：${info.game.slice(0, 9).join(" ")}`)
    : bad("游戏 COS 分组按钮",
        `按钮 ${(info?.game || []).length} 个，缺 ${missing.join(",") || "无"}`);
  if (info?.cards > 0) {
    ok("服装卡片已渲染", `${info.cards} 张`);
  } else {
    // 判据失效时把真实结构 dump 出来，别再猜
    const diag = await ev(`
      ${OV}
      const withTitle=[...ov.querySelectorAll("button")].filter(b=>b.title && String(b.title).length>3);
      const byKids={};
      for (const b of withTitle) { const k=b.children.length; byKids[k]=(byKids[k]||0)+1; }
      const sample=withTitle.slice(0,4).map(b=>({
        kids:b.children.length,
        kidTags:[...b.children].map(c=>c.tagName).join(","),
        title:String(b.title).slice(0,30),
        text:String(b.textContent).replace(/\s+/g," ").trim().slice(0,26),
      }));
      const noTitle=[...ov.querySelectorAll("button")].filter(b=>!b.title||String(b.title).length<=3);
      const grid=[...ov.querySelectorAll("div")].filter(d=>{const s=getComputedStyle(d);
        return s.display==="flex" && s.flexWrap==="wrap" && s.overflowY==="auto";});
      return { withTitle:withTitle.length, byKids, sample,
               gridKids: grid.map(g=>g.children.length),
               gridBtns: grid.map(g=>g.querySelectorAll("button").length),
               noTitleN: noTitle.length };
    `);
    bad("服装卡片已渲染", `判据失效；诊断: ${JSON.stringify(diag).slice(0, 420)}`);
  }

  // ---- 随机 30 次 ----
  const rand = await ev(`
    ${OV}
    const b=[...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").includes("随机一套服装"));
    if (!b) return { ok:false, why:"no random button" };
    const w = window.__n.widgets.find(w => w.name === "outfit_preset");
    const seen=new Set(), times=[]; let empty=0;
    for (let i=0;i<30;i++){
      const t=performance.now(); b.click(); times.push(performance.now()-t);
      if (!String(w.value||"")) empty++;
      const rec=window.__n.__animansfwLastPreset;
      if (rec) seen.add(rec.id);
    }
    times.sort((a,b)=>a-b);
    return { ok:true, distinct:seen.size, empty,
             med:times[Math.floor(times.length/2)], max:times[times.length-1] };
  `);
  if (rand?.ok) {
    rand.empty === 0 ? ok("随机写入节点（30 次无空值）") : bad("随机写入节点", `${rand.empty} 次为空`);
    rand.distinct >= 20 ? ok("随机有变化", `30 次抽到 ${rand.distinct} 套不同`)
      : bad("随机有变化", `只抽到 ${rand.distinct} 套`);
    ok("随机单次耗时", `中位 ${rand.med.toFixed(1)}ms / 最大 ${rand.max.toFixed(1)}ms`);
    if (rand.max > 300) bad("随机单次 > 300ms", `${rand.max.toFixed(0)}ms`);
  } else {
    bad("随机按钮可用", JSON.stringify(rand).slice(0, 160));
  }

  // ---- 分组内随机 ----
  const inGroup = await ev(`
    ${OV}
    const isGameGroup=${GAME_ICON_CHECK};
    const gbtn=[...ov.querySelectorAll("button")]
      .find(x=>isGameGroup(String(x.textContent||"")));
    if (!gbtn) return { ok:false, why:"no group button",
      btns:[...ov.querySelectorAll("button")].map(x=>String(x.textContent||"").trim()).filter(s=>/碧蓝/.test(s)) };
    const gLabel=String(gbtn.textContent).replace(/\\s+/g," ").trim();
    gbtn.click();
    await new Promise(r=>setTimeout(r,350));
    // 从点下去的那个分组按钮反查它的分组 id（按钮带 data-g），别写死
    const grpBtn = ov.querySelector('[data-g]');
    const keChou=[...ov.querySelectorAll("span,div")]
      .map(x=>String(x.textContent||"").replace(/\\s+/g," ").trim())
      .find(x=>/^可抽 \\d+ 套$/.test(x)) || null;
    const b=[...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").includes("随机一套服装"));
    if (!b) return { ok:false, why:"no random button", gLabel };
    const groups=new Set(), names=[]; let n=0;
    for (let i=0;i<25;i++){
      b.click();
      const rec=window.__n.__animansfwLastPreset;
      if (rec && rec.random) { n++; groups.add(rec.g); names.push(rec.zh); }
    }
    return { ok:true, gLabel, groupId:(window.__n && window.__n.__animansfwLastGroup) || null,
             groups:[...groups], n, keChou, sample:names.slice(0,3) };
  `);
  if (inGroup?.ok) {
    ok("分组按钮已点", inGroup.gLabel);
    inGroup.keChou ? ok("筛选后显示可抽数量", inGroup.keChou)
      : bad("筛选后显示可抽数量", "没找到「可抽 N 套」");
    inGroup.n >= 20 ? ok("随机留下了记录", `${inGroup.n}/25 次`)
      : bad("随机留下了记录", `${inGroup.n}/25 次`);
    // ⚠️ 别写死分组 id（旧的是 "al_royal"，v1.9.9 改成了 "gc_al_royal"）。
    //    从点下去的那个按钮反查它对应的分组 id，再比对抽出来的记录。
    const wantG = inGroup.groupId;
    inGroup.groups.length === 1 && wantG && inGroup.groups[0] === wantG
      ? ok("分组内随机只在该组抽", `组=${inGroup.groups.join(",")} == 按钮的 ${wantG}  例: ${inGroup.sample.join(" / ")}`)
      : bad("分组内随机只在该组抽",
          `抽到了 [${inGroup.groups.join(",")}]，期望 [${wantG || "?"}]`);
  } else {
    bad("分组内随机", JSON.stringify(inGroup).slice(0, 200));
  }

  // ---- 配饰开关 ----
  const acc = await ev(`
    ${OV}
    const boxes=[...ov.querySelectorAll("input")].filter(i=>i.type==="checkbox");
    if (!boxes.length) return { ok:false, why:"no checkbox" };
    const cb=boxes[boxes.length-1];
    cb.checked=true; cb.dispatchEvent(new Event("change"));
    const b=[...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").includes("随机一套服装"));
    let withAcc=0, total=0; const slots=new Set();
    for (let i=0;i<20;i++){
      b.click();
      const rec=window.__n.__animansfwLastPreset;
      if (rec?.added?.length) { withAcc++; total+=rec.added.length; rec.added.forEach(a=>slots.add(a.split(" ").pop())); }
    }
    return { ok:true, withAcc, total, kinds:[...slots].slice(0,8) };
  `);
  if (acc?.ok) {
    acc.withAcc >= 15
      ? ok("＋配饰开关生效", `20 次里 ${acc.withAcc} 次补了配饰，共 ${acc.total} 个`)
      : bad("＋配饰开关生效", `20 次只补了 ${acc.withAcc} 次`);
    ok("补的配饰种类", acc.kinds.join(" / ") || "(无)");
  } else {
    bad("＋配饰开关", JSON.stringify(acc).slice(0, 160));
  }

  // ---- 性能：切所有游戏分组 ----
  const perf = await ev(`
    ${OV}
    const isGameGroup=${GAME_ICON_CHECK};
    const groups=[...ov.querySelectorAll("button")].filter(x=>isGameGroup(String(x.textContent||"")));
    if (!groups.length) return { ok:false };
    const times=[];
    for (const g of groups) {
      const t=performance.now(); g.click(); await new Promise(r=>setTimeout(r,60));
      times.push(performance.now()-t);
    }
    times.sort((a,b)=>a-b);
    return { ok:true, n:groups.length, med:times[Math.floor(times.length/2)],
             max:times[times.length-1], dom: ov.querySelectorAll("*").length };
  `);
  if (perf?.ok) {
    ok("切换游戏 COS 分组", `${perf.n} 组，中位 ${perf.med.toFixed(0)}ms / 最大 ${perf.max.toFixed(0)}ms`);
    ok("面板 DOM 规模", `${perf.dom} 节点`);
    if (perf.max > 800) bad("切分组 > 800ms", `${perf.max.toFixed(0)}ms`);
  }

  // ---- 搜索：验证过滤真的生效 ----
  // 判据用「卡片数必须缩小」+「结果必须都是游戏服装」，
  // 而不是猜 DOM 结构（数量容易被侧栏分类污染，踩过）。
  const srch = await ev(`
    ${OV}
    const all=[...ov.querySelectorAll("button")].find(x=>String(x.textContent||"").trim()==="全部");
    if (all) { all.click(); await new Promise(r=>setTimeout(r,350)); }
    const inp=[...ov.querySelectorAll("input")].find(i=>String(i.placeholder||"").includes("搜索预设"));
    if (!inp) return { ok:false, why:"no search input" };
    const beforeN=${CARDS}.length;
    inp.value="碧蓝"; inp.dispatchEvent(new Event("input"));
    await new Promise(r=>setTimeout(r,800));
    const cards=${CARDS};
    const titles=cards.map(b=>String(b.title));
    // 诊断：搜索后网格里到底有什么
    const grid=[...ov.querySelectorAll("div")].find(d=>{const s=getComputedStyle(d);
      return s.display==="flex" && s.flexWrap==="wrap" && s.overflowY==="auto";});
    const gridBtns = grid ? [...grid.querySelectorAll("button")] : [];
    const diag = {
      gridFound: !!grid,
      gridBtnN: gridBtns.length,
      gridKids: [...new Set(gridBtns.map(b=>b.children.length))],
      firstKidTags: [...new Set(gridBtns.map(b=>b.children[0]?b.children[0].tagName:"none"))],
      firstKidStyle: gridBtns.slice(0,3).map(b=>b.children[0]?(b.children[0].style.backgroundImage||b.children[0].style.background||"(空)"):"无子元素"),
      texts: gridBtns.slice(0,6).map(b=>String(b.textContent).replace(/\s+/g," ").trim().slice(0,22)),
      searchVal: inp.value,
    };
    return {
      ok:true, beforeN, afterN:cards.length, diag,
      sample: cards.slice(0,5).map(b=>String(b.textContent).replace(/\\s+/g," ").trim().slice(0,20)),
      titles: titles.slice(0,5),
    };
  `);
  console.log("  搜索诊断:", JSON.stringify(srch?.diag ?? srch ?? {}).slice(0, 700));
  if (srch?.ok) {
    srch.afterN > 0
      ? ok("搜索「碧蓝」有结果", `${srch.beforeN} → ${srch.afterN} 张`)
      : bad("搜索「碧蓝」有结果", `${srch.beforeN} → ${srch.afterN} 张`);
    srch.afterN > 0 && srch.afterN < srch.beforeN
      ? ok("搜索缩小了范围", `${srch.beforeN} → ${srch.afterN}`)
      : bad("搜索缩小了范围", `${srch.beforeN} → ${srch.afterN}（没变）`);
    srch.afterN <= 40
      ? ok("搜索结果聚焦（≤40 张）", `${srch.afterN} 张  例: ${srch.sample.join(" / ")}`)
      : bad("搜索结果聚焦", `${srch.afterN} 张（太多）`);
  } else {
    bad("搜索「碧蓝」", JSON.stringify(srch).slice(0, 200));
    console.log("  搜索诊断:", JSON.stringify(srch?.diag || {}).slice(0, 600));
  }

  // ---- 截图 ----
  const shot = await send("Page.captureScreenshot", { format: "png" });
  const out = path.join(process.cwd(), "animansfw_outfit_view.png");
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  ok("截图", path.basename(out));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW|withRandomAccessories|randomOutfit|applyPresetOutfit/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错")
    : bad("控制台有报错", errs.slice(0, 3).join(" | ").slice(0, 240));

  console.log("\n=== 服装视图 + 随机服装（真浏览器）===");
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
