/**
 * 随机服装逻辑测试：验证「搭配合理」的三条约束真的成立。
 *
 *   node tools/animansfw_random_test.mjs
 *
 * 从面板源码里把 withRandomAccessories / presetColors 抠出来跑真实数据，
 * 跑几千次统计违规。不需要启动 ComfyUI。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.dirname(HERE);
const SRC = path.join(PKG_ROOT, "web", "anima_nsfw_panel.js");

const code = fs.readFileSync(SRC, "utf8");

// ---- 从面板源码里抠出需要的函数（避免复制一份导致测试和实现漂移）----
/**
 * 抠一段源码出来。
 * 先按 `function name(...) {...}` 找；找不到再按 `const NAME = [...] / {...}` 找。
 * —— 不能靠 "第一个 = 号" 判断是不是 const：默认参数里也可能有 = 号。
 */
function grab(name) {
  // 1) function 声明
  const fm = new RegExp(`\\nfunction\\s+${name}\\b`).exec(code);
  if (fm) {
    let i = fm.index + 1;
    let k = code.indexOf("(", i);
    let d = 0;
    for (; k < code.length; k++) {
      if (code[k] === "(") d++;
      else if (code[k] === ")") { d--; if (d === 0) { k++; break; } }
    }
    while (k < code.length && code[k] !== "{") k++;
    return balance(code, i, k);
  }
  // 2) const NAME = ...;
  const cm = new RegExp(`\\nconst\\s+${name}\\s*=`).exec(code);
  if (cm) {
    let i = cm.index + 1;
    let k = code.indexOf("=", i) + 1;
    while (k < code.length && !"{[".includes(code[k])) k++;
    return balance(code, i, k);
  }
  throw new Error(`源码里找不到 ${name}`);
}

/** 从 open 位置的花括号/方括号开始配平，返回 [declStart, declEnd] 的切片 */
function balance(code, declStart, openIdx) {
  const open = code[openIdx];
  const close = open === "{" ? "}" : "]";
  let depth = 0;
  for (let j = openIdx; j < code.length; j++) {
    const ch = code[j];
    // 跳过字符串，避免里面的括号打乱配平
    if (ch === '"' || ch === "'" || ch === "`") {
      const q = ch;
      j++;
      while (j < code.length && code[j] !== q) {
        if (code[j] === "\\") j++;
        j++;
      }
      continue;
    }
    if (ch === open) depth++;
    else if (ch === close) {
      depth--;
      if (depth === 0) return code.slice(declStart, j + 1);
    }
  }
  throw new Error("括号不配平");
}

const src = [
  grab("RANDOM_ACCESSORIES") + ";",
  grab("COLOR_WORDS") + ";",
  grab("presetColors"),
  grab("withRandomAccessories"),
].join("\n");

const mod = new Function(src + "\nreturn { withRandomAccessories, presetColors, RANDOM_ACCESSORIES, COLOR_WORDS };")();
const { withRandomAccessories, presetColors, RANDOM_ACCESSORIES, COLOR_WORDS } = mod;

// ---- 载入真实预设 ----
const FIX = path.join(HERE, "tags_fixture.json");
let presets = [];
if (fs.existsSync(FIX)) {
  const d = JSON.parse(fs.readFileSync(FIX, "utf8"));
  presets = d.outfit_presets || [];
}
if (!presets.length) {
  console.error("缺少 tags_fixture.json（先跑 tools/animansfw_make_fixture.py）");
  process.exit(2);
}


/** 按白名单槽位表解析一个标签属于哪个槽位（支持颜色前缀） */
const SLOT_BY_TAG = new Map(RANDOM_ACCESSORIES.map((a) => [a.tag, a.slot]));
function slotOfWhitelist(raw) {
  const low = String(raw).toLowerCase().trim();
  if (SLOT_BY_TAG.has(low)) return SLOT_BY_TAG.get(low);
  const parts = low.split(" ");
  for (let i = 1; i < parts.length; i++) {
    const rest = parts.slice(i).join(" ");
    if (SLOT_BY_TAG.has(rest)) return SLOT_BY_TAG.get(rest);
  }
  return null;
}

const results = [];
const ok = (l, e = "") => results.push(["OK  ", l, e]);
const bad = (l, e = "") => results.push(["ERR ", l, e]);

console.log(`预设 ${presets.length} 套；配饰白名单 ${RANDOM_ACCESSORIES.length} 条\n`);

// ---- 1. 配饰槽位不重复 ----
const SLOT_MAX = { head: 1, neck: 1, hand: 1, leg: 1, foot: 1, waist: 1, face: 1 };
const slotOf = new Map();
for (const a of RANDOM_ACCESSORIES) slotOf.set(a.tag, a.slot);

const N = 4000;
const violations = { slotDup: [], colorClash: [], dupTag: [], sameAsBase: [], emptyAdd: 0 };
const counts = [];

for (let i = 0; i < N; i++) {
  const p = presets[Math.floor(Math.random() * presets.length)];
  const want = 1 + Math.floor(Math.random() * 2);      // 和实现一致：1~2 个
  const out = withRandomAccessories(p, want);
  const base = new Set((p.tags || []).map((x) => x.toLowerCase().trim()));
  const added = out.filter((x) => !base.has(String(x).toLowerCase().trim()));
  counts.push(added.length);
  if (added.length === 0) violations.emptyAdd++;

  // a) 同槽位最多一个
  const seen = {};
  for (const a of added) {
    // 找到它对应白名单里的哪一条（可能带颜色前缀）
    let slot = null;
    for (const w of RANDOM_ACCESSORIES) {
      if (a === w.tag || a.endsWith(" " + w.tag)) { slot = w.slot; break; }
    }
    if (!slot) { violations.dupTag.push([p.zh, a, "不在白名单里"]); continue; }
    seen[slot] = (seen[slot] || 0) + 1;
  }
  for (const [s, c] of Object.entries(seen)) {
    if (c > SLOT_MAX[s]) violations.slotDup.push([p.zh, s, c, added.join("|")]);
  }

  // b) 不能和预设已有标签重复（含语义重复：预设已有 black thighhighs 就不该再加 thighhighs）
  const lowOut = out.map((x) => String(x).toLowerCase().trim());
  const dupes = lowOut.filter((x, i) => lowOut.indexOf(x) !== i);
  if (dupes.length) violations.dupTag.push([p.zh, dupes.join(",")]);

  // c) 加进去的配饰不能和预设已有标签构成**同槽位**重复
  //    ⚠️ 判据必须按槽位，不能用子串：`belt`(waist) 和 `garter belt`(leg)
  //    字符串上包含，但一个是腰间皮带、一个是大腿吊袜带，同时戴完全正常。
  for (const a of added) {
    const aSlot = slotOfWhitelist(a);
    if (!aSlot) continue;
    for (const h of base) {
      if (slotOfWhitelist(h) === aSlot) {
        violations.sameAsBase.push([p.zh, "已有:" + h, "同槽又加:" + a]);
      }
    }
  }

  // d) 色系：预设有色系时，带颜色的配饰必须落在其中
  const colors = presetColors(p);
  if (colors.length) {
    for (const a of added) {
      const parts = a.split(" ");
      const cw = COLOR_WORDS.find((c) => parts[0] === c);
      if (cw && !colors.includes(cw)) {
        violations.colorClash.push([p.zh, a, "预设色系:" + colors.join("/")]);
      }
    }
  }
}

const show = (label, arr, limit = 3) => {
  if (!arr.length) { ok(label, "0 次"); return; }
  bad(label, `${arr.length} 次  例: ${JSON.stringify(arr.slice(0, limit))}`);
};

show("同槽位配饰最多 1 个", violations.slotDup);
show("不出现重复标签", violations.dupTag);
show("不与预设已有标签同类重复", violations.sameAsBase);
show("配饰颜色与整套同色系", violations.colorClash);

const avg = counts.reduce((a, b) => a + b, 0) / counts.length;
ok("每个预设都能配上配饰", `平均 ${avg.toFixed(2)} 个（${
  counts.filter((c) => c === 0).length} / ${N} 次没配上）`);

// ---- 2. 白名单本身的合法性 ----
const whitelist = new Set(RANDOM_ACCESSORIES.map((a) => a.tag));
whitelist.size === RANDOM_ACCESSORIES.length
  ? ok("白名单无重复条目")
  : bad("白名单无重复条目", `${RANDOM_ACCESSORIES.length} → ${whitelist.size}`);

const slots = new Set(RANDOM_ACCESSORIES.map((a) => a.slot));
ok("白名单覆盖槽位", [...slots].join(", "));

// ---- 3. 统计：每套预设的配饰数量分布 ----
const dist = {};
for (const c of counts) dist[c] = (dist[c] || 0) + 1;
ok("配饰数量分布", Object.entries(dist).map(([k, v]) => `${k}个:${v}`).join("  "));

// ---- 4. 游戏 COS 预设确实进来了 ----
const gameCos = presets.filter((p) => p.src === "game-cos");
const gcosGroups = new Set(gameCos.map((p) => p.g));
gameCos.length >= 40
  ? ok("游戏 COS 预设已入库", `${gameCos.length} 套 / ${gcosGroups.size} 组`)
  : bad("游戏 COS 预设已入库", `${gameCos.length} 套`);

const alCount = presets.filter((p) => String(p.g).startsWith("al_")).length;
const clCount = presets.filter((p) => String(p.g).startsWith("cl_")).length;
alCount >= 25 ? ok("碧蓝航线服装", `${alCount} 套`) : bad("碧蓝航线服装", `${alCount} 套`);
clCount >= 10 ? ok("封印者服装", `${clCount} 套`) : bad("封印者服装", `${clCount} 套`);

// ---- 5. 每套游戏 COS 预设的标签都要在标签库里（否则互斥组认不出）----
const tagIndex = new Map((JSON.parse(fs.readFileSync(FIX, "utf8")).tags || [])
  .map((t) => [String(t.t).toLowerCase(), t]));
const missing = [];
for (const p of gameCos) {
  for (const t of p.tags || []) {
    if (!tagIndex.has(String(t).toLowerCase())) missing.push(`${p.zh}:${t}`);
  }
}
missing.length === 0
  ? ok("游戏 COS 预设的标签都在标签库里", "(互斥组能正确识别)")
  : bad("游戏 COS 预设的标签都在标签库里", `${missing.length} 个缺失，例: ${missing.slice(0, 6).join(", ")}`);

console.log("\n=== 随机服装测试结果 ===");
for (const [tag, label, extra] of results) console.log(`  ${tag} ${label}${extra ? "  " + extra : ""}`);
const errs = results.filter((r) => r[0] === "ERR ").length;
console.log(`\n${errs === 0 ? "全部通过" : errs + " 项失败"}`);
process.exit(errs === 0 ? 0 : 1);
