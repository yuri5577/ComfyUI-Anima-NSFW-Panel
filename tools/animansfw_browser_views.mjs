/**
 * 真浏览器：把面板每个视图都点一遍，量耗时并检查有没有报错。
 *
 *   node tools/animansfw_browser_views.mjs [http://127.0.0.1:8188]
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

const PORT = 9334;
const PROFILE = path.join(os.tmpdir(), `animansfw_views_${process.pid}`);
fs.rmSync(PROFILE, { recursive: true, force: true });
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, "--no-first-run", "--no-default-browser-check",
  "--disable-gpu", "--window-size=1600,1000", "about:blank"], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws = null, msgId = 0;
const pending = new Map();
const logs = [];
const results = [];
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

async function main() {
  let ver = null;
  for (let i = 0; i < 100; i++) {
    try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); break; }
    catch (e) { await sleep(300); }
  }
  if (!ver) throw new Error("DevTools 没起来");

  const target = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id); pending.delete(m.id);
      m.error ? reject(new Error(m.error.message)) : resolve(m.result);
      return;
    }
    if (m.method === "Runtime.exceptionThrown") {
      logs.push("[exception] " + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || "").slice(0, 200));
    }
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      logs.push("[console.error] " + (m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 200));
    }
  };
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: BASE });

  for (let i = 0; i < 120; i++) {
    await sleep(500);
    const r = await send("Runtime.evaluate", { expression: "!!(window.app && window.app.graph)", returnByValue: true });
    if (r.result?.value) break;
  }

  const setup = await send("Runtime.evaluate", {
    expression: `(() => {
      const lg = window.LiteGraph || window.LiteGraphJS;
      const n = lg.createNode("AnimaNsfwPromptBuilder");
      window.app.graph.add(n); window.__n = n;
      const w = n.widgets.find(w => w.type === "button" && String(w.label||w.name||"").includes("面板"));
      window.__b = w;
      w.callback();
      return "ok";
    })()`, returnByValue: true,
  });
  if (setup.result?.value !== "ok") { bad("创建节点并开面板"); }

  // 等面板就绪
  for (let i = 0; i < 100; i++) {
    await sleep(200);
    const r = await send("Runtime.evaluate", {
      expression: `(() => { const ov=[...document.body.children].find(c=>c.className&&String(c.className).includes("animansfw-overlay"));
        return ov && ov.querySelectorAll("button").length > 20 ? "ready" : "no"; })()`,
      returnByValue: true,
    });
    if (r.result?.value === "ready") break;
  }
  ok("面板已就绪");

  // 逐个视图点一遍
  const VIEWS = [
    ["服装预设", "outfits"],
    ["姿势参考", "poses"],
    ["我的", "mine"],
    ["角色", "chars"],
    ["剧情", "story"],
  ];
  for (const [label, key] of VIEWS) {
    const r = await send("Runtime.evaluate", {
      expression: `(async () => {
        const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
        if (!ov) return JSON.stringify({ ok: false, why: "no overlay" });
        const btn = [...ov.querySelectorAll("button")].find(b => String(b.textContent||"").includes(${JSON.stringify(label)}));
        if (!btn) return JSON.stringify({ ok: false, why: "no button: " + ${JSON.stringify(label)} });
        const t0 = performance.now();
        btn.click();
        await new Promise(r => setTimeout(r, 400));
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        const ms = performance.now() - t0;
        // ⚠️ 剧情视图首次要拉 /anima_nsfw/story（故事线 + 每拍台词），
        //    400ms 不够 —— 后面的「套用这一拍」断言会撞竞态（实测偶发失败）。
        //    这里额外等它渲染出来（最多 3 秒），性能测量仍然只看上面那 400ms。
        if (${JSON.stringify("story")} === "story") {
          for (let i = 0; i < 20; i++) {
            const hit = [...ov.querySelectorAll("button")].some(b =>
              String(b.textContent || "").includes("套用"));
            if (hit) break;
            await new Promise(r => setTimeout(r, 150));
          }
        }
        const nodes = ov.querySelectorAll("*").length;
        const imgs = ov.querySelectorAll("img").length;
        const cards = [...ov.querySelectorAll("button")].filter(b => b.children.length >= 2 && b.textContent.length > 1).length;
        return JSON.stringify({ ok: true, ms, nodes, imgs, cards, label: ${JSON.stringify(label)} });
      })()`,
      awaitPromise: true, returnByValue: true,
    });
    let d = {};
    try { d = JSON.parse(r.result?.value || "{}"); } catch (e) { /* ignore */ }
    if (d.ok) {
      const flag = d.ms > 2000 ? "  ← 慢" : "";
      ok(`切换到「${label}」`, `${d.ms.toFixed(0)} ms · ${d.nodes} DOM · ${d.cards} 卡片 · ${d.imgs} 图${flag}`);
      if (d.ms > 4000) bad(`「${label}」切换 > 4s`, `${d.ms.toFixed(0)}ms`);
    } else {
      bad(`切换到「${label}」`, JSON.stringify(d).slice(0, 150));
    }
  }

  // 剧情视图里套用一拍
  //
  // ⚠️ 这一步曾经偶发失败（找不到「套用这一拍」）。诊断脚本里每次都正常，
  //    所以先**等按钮出现**（最多 12 秒），失败时再把现场 dump 出来 ——
  //    不要靠"多睡一会儿"蒙过去。
  const waitApply = await send("Runtime.evaluate", {
    expression: `(async () => {
      const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
      if (!ov) return JSON.stringify({ ok:false, why:"no overlay" });
      for (let i = 0; i < 60; i++) {
        const hit = [...ov.querySelectorAll("button")].some(b => String(b.textContent||"").includes("套用"));
        if (hit) return JSON.stringify({ ok:true, waited: i * 200 });
        await new Promise(r => setTimeout(r, 200));
      }
      const bar = [...ov.querySelectorAll("div")].find(d => d.style.maxHeight === "42vh");
      const grid = [...ov.querySelectorAll("div")].find(d => d.style.padding === "10px 12px");
      return JSON.stringify({ ok:false, why:"等 12 秒也没出现",
        nodes: ov.querySelectorAll("*").length,
        barText: bar ? String(bar.textContent||"").replace(/\s+/g," ").trim().slice(0,120) : "(没找到剧情条)",
        gridText: grid ? String(grid.textContent||"").replace(/\s+/g," ").trim().slice(0,120) : "(没找到网格)",
        btns: [...ov.querySelectorAll("button")].map(b => String(b.textContent||"").replace(/\s+/g," ").trim()).slice(0, 26) });
    })()`,
    awaitPromise: true, returnByValue: true,
  });
  let w = {};
  try { w = JSON.parse(waitApply.result?.value || "{}"); } catch (e) { /* ignore */ }
  if (w.ok) {
    ok("剧情视图渲染出「套用这一拍」", `等了 ${w.waited}ms`);
  } else {
    bad("剧情视图渲染出「套用这一拍」", JSON.stringify(w).slice(0, 400));
  }

  const applyScene = await send("Runtime.evaluate", {
    expression: `(async () => {
      const ov = [...document.body.children].find(c => c.className && String(c.className).includes("animansfw-overlay"));
      const btn = [...ov.querySelectorAll("button")].find(b => String(b.textContent||"").includes("套用"));
      if (!btn) return JSON.stringify({ ok: false, why: "没找到「套用这一拍」按钮" });
      btn.click();
      await new Promise(r => setTimeout(r, 600));
      const tags = (window.__n.widgets.find(w => w.name === "tags") || {}).value || "";
      const ct = (window.__n.widgets.find(w => w.name === "caption_text") || {}).value || "";
      const sm = (window.__n.widgets.find(w => w.name === "seed_mode") || {}).value || "";
      return JSON.stringify({ ok: true, tagsLen: tags.length, hasLock: tags.includes("char_lock"),
        ctEmpty: ct === "", seedMode: sm, head: tags.slice(0, 60) });
    })()`, awaitPromise: true, returnByValue: true,
  });
  let sa = {};
  try { sa = JSON.parse(applyScene.result?.value || "{}"); } catch (e) { /* ignore */ }
  if (sa.ok) {
    ok("剧情「套用这一拍」写入节点", `${sa.tagsLen} 字符`);
    sa.hasLock ? ok("标签带 char_lock（主角锁定）") : bad("标签带 char_lock");
    sa.ctEmpty ? ok("台词没有写进 caption_text") : bad("台词被写进了 caption_text");
    /递增/.test(sa.seedMode) ? ok("种子自动切到递增", sa.seedMode) : bad("种子自动切到递增", sa.seedMode);
  } else {
    bad("剧情「套用这一拍」", JSON.stringify(sa).slice(0, 160));
  }

  // 每个视图都截一张
  const shots = {};
  for (const [label, key] of [["tags", "全部标签"], ...VIEWS.map(([l, k]) => [k, l])]) {
    await send("Runtime.evaluate", {
      expression: `(() => { const ov=[...document.body.children].find(c=>c.className&&String(c.className).includes("animansfw-overlay"));
        const b=[...ov.querySelectorAll("button")].find(b=>String(b.textContent||"").includes(${JSON.stringify(label === "tags" ? "全部标签" : label)}));
        if (b) b.click(); return 1; })()`, returnByValue: true,
    });
    await sleep(500);
    const s = await send("Page.captureScreenshot", { format: "png" });
    shots[key] = path.join(process.cwd(), `animansfw_view_${key}.png`);
    fs.writeFileSync(shots[key], Buffer.from(s.data, "base64"));
  }
  ok("各视图截图已保存", Object.values(shots).map((p) => path.basename(p)).join(", "));

  const errs = logs.filter((l) => /animansfw|AnimaNSFW/i.test(l));
  errs.length === 0 ? ok("控制台没有本包报错") : bad("控制台有报错", errs.slice(0, 3).join(" | ").slice(0, 240));

  console.log("\n=== 各视图实测 ===");
  for (const [t, l, e] of results) console.log(`  ${t} ${l}${e ? "  " + e : ""}`);
  const n = results.filter((r) => r[0] === "ERR ").length;
  console.log(`\n${n === 0 ? "全部通过" : n + " 项失败"}`);
  if (logs.length) { console.log("\n--- 浏览器报错 ---"); logs.slice(0, 10).forEach((l) => console.log("  " + l)); }
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
  console.error("崩了:", e.message); logs.slice(-8).forEach((l) => console.error("  " + l));
  cleanup(); process.exit(2);
}
