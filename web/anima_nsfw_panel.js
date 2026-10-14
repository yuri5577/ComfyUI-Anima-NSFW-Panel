import { app } from "../../scripts/app.js";

/**
 * Anima NSFW 提示词面板 —— 前端可视化选标签
 *
 * 设计要点
 *  --------
 *  * `tags` 是 Python 侧的隐藏 STRING 控件，面板只是它的编辑界面，
 *    这样序列化、连线、API 调用都还是原生的字符串语义。
 *  * 面板是挂在 document.body 上的固定浮层（不是节点内的 DOM widget），
 *    避免跟着节点缩放/平移出问题；节点上只放一个只读的预览 DOM widget。
 *  * 提示词的实际合成走 Python 的 /anima_nsfw/preview，保证预览和出图一致。
 */

const BUILDER_NODE = "AnimaNsfwPromptBuilder";
const NEGATIVE_NODE = "AnimaNsfwNegativeBuilder";
const TAGS_URL = "anima_nsfw/tags";
const PREVIEW_URL = "anima_nsfw/preview";

const THEME = {
    bg: "#12121b",
    panel: "#1b1b27",
    panel2: "#22222f",
    line: "#33334a",
    text: "#e6e6f0",
    dim: "#9a9ab0",
    accent: "#f472b6",
    accentSoft: "rgba(244, 114, 182, 0.16)",
    accentLine: "rgba(244, 114, 182, 0.5)",
    warn: "#fbbf24",
    danger: "#f87171",
    outfit: "#e879f9",
    pose: "#38bdf8",
    poseSoft: "rgba(56,189,248,0.16)",
    poseLine: "rgba(56,189,248,0.5)",
    story: "#facc15",
    storySoft: "rgba(250,204,21,0.16)",
    storyLine: "rgba(250,204,21,0.5)",
    sfw: "#4ade80",
    sfwSoft: "rgba(74,222,128,0.16)",
    sfwLine: "rgba(74,222,128,0.5)",
    nsfw: "#fb7185",
    nsfwSoft: "rgba(251,113,133,0.16)",
    nsfwLine: "rgba(251,113,133,0.5)",
    char: "#818cf8",
    charSoft: "rgba(129,140,248,0.16)",
    charLine: "rgba(129,140,248,0.5)",
    mine: "#fbbf24",
    mineSoft: "rgba(251,191,36,0.16)",
    mineLine: "rgba(251,191,36,0.5)",
    lock: "#fbbf24",
};

const RATING_COLORS = {
    soft: "#34d399",
    hard: "#f472b6",
    extreme: "#f87171",
    meta: "#94a3b8",
};

// ---------------------------------------------------------------------------
// 低版本前端兼容工具
// ---------------------------------------------------------------------------
// 老版 ComfyUI / 受限环境里这些 API 可能不存在，一旦直接调用就会抛异常，
// 把 setupBuilder 整个打断 —— 表现就是「节点上没有面板按钮 / 点了没反应」。

/** requestAnimationFrame 兜底（没有就用 setTimeout） */
function raf(fn) {
    try {
        if (typeof requestAnimationFrame === "function") return requestAnimationFrame(fn);
    } catch (e) { /* 忽略 */ }
    return setTimeout(fn, 16);
}

/**
 * 设置元素样式，优先用 cssText（一次搞定），失败则逐个属性赋值。
 * `cssText` 是 `["color:red", "width:100%"].join(";")` 这种形式。
 */
function setStyle(el, cssText) {
    if (!el) return;
    try {
        if (el.style && "cssText" in el.style) {
            el.style.cssText = cssText;
            return;
        }
    } catch (e) { /* 落到逐条赋值 */ }
    try {
        for (const piece of String(cssText).split(";")) {
            const i = piece.indexOf(":");
            if (i <= 0) continue;
            const k = piece.slice(0, i).trim();
            const v = piece.slice(i + 1).trim();
            if (k) el.style[k] = v;
        }
    } catch (e) { /* 实在不行就算了，不影响功能 */ }
}

/** 复制到剪贴板（老前端没有 navigator.clipboard 时用 execCommand 兜底） */
async function copyText(text) {
    try {
        if (globalThis.navigator?.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (e) { /* 落到兜底 */ }
    try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-100000px";
        document.body.appendChild(ta);
        ta.select?.();
        const done = document.execCommand?.("copy");
        ta.remove?.();
        return !!done;
    } catch (e) {
        return false;
    }
}

// 预设卡片一次最多渲染多少张（500+ 张卡片 + 图片会拖慢面板）
const CARD_LIMIT = 150;

const STATE = {
    data: null,
    loading: null,
    storyLoading: null,      // /anima_nsfw/story 的并发去重（剧情视图快速切换会连点）
    showThumbs: null,        // null = 未初始化，默认开
};

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------

async function loadTagData() {
    if (STATE.data) return STATE.data;
    if (STATE.loading) return STATE.loading;
    STATE.loading = (async () => {
        const resp = await fetch(TAGS_URL, { cache: "no-cache" });
        if (!resp.ok) throw new Error(`标签库请求失败: HTTP ${resp.status}`);
        const data = await resp.json();
        if (!data || !Array.isArray(data.tags)) throw new Error("标签库格式异常");
        STATE.data = data;
        return data;
    })();
    try {
        return await STATE.loading;
    } finally {
        STATE.loading = null;
    }
}

function tagIndex(data) {
    if (!data.__index) {
        const map = new Map();
        for (const t of data.tags) map.set(t.t.toLowerCase(), t);
        Object.defineProperty(data, "__index", { value: map, enumerable: false });
    }
    return data.__index;
}

function categoryList(data) {
    if (!data.__cats) {
        Object.defineProperty(data, "__cats", {
            value: [...data.categories], enumerable: false,
        });
    }
    return data.__cats;
}

// ---------------------------------------------------------------------------
// 缩略图开关（图片托管在 jsDelivr 上，离线用户可关掉只看文字）
// ---------------------------------------------------------------------------

const THUMB_KEY = "animansfw.showThumbnails";

function showThumbs() {
    if (STATE.showThumbs === null) {
        let v = true;
        try {
            const raw = localStorage.getItem(THUMB_KEY);
            if (raw === "0") v = false;
        } catch (e) { /* ignore */ }
        STATE.showThumbs = v;
    }
    return STATE.showThumbs;
}

function setShowThumbs(v) {
    STATE.showThumbs = !!v;
    try { localStorage.setItem(THUMB_KEY, v ? "1" : "0"); } catch (e) { /* ignore */ }
}

/**
 * 角色立绘缩略图 URL：`角色名, 作品名` 经 URL 编码后拼到 Animadex thumbs。
 * 实测覆盖率约 93%（抽样 60 个角色命中 56 个），404 时 makeThumb 会自动退回「无图」。
 */
const CHAR_THUMB_BASE = "https://blobs.animadex.net/Outputs/thumbs/{}.webp";

// ---------------------------------------------------------------------------
// 缩略图本地缓存
//
// 面板里的预览图（服装 430 + 姿势 297 + 角色 8017）全在**境外 CDN**，
// 用户反馈「要挂 VPN 才能打开」。改成走后端代理：
//
//   浏览器 → 127.0.0.1/anima_nsfw/thumb?u=<原始URL> → 后端下载一次并落盘
//
// 之后每次都只读本地磁盘，离线也能用。前端只是把 URL 换个前缀，
// 加载失败照样能退回「无图」占位。
// ---------------------------------------------------------------------------

const THUMB_PROXY = "anima_nsfw/thumb";
const THUMB_STATS_URL = "anima_nsfw/thumb_cache/stats";
const THUMB_WARM_URL = "anima_nsfw/thumb_cache/warm";
const THUMB_CLEAR_URL = "anima_nsfw/thumb_cache/clear";

/** 这个 URL 是不是该走本地缓存代理（只代理白名单 CDN，其余原样放行） */
function cacheable(url) {
    const u = String(url || "");
    return u.startsWith("https://cdn.jsdelivr.net/")
        || u.startsWith("https://fastly.jsdelivr.net/")
        || u.startsWith("https://gcore.jsdelivr.net/")
        || u.startsWith("https://testingcf.jsdelivr.net/")
        || u.startsWith("https://blobs.animadex.net/");
}

/** 原始 URL → 本地代理 URL（非 CDN 的原样返回） */
function proxied(url) {
    const u = String(url || "");
    if (!u || !cacheable(u)) return u;
    return `${THUMB_PROXY}?u=${encodeURIComponent(u)}`;
}

function charThumbUrl(name, copyright) {
    const n = String(name || "").trim();
    if (!n) return "";
    const c = String(copyright || "").trim();
    const raw = c ? `${n}, ${c}` : n;
    try {
        return CHAR_THUMB_BASE.replace("{}", encodeURIComponent(raw));
    } catch (e) {
        return "";
    }
}

/**
 * 造一个带占位/失败兜底的缩略图元素。
 *
 * 图片先走**本地缓存代理**（`/anima_nsfw/thumb?u=...`）—— 后端下载一次落盘，
 * 之后只读本地磁盘，不挂 VPN 也能看。代理不可用（老版本后端 / 非 CDN 域名）时
 * 自动退回直连原始 URL。
 */
function makeThumb(url, opts) {
    const { width = 96, height = 150, onFail } = opts || {};
    const box = el("div", {
        width: `${width}px`, height: `${height}px`, flexShrink: "0",
        borderRadius: "6px", overflow: "hidden", background: "#0e0e16",
        border: `1px solid ${THEME.line}`, display: "flex",
        alignItems: "center", justifyContent: "center",
    });
    if (!url) {
        box.appendChild(el("span", { fontSize: "16px", opacity: "0.5" },
            { textContent: "🖼" }));
        return box;
    }
    const img = document.createElement("img");
    const local = proxied(url);
    img.src = local;
    img.loading = "lazy";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    setStyle(img, `width:100%;height:100%;object-fit:cover;display:block`);
    let triedDirect = local === url;
    img.addEventListener("error", () => {
        // 代理失败（缓存目录不可写 / 后端没起来）→ 试一次直连原始 CDN
        if (!triedDirect) {
            triedDirect = true;
            img.src = url;
            return;
        }
        box.innerHTML = "";
        box.appendChild(el("span", { fontSize: "10px", color: THEME.dim, padding: "2px" },
            { textContent: "无图" }));
        onFail?.();
    });
    box.appendChild(img);
    return box;
}

/** 收集当前面板里所有可缓存的缩略图 URL（用于「缓存全部」） */
function collectThumbUrls() {
    const out = new Set();
    for (const p of (STATE.data?.outfit_presets || [])) {
        if (p.preview && cacheable(p.preview)) out.add(p.preview);
    }
    for (const p of (STATE.data?.pose_presets || [])) {
        if (p.preview && cacheable(p.preview)) out.add(p.preview);
    }
    // 角色立绘：只收**当前可见**的（8017 个全下要几百 MB，让用户自己选）
    const chars = STATE.charData?.chars || [];
    for (const c of chars) {
        if (c.hidden) continue;
        const u = charThumbUrl(c.n, c.c);
        if (u) out.add(u);
    }
    return [...out];
}

// ---------------------------------------------------------------------------
// 种子：从本节点的输出连线找下游采样器，把种子写进去
// ---------------------------------------------------------------------------

const SEED_MODES = ["固定（每次同图）", "每次随机", "递增 +1", "递减 -1"];
const SEED_CONTROL = {
    "固定（每次同图）": "fixed",
    "每次随机": "randomize",
    "递增 +1": "increment",
    "递减 -1": "decrement",
};

function randomSeed() {
    // ComfyUI 的 seed 是 64 位整数，但超过 2^53 在 JS 里会失真，取 15 位
    try {
        if (globalThis.crypto?.getRandomValues) {
            const a = new Uint32Array(1);
            crypto.getRandomValues(a);
            return a[0] * 4096 + Math.floor(Math.random() * 4096);
        }
    } catch (e) { /* 落到 Math.random */ }
    return Math.floor(Math.random() * 0x100000000 * 4096);
}

/** 采样器节点上的种子控件名（KSampler / KSamplerAdvanced / RandomNoise 等） */
function seedWidgetOf(target) {
    if (!target?.widgets) return null;
    return target.widgets.find((w) => w && (w.name === "seed" || w.name === "noise_seed"))
        || null;
}

function isSeedWidget(w) {
    return !!w && (w.name === "seed" || w.name === "noise_seed");
}

/** 从本节点出发，沿输出连线收集所有下游节点（广度优先，带深度上限） */
function downstreamNodes(node, maxDepth = 6) {
    const out = [];
    const seen = new Set();
    let frontier = [node];
    for (let depth = 0; depth < maxDepth; depth++) {
        const next = [];
        for (const cur of frontier) {
            for (const slot of cur?.outputs || []) {
                for (const linkId of (slot?.links || [])) {
                    let link = null;
                    try {
                        link = node.graph?.links?.[linkId]
                            || node.graph?.getLink?.(linkId)
                            || null;
                    } catch (e) { /* ignore */ }
                    const targetId = link?.target_id ?? link?.target;
                    if (targetId == null) continue;
                    let target = null;
                    try {
                        target = node.graph?.getNodeById?.(targetId)
                            || node.graph?._nodes_by_id?.[targetId]
                            || null;
                    } catch (e) { /* ignore */ }
                    if (!target || seen.has(target.id)) continue;
                    seen.add(target.id);
                    out.push(target);
                    next.push(target);
                }
            }
        }
        if (!next.length) break;
        frontier = next;
    }
    return out;
}

/**
 * 把种子设置应用到下游采样器。
 * 返回 {count, names} 表示改了几个节点，用来给用户提示。
 */
function applySeedToGraph(node, mode, seed) {
    const targets = downstreamNodes(node).filter((d) => seedWidgetOf(d));
    const names = [];
    for (const d of targets) {
        const w = seedWidgetOf(d);
        if (!w) continue;
        try {
            if (mode === "每次随机") {
                w.value = randomSeed();
            } else if (seed != null) {
                w.value = Number(seed);
            }
            // 自动控制：固定时锁住，随机/递增/递减按模式设置
            const ctl = SEED_CONTROL[mode] || "fixed";
            w.options = w.options || {};
            if ("control_after_generate" in w.options || ctl !== "fixed") {
                w.options.control_after_generate = ctl;
            }
            d.setDirtyCanvas?.(true, true);
            names.push(`${d.type || d.title || "sampler"}#${d.id}`);
        } catch (e) { /* 忽略单个节点失败 */ }
    }
    try { node.graph?.setDirtyCanvas?.(true, true); } catch (e) { /* ignore */ }
    return { count: targets.length, names };
}

// ---------------------------------------------------------------------------
// 随机服装：配饰白名单（保证"搭配合理"）
// ---------------------------------------------------------------------------
// 只从这些里抽 —— 都是我人工过一遍、能和各种底装搭的通用配饰。
// 不按语义槽位分（因为无法可靠判断一套预设已经包含了哪个槽位），
// 而是靠「同色系 + 不在预设里出现过 + 同类不重复」三条来保证不打架。
const RANDOM_ACCESSORIES = [
    // 头饰
    { slot: "head", tag: "hair ribbon" },
    { slot: "head", tag: "hair bow" },
    { slot: "head", tag: "hairband" },
    { slot: "head", tag: "hair ornament" },
    { slot: "head", tag: "hairclip" },
    { slot: "head", tag: "beret" },
    // 颈饰
    { slot: "neck", tag: "choker" },
    { slot: "neck", tag: "lace choker" },
    { slot: "neck", tag: "necklace" },
    { slot: "neck", tag: "neckerchief" },
    { slot: "neck", tag: "neck ribbon" },
    // 手
    { slot: "hand", tag: "gloves" },
    { slot: "hand", tag: "fingerless gloves" },
    { slot: "hand", tag: "wrist cuffs" },
    { slot: "hand", tag: "bracelet" },
    // 腿
    { slot: "leg", tag: "thighhighs" },
    { slot: "leg", tag: "kneehighs" },
    { slot: "leg", tag: "white socks" },
    { slot: "leg", tag: "garter belt" },
    { slot: "leg", tag: "leg ribbon" },
    // 脚
    { slot: "foot", tag: "loafers" },
    { slot: "foot", tag: "mary janes" },
    { slot: "foot", tag: "high heels" },
    { slot: "foot", tag: "boots" },
    { slot: "foot", tag: "sneakers" },
    // 腰
    { slot: "waist", tag: "belt" },
    { slot: "waist", tag: "sash" },
    { slot: "waist", tag: "waist bow" },
    // 脸/眼
    { slot: "face", tag: "glasses" },
    { slot: "face", tag: "sunglasses" },
    { slot: "face", tag: "eyepatch" },
];

/** 色系词。一套预设里出现哪个色系，配饰就优先挑同色系的写法。 */
const COLOR_WORDS = [
    "white", "black", "red", "blue", "green", "yellow", "pink", "purple",
    "brown", "grey", "gray", "orange", "silver", "gold", "aqua", "navy",
];

/** 从预设标签串里提取出现的色系（用于给配饰上色） */
function presetColors(preset) {
    const set = new Set();
    for (const raw of preset.tags || []) {
        const low = String(raw).toLowerCase();
        for (const c of COLOR_WORDS) {
            if (low === c || low.startsWith(c + " ") || low.includes(" " + c + " ")) set.add(c);
        }
    }
    return [...set];
}

/**
 * 给一套预设随机补配饰。返回新的 tags 数组（不改原对象）。
 *
 * 三条约束（缺一不可，否则就会出现"两顶帽子"或"粉发带配黑军装"）：
 *   1. 同类槽位每套最多加 1 个
 *   2. 配饰必须**不在**预设已有的标签里（含同色变体，如已有 black thighhighs 就不再加 thighhighs）
 *   3. 有色系可用时，只在同色系里挑；没有就用无色版本
 */
function withRandomAccessories(preset, count) {
    const presetTags = (preset.tags || []).map((x) => String(x).toLowerCase().trim());
    const have = new Set(presetTags);
    const colors = presetColors(preset);

    // 白名单条目的槽位表（支持带颜色前缀的写法）
    const SLOT_BY_TAG = new Map();
    for (const a of RANDOM_ACCESSORIES) SLOT_BY_TAG.set(a.tag, a.slot);
    const slotOfTag = (raw) => {
        const low = String(raw).toLowerCase().trim();
        if (SLOT_BY_TAG.has(low)) return SLOT_BY_TAG.get(low);
        const parts = low.split(" ");
        for (let i = 1; i < parts.length; i++) {
            const rest = parts.slice(i).join(" ");
            if (SLOT_BY_TAG.has(rest)) return SLOT_BY_TAG.get(rest);
        }
        return null;
    };
    // raw 是不是 base 的写法（含颜色前缀变体）
    const isVariantOf = (raw, base) => {
        const low = String(raw).toLowerCase().trim();
        return low === base || low.endsWith(" " + base);
    };

    // ⚠️ 用**槽位**判断「这套已经有同类配饰了」，不要用子串匹配。
    //    实测两种错法：
    //      · 预设已有 black belt(waist) → 该拦住 waist 的，却因为
    //        字符串里都有 "belt" 把 garter belt(leg) 也拦了（77 次误判）
    //      · 预设已有 white gloves(hand) → 该被拦住的 black fingerless
    //        gloves(hand) 又加了进去（真漏判）
    //    槽位表两个都能判对。
    const usedSlots = new Set();
    for (const h of presetTags) {
        const s = slotOfTag(h);
        if (s) usedSlots.add(s);
    }

    const add = [];
    const pool = RANDOM_ACCESSORIES.slice();
    // 洗牌，避免总是抽到数组前几个
    for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    for (const item of pool) {
        if (add.length >= count) break;
        if (usedSlots.has(item.slot)) continue;          // 同槽位只加一个

        let tag = item.tag;
        if (colors.length) {
            const cands = colors.map((c) => `${c} ${item.tag}`).filter((v) => !have.has(v));
            if (cands.length) tag = cands[Math.floor(Math.random() * cands.length)];
        }
        const low = tag.toLowerCase();
        if (have.has(low)) continue;                     // 一模一样 → 跳过

        // 预设里已有这个东西的其它颜色版本 → 不再加
        //（已有 black thighhighs 就不加 thighhighs / white thighhighs）
        let variant = false;
        for (const h of presetTags) {
            if (isVariantOf(h, item.tag)) { variant = true; break; }
        }
        if (variant) continue;

        have.add(low);
        usedSlots.add(item.slot);
        add.push(tag);
    }
    return (preset.tags || []).concat(add);
}

// ---------------------------------------------------------------------------
// 作品 → 角色索引
// ---------------------------------------------------------------------------
// ⚠️ 性能要点：不要「每个作品都 filter 一遍全部角色」。
// 实测 477 个作品 × 8000 角色 = 380 万次比较，切个分类就 23ms；
// 而且 renderWorkList() 每次都会重跑。这里一次建好 Map，之后 O(1)。
const WORK_INDEX = { key: "", map: null };

function workIndex() {
    const chars = STATE.charData?.chars;
    if (!chars) return null;
    if (WORK_INDEX.map && WORK_INDEX.key === STATE.charData) return WORK_INDEX.map;
    const m = new Map();
    for (const c of chars) {
        const k = c.c || "(未标注作品)";
        let arr = m.get(k);
        if (!arr) { arr = []; m.set(k, arr); }
        arr.push(c);
    }
    // 角色库里已按热度排序，所以各作品内部也是有序的
    WORK_INDEX.key = STATE.charData;
    WORK_INDEX.map = m;
    return m;
}

/** 该作品下的角色（O(1)） */
function workChars(cp) {
    const m = workIndex();
    if (!m) return [];
    return m.get(cp || "(未标注作品)") || [];
}

// ---------------------------------------------------------------------------
// 节点控件处理
// ---------------------------------------------------------------------------

function findWidget(node, name) {
    return node.widgets?.find((w) => w?.name === name) || null;
}

function readTags(node) {
    const w = findWidget(node, "tags");
    const v = w?.value;
    if (typeof v === "string" && v.length) return v;
    return String(w?.value ?? "");
}

// ---------------------------------------------------------------------------
// 自定义库（触发词 / 角色 / 服装 / 姿势）
// 存储：后端 custom_library.json 为准，localStorage 仅作离线兜底
// ---------------------------------------------------------------------------

const CUSTOM_URL = "anima_nsfw/custom";
const CUSTOM_LS_KEY = "animansfw.customLibrary";
const CUSTOM_KINDS = ["trigger", "character", "outfit", "pose"];

const CUSTOM_META = {
    trigger: { zh: "我的触发词", icon: "🔑", color: "#fbbf24",
               hint: "LoRA 触发词、画师名、自己常用的前置词。勾选后会拼到提示词最前面。" },
    character: { zh: "我的角色", icon: "🧑", color: "#38bdf8",
                 hint: "角色名 + 一串标签（发色/瞳色/服装…），一键铺开。可当角色模板用。" },
    outfit: { zh: "我的服装", icon: "👗", color: "#e879f9",
              hint: "自己搭的服装套装，和服装预设一样一键铺开。" },
    pose: { zh: "我的姿势", icon: "🧍", color: "#2dd4bf",
            hint: "自己常用的姿势组合。" },
};

const CUSTOM = { data: null, loading: null, dirty: false };
const CHAR_URL = "anima_nsfw/characters";
const STORY_URL = "anima_nsfw/story";
STATE.charData = null;
STATE.charLoading = null;
// 「存为触发词 / 存为角色」按钮预填编辑器用（模块级，编辑器读完即清）
let PENDING_PREFILL = null;

function emptyCustom() {
    const o = { version: 1 };
    for (const k of CUSTOM_KINDS) o[k] = [];
    return o;
}

/** 读取：优先后端文件，失败则退回 localStorage */
async function loadCustom(force = false) {
    if (CUSTOM.data && !force) return CUSTOM.data;
    if (CUSTOM.loading && !force) return CUSTOM.loading;
    CUSTOM.loading = (async () => {
        try {
            const resp = await fetch(CUSTOM_URL, { cache: "no-cache" });
            if (resp.ok) {
                const j = await resp.json();
                if (j && j.ok && j.data) {
                    CUSTOM.data = normalizeCustom(j.data);
                    try { localStorage.setItem(CUSTOM_LS_KEY, JSON.stringify(CUSTOM.data)); } catch (e) { /* ignore */ }
                    return CUSTOM.data;
                }
            }
        } catch (e) { /* 后端不可用，走兜底 */ }
        try {
            const raw = localStorage.getItem(CUSTOM_LS_KEY);
            CUSTOM.data = normalizeCustom(raw ? JSON.parse(raw) : null);
        } catch (e) {
            CUSTOM.data = emptyCustom();
        }
        return CUSTOM.data;
    })();
    try {
        return await CUSTOM.loading;
    } finally {
        CUSTOM.loading = null;
    }
}

function normalizeCustom(src) {
    const out = emptyCustom();
    if (!src || typeof src !== "object") return out;
    for (const k of CUSTOM_KINDS) {
        const items = Array.isArray(src[k]) ? src[k] : [];
        out[k] = items.filter((x) => x && typeof x === "object" && x.name).map((x) => ({
            id: String(x.id || `${k}_${x.name}`),
            name: String(x.name),
            trigger: String(x.trigger || ""),
            tags: Array.isArray(x.tags) ? x.tags.map(String) : parseTags(x.tags),
            icon: String(x.icon || ""),
            updated: Number(x.updated || 0),
        }));
    }
    return out;
}

/** 写入一条：后端成功就以后端返回为准，失败也要落 localStorage 不掉数据 */
async function saveCustomEntry(kind, payload) {
    const body = { kind, ...payload };
    let saved = null;
    try {
        const resp = await fetch(`${CUSTOM_URL}/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const j = await resp.json();
        if (j && j.ok) {
            CUSTOM.data = normalizeCustom(j.data);
            saved = j.entry;
        } else if (j && j.error) {
            toast(`保存失败：${j.error}`);
            return null;
        }
    } catch (e) {
        // 离线兜底
        const local = CUSTOM.data || emptyCustom();
        const items = local[kind];
        const idx = payload.id ? items.findIndex((x) => x.id === payload.id) : -1;
        const entry = {
            id: payload.id || `${kind}_${Date.now()}`,
            name: payload.name,
            trigger: payload.trigger || "",
            tags: parseTags(payload.tags),
            icon: payload.icon || "",
            updated: Date.now(),
        };
        if (idx >= 0) items[idx] = entry; else items.push(entry);
        CUSTOM.data = local;
        saved = entry;
        toast("后端不可用，已暂存到浏览器（重启后会丢失）");
    }
    try { localStorage.setItem(CUSTOM_LS_KEY, JSON.stringify(CUSTOM.data)); } catch (e) { /* ignore */ }
    return saved;
}

async function deleteCustomEntry(kind, id) {
    try {
        const resp = await fetch(`${CUSTOM_URL}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind, id }),
        });
        const j = await resp.json();
        if (j && j.ok) CUSTOM.data = normalizeCustom(j.data);
    } catch (e) {
        const local = CUSTOM.data || emptyCustom();
        local[kind] = local[kind].filter((x) => x.id !== id);
        CUSTOM.data = local;
    }
    try { localStorage.setItem(CUSTOM_LS_KEY, JSON.stringify(CUSTOM.data)); } catch (e) { /* ignore */ }
}

function toast(msg, ms = 2200) {
    let box = document.querySelector(".animansfw-toast");
    if (!box) {
        box = el("div", {
            position: "fixed", left: "50%", bottom: "42px", transform: "translateX(-50%)",
            zIndex: "100200", padding: "8px 16px", borderRadius: "8px",
            background: "rgba(20,20,30,0.95)", border: `1px solid ${THEME.line}`,
            color: THEME.text, fontSize: "12px", pointerEvents: "none",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
        });
        box.className = "animansfw-toast";
        document.body.appendChild(box);
    }
    box.textContent = msg;
    box.style.opacity = "1";
    clearTimeout(box.__t);
    box.__t = setTimeout(() => { box.style.opacity = "0"; }, ms);
}

function writeTags(node, value) {
    const w = findWidget(node, "tags");
    if (!w) return;
    // 只写值，不触发 widget.callback，避免面板交互被回调打断
    w.value = value;
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    schedulePreview(node);
}

function parseTags(text) {
    return String(text || "")
        .split(/[,，、\n]+/)
        .map((s) => s.trim())
        .filter(Boolean);
}

// 服装预设序列化： "名字[L],,tag1, tag2"   [L] = 锁定角色（后端保持一致）
const PRESET_SEP = ",,";
const LOCK_MARK = "[L]";

function encodeOutfitPreset(preset) {
    if (!preset) return "";
    const head = preset.lock ? `${preset.zh}${LOCK_MARK}` : String(preset.zh || "");
    return `${head}${PRESET_SEP}${(preset.tags || []).join(", ")}`;
}

function decodeOutfitPreset(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;
    let name = "";
    let rest = text;
    if (text.includes(PRESET_SEP)) {
        const idx = text.indexOf(PRESET_SEP);
        name = text.slice(0, idx).trim();
        rest = text.slice(idx + PRESET_SEP.length);
    }
    let lock = name.endsWith(LOCK_MARK);
    if (lock) name = name.slice(0, -LOCK_MARK.length).trim();
    else lock = name.includes("锁定");
    const tags = rest.split(",").map((s) => s.trim()).filter(Boolean);
    return { id: "__from_widget__", zh: name, tags, lock, g: "", r: "soft" };
}

function joinTags(list) {
    return list.join(", ");
}

/**
 * 把控件「藏起来」但不能让它消失。
 *
 * ⚠️ 踩过的坑：早期版本把 widget.type 改成 "hidden"，结果 ComfyUI 生成 prompt 时
 * 会直接跳过该控件，报「缺少必需的输入: tags」。正确做法是保留控件本体
 * （type / value / serialize 全都不动），只让它画不出东西、算不出高度。
 */
function hideWidget(widget) {
    if (!widget || widget.__animansfwHidden) return;
    widget.__animansfwHidden = true;
    // 保留外部记录（排查问题用），但绝不改 type / serialize / serializeValue
    widget.__animansfwOriginalType = widget.type;
    widget.computeSize = () => [0, -4];
    widget.draw = () => {};          // 不绘制 = 视觉上不存在
    const el = widget.element || widget.inputEl;
    if (el) {
        el.style.display = "none";
        el.style.height = "0px";
        el.style.width = "0px";
    }
}

// ---------------------------------------------------------------------------
// 预览（走后端合成，保证与出图一致）
// ---------------------------------------------------------------------------

let previewTimer = 0;
const previewCache = new Map();

function schedulePreview(node, delay = 260) {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
        refreshPreview(node).catch(() => {});
    }, delay);
}

function nodePayload(node) {
    const val = (name) => findWidget(node, name)?.value;
    return {
        tags: readTags(node),
        intensity: val("intensity") || "hard",
        quality_preset: val("quality_preset") || "base（原版 28~32 步）",
        extra_front: val("extra_front") || "",
        extra_tail: val("extra_tail") || "",
        caption_enabled: val("caption_enabled") !== false,
        caption_seed: Number(val("caption_seed") || 0),
        caption_text: val("caption_text") || "",
        sort_tags: val("sort_tags") !== false,
        outfit_preset: decodeOutfitPreset(val("outfit_preset")),
        pose_preset: decodeOutfitPreset(val("pose_preset")),
    };
}

async function refreshPreview(node, force = false) {
    const payload = nodePayload(node);
    const key = JSON.stringify(payload);
    if (!force && previewCache.has(key)) {
        node.__animansfwPreview = previewCache.get(key);
        renderPreviewWidget(node);
        return node.__animansfwPreview;
    }
    const resp = await fetch(PREVIEW_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: key,
    });
    if (!resp.ok) throw new Error(`预览失败: HTTP ${resp.status}`);
    const data = await resp.json();
    previewCache.set(key, data);
    if (previewCache.size > 200) previewCache.clear();
    node.__animansfwPreview = data;
    renderPreviewWidget(node);
    return data;
}

// ---------------------------------------------------------------------------
// 节点上的只读预览
// ---------------------------------------------------------------------------

/**
 * 节点上的只读预览。
 *
 * 兼容性：老版 ComfyUI 前端没有 `node.addDOMWidget()`（或它的 options 不认
 * getHeight/getMinHeight），这里会退回**画布绘制**模式，而不是抛异常
 * —— 之前的版本在这里直接 throw，会把整个 setupBuilder 打断，
 * 结果连「打开面板」按钮都出不来。
 */
function ensurePreviewWidget(node) {
    if (node.__animansfwPreviewWidget || node.__animansfwCanvasPreviewInstalled) {
        return node.__animansfwPreviewWidget || null;
    }
    const canDom = typeof node.addDOMWidget === "function"
        && typeof document !== "undefined"
        && typeof document.createElement === "function";

    if (canDom) {
        try {
            const box = document.createElement("div");
            box.className = "animansfw-node-preview";
            setStyle(box, [
                "box-sizing:border-box",
                "width:100%",
                "padding:4px 6px",
                "font-size:11px",
                "line-height:1.45",
                `color:${THEME.text}`,
                "overflow:hidden",
                "white-space:pre-wrap",
                "word-break:break-word",
                "font-family:ui-monospace,Consolas,monospace",
            ].join(";"));

            const widget = node.addDOMWidget("animansfw_preview", "div", box, {
                serialize: false,
                hideOnZoom: false,
                getMinHeight: () => 84,
                getMaxHeight: () => 240,
                getHeight: () => "124px",
            });
            if (!widget) throw new Error("addDOMWidget 返回空");
            try {
                widget.serialize = false;
                widget.options = widget.options || {};
                widget.options.serialize = false;
            } catch (e) { /* 忽略 */ }
            node.__animansfwPreviewWidget = widget;
            node.__animansfwPreviewEl = box;
            return widget;
        } catch (err) {
            console.warn("[AnimaNSFW] addDOMWidget 不可用，改用画布绘制预览：", err);
        }
    }

    installCanvasPreview(node);
    return null;
}

/** 无 DOM widget 时的兜底：在节点画布上画预览文字（老前端也能用） */
function installCanvasPreview(node) {
    if (node.__animansfwCanvasPreviewInstalled) return;
    node.__animansfwCanvasPreviewInstalled = true;
    node.__animansfwCanvasLines = [];

    const draw = function (ctx) {
        try {
            const lines = node.__animansfwCanvasLines || [];
            if (!lines.length) return;
            const w = (node.size && node.size[0]) || 320;
            ctx.save();
            ctx.font = "11px ui-monospace, Consolas, monospace";
            ctx.textBaseline = "top";
            let y = Math.max(0, (node.size && node.size[1] ? node.size[1] : 200) - 12 * lines.length - 6);
            for (const ln of lines.slice(-8)) {
                ctx.fillStyle = ln.color || THEME.dim;
                ctx.fillText(String(ln.text).slice(0, 60), 8, y);
                y += 12;
            }
            ctx.restore();
        } catch (e) { /* 忽略绘制错误 */ }
    };
    const origBg = node.onDrawBackground;
    node.onDrawBackground = function () {
        try { origBg?.apply(this, arguments); } catch (e) { /* 忽略 */ }
    };
    const origFg = node.onDrawForeground;
    node.onDrawForeground = function () {
        try { origFg?.apply(this, arguments); } catch (e) { /* 忽略 */ }
        draw(arguments[0]);
    };
    renderPreviewWidget(node);   // 先用占位提示
}

function renderPreviewWidget(node) {
    const data = node.__animansfwPreview;

    // 兜底模式：把预览压成几行文字，交给画布绘制
    if (!node.__animansfwPreviewEl) {
        const lines = [];
        if (!data) {
            lines.push({ text: "尚未预览 —— 点「🎛 打开 NSFW 面板」开始选标签", color: THEME.dim });
        } else if (data.error) {
            lines.push({ text: "预览出错: " + data.error, color: THEME.danger });
        } else {
            const ts = data.info?.tags || [];
            lines.push({ text: `正面 ${ts.length} 个标签`, color: THEME.accent });
            for (const t of ts.slice(0, 6)) {
                lines.push({ text: "· " + t, color: THEME.text });
            }
            if (data.info?.caption) {
                lines.push({ text: data.info.caption.slice(0, 58), color: THEME.dim });
            }
        }
        node.__animansfwCanvasLines = lines;
        node.setDirtyCanvas?.(true, true);
        return;
    }

    const el = node.__animansfwPreviewEl;
    if (!data) {
        el.innerHTML = `<span style="color:${THEME.dim}">尚未预览——点上方「🎛 打开 NSFW 面板」开始选标签。</span>`;
        return;
    }
    if (data.error) {
        el.innerHTML = `<span style="color:${THEME.danger}">预览出错: ${escapeHtml(data.error)}</span>`;
        return;
    }
    const tags = (data.info?.tags || []).slice(0, 40);
    const chips = tags.map((t) => {
        const info = STATE.data ? tagIndex(STATE.data).get(String(t).toLowerCase()) : null;
        const color = RATING_COLORS[info?.r || "soft"] || THEME.dim;
        return `<span style="display:inline-block;margin:1px 3px 1px 0;padding:1px 6px;border-radius:8px;` +
            `background:${color}22;color:${color};border:1px solid ${color}55">${escapeHtml(t)}</span>`;
    }).join("");
    const caption = data.info?.caption
        ? `<div style="margin-top:4px;color:${THEME.dim};font-style:italic">${escapeHtml(data.info.caption)}</div>`
        : "";
    el.innerHTML =
        `<div style="margin-bottom:3px"><b style="color:${THEME.accent}">正面</b> ` +
        `<span style="color:${THEME.dim}">${tags.length} 个标签</span></div>` +
        `<div>${chips || `<span style="color:${THEME.dim}">（无标签）</span>`}</div>${caption}`;
}

function escapeHtml(text) {
    return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// 面板（浮层）
// ---------------------------------------------------------------------------

const PANEL_CLASS = "animansfw-overlay";

function openPanel(node) {
    try {
        closePanel();
    } catch (e) { /* 忽略 */ }
    loadTagData().then((data) => {
        let panel;
        try {
            panel = buildPanel(node, data);
        } catch (err) {
            console.error("[AnimaNSFW] 面板构建失败:", err);
            alert(`面板构建失败：${err && err.message ? err.message : err}\n`
                + "请把浏览器控制台（F12）的报错发给作者。");
            return;
        }
        try {
            panel.dataset.overlay = "1";
            panel.className = PANEL_CLASS;
            document.body.appendChild(panel);
        } catch (err) {
            console.error("[AnimaNSFW] 面板挂载失败:", err);
            alert(`面板无法显示：${err && err.message ? err.message : err}`);
        }
    }).catch((err) => {
        alert(`标签库加载失败：${err && err.message ? err.message : err}\n`
            + "检查 /anima_nsfw/tags 是否可访问（反向代理可能剥掉了路径前缀）。");
    });
}

function closePanel() {
    document.querySelectorAll(`.${PANEL_CLASS}`).forEach((el) => el.remove());
}

/**
 * 建 DOM 节点。
 *
 * ⚠️ 性能要点：样式**一次性**写进 `cssText`，不要用 `Object.assign(node.style, {...})`。
 * 后者是每个属性一次 setter —— 面板开一次会建 10 万个节点、几十万次 setter，
 * 在浏览器里会累积成明显的卡顿（实测每个节点平均 5~6 个属性）。
 */
function el(tag, style, props) {
    const node = document.createElement(tag);
    if (style) {
        const parts = [];
        for (const k in style) {
            const v = style[k];
            if (v === undefined || v === null) continue;
            // camelCase -> kebab-case
            const name = k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
            parts.push(`${name}:${v}`);
        }
        if (parts.length) {
            try {
                node.style.cssText = parts.join(";");
            } catch (e) {
                for (const k in style) {
                    if (style[k] !== undefined && style[k] !== null) node.style[k] = style[k];
                }
            }
        }
    }
    if (props) Object.assign(node, props);
    return node;
}

function buildPanel(node, data) {
    const index = tagIndex(data);
    const selected = new Set(parseTags(readTags(node)).map((t) => t.toLowerCase()));
    const order = parseTags(readTags(node));
    let activeCat = "all";
    let query = "";
    let activeIntensity = findWidget(node, "intensity")?.value || "hard";
    let view = "tags";                 // "tags" | "outfits" | "poses" | "mine"
    let showHidden = false;            // 是否显示 hidden 标签（预设补充里的细碎词）
    let outfitQuery = "";
    let outfitGroup = "all";
    let outfitSrc = "all";             // "all" | "curated" | "import"
    let outfitTimer = 0;
    let poseQuery = "";
    let poseGroup = "all";
    let poseTimer = 0;
    let workOpen = "";
    let storyArc = "";          // 当前故事线 id
    let storyCast = "";         // 当前主角 key
    let storyCache = null;      // /anima_nsfw/story 的结果
    let seedMode = findWidget(node, "seed_mode")?.value || SEED_MODES[0];
    let seedValue = Number(findWidget(node, "seed")?.value ?? 1234);
    // SFW 模式：'sfw' | 'nsfw'（与节点上的 mode 控件同步）
    const SFW_MODE_NSFW = "NSFW（不限）";
    const SFW_MODE_SFW = "SFW（全年龄）";
    const SFW_HIDDEN_CATS = (data.sfw && data.sfw.hidden_categories) || [];
    // ⚠️ "nsfw" 里**包含** "sfw" 子串，所以不能直接 includes("sfw")。
    //    先看有没有明确的 NSFW 标记，再看 SFW 标记 —— 与后端 sfw.is_sfw() 保持一致。
    const MODE_NSFW_HINTS = ["nsfw", "not safe", "r18", "r-18", "18+", "成人", "不限"];
    const MODE_SFW_HINTS = ["sfw", "safe", "全年龄", "安全", "一般向"];
    const looksSfw = (v) => {
        const s = String(v || "").trim().toLowerCase();
        if (!s) return false;
        if (MODE_NSFW_HINTS.some((h) => s.includes(h))) return false;
        return MODE_SFW_HINTS.some((h) => s.includes(h));
    };
    let mode = looksSfw(findWidget(node, "mode")?.value) ? "sfw" : "nsfw";
    const isSfw = () => mode === "sfw";
    const sfwBlocked = (tag) => {
        if (!isSfw()) return false;
        const key = String(tag || "").trim().toLowerCase().replace(/_/g, " ");
        return (data.sfw?.block_keys || []).includes(key);
    };
    let charQuery = "";
    let charWork = "all";
    let charTimer = 0;
    let mineKind = "trigger";
    let mineQuery = "";
    let mineTimer = 0;
    let currentPreset = decodeOutfitPreset(findWidget(node, "outfit_preset")?.value);
    let currentPose = decodeOutfitPreset(findWidget(node, "pose_preset")?.value);

    // 保证已选标签在 order 里
    for (const t of order) if (!selected.has(t.toLowerCase())) selected.add(t.toLowerCase());

    const overlay = el("div", {
        position: "fixed",
        inset: "0",
        background: "rgba(0,0,0,0.62)",
        zIndex: "100050",
        display: "flex",
        alignItems: "center",
        // ⚠️ 用 `margin: auto` 居中而**不是** `justifyContent: center`：
        //    可滚动容器里用 justify-content 居中时，内容溢出左边界会**滚不到**
        //    （flexbox 的经典坑：负溢出区不可达）。margin:auto 两边都能滚到。
        backdropFilter: "blur(2px)",
        overflow: "auto",
        padding: "8px",
        boxSizing: "border-box",
    });
    overlay.addEventListener("mousedown", (e) => {
        if (e.target === overlay) commit(true);
    });

    const box = el("div", {
        // 面板宽度跟着视口走（不设最小宽度 —— 设了在极窄视口下 `min(720px, 96vw)`
        // 还是等于视口宽，没意义）。窄的时候由 applyResponsiveLayout() 收缩侧栏，
        // 保住网格的可读宽度，这样才不会"左边的选项显示不完整"。
        width: "min(1180px, 96vw)",
        maxWidth: "none",
        margin: "auto",
        height: "min(820px, 92vh)",
        background: THEME.bg,
        border: `1px solid ${THEME.line}`,
        borderRadius: "10px",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
        color: THEME.text,
        fontFamily: "'Segoe UI','Microsoft YaHei',sans-serif",
    });
    overlay.appendChild(box);

    // ---- 标题栏 ----
    const header = el("div", {
        display: "flex", alignItems: "center", gap: "10px",
        // ⚠️ `flexWrap: "wrap"` + `minWidth: 0` 是**必须的**，这是用户反馈
        //    「左边的选项显示不完整」的**真正根因**。
        //
        //    实测：面板 clientWidth 1178px，但整个面板子树的 scrollWidth 是
        //    **1373px** —— 唯一溢出的就是这个 header（`flexWrap` 默认 nowrap，
        //    里面 10 个按钮 + 搜索框排成一行不肯折行，需要 1373px）。
        //    溢出导致面板内容被居中推左 91px，而面板 `overflow: hidden`
        //    于是把**左边 91px 直接裁掉** —— 侧栏的「全部标签」「露骨 / 强度」
        //    这些就是被这么切掉的，且与视口宽度无关（恒定 91px）。
        //
        //    允许折行后 header 最多占满面板宽度，不再撑宽子树。
        flexWrap: "wrap", minWidth: "0", maxWidth: "100%",
        padding: "10px 14px", borderBottom: `1px solid ${THEME.line}`,
        background: THEME.panel,
    });
    header.appendChild(el("div", {
        fontSize: "15px", fontWeight: "600", color: THEME.accent,
    }, { textContent: "Anima NSFW 面板" }));
    header.appendChild(el("div", {
        fontSize: "11px", color: THEME.dim,
    }, { textContent: "点选标签 → 自动互斥 / 排序 → 生成 Anima 风格提示词" }));

    const spacer = el("div", { flex: "1" });
    header.appendChild(spacer);

    // ---- SFW / NSFW 模式切换（一个节点两用）----
    const modeBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        fontWeight: "600", whiteSpace: "nowrap",
    });
    const paintMode = () => {
        const on = isSfw();
        modeBtn.textContent = on ? "🧸 SFW（全年龄）" : "🔞 NSFW（不限）";
        modeBtn.style.border = `1px solid ${on ? THEME.sfwLine : THEME.nsfwLine}`;
        modeBtn.style.background = on ? THEME.sfwSoft : THEME.nsfwSoft;
        modeBtn.style.color = on ? THEME.sfw : THEME.nsfw;
        modeBtn.title = on
            ? "当前：全年龄。会自动拦下性行为/裸露/体液/束缚/泳装内衣等标签，"
              + "正向追加 rating:safe，负面换成全年龄向安全词。点一下切回 NSFW。"
            : "当前：不限。点一下切到 SFW（全年龄），同一个节点就能两用。";
    };
    const applyMode = (next, silent) => {
        mode = next === "sfw" ? "sfw" : "nsfw";
        const w = findWidget(node, "mode");
        if (w) {
            w.value = isSfw() ? SFW_MODE_SFW : SFW_MODE_NSFW;
            try { w.callback?.(w.value); } catch (e) { /* 忽略 */ }
        }
        paintMode();
        // SFW 下如果当前停在已被收起的分类，回到「全部标签」
        if (isSfw() && SFW_HIDDEN_CATS.includes(activeCat)) activeCat = "all";
        syncCatButtons();
        renderGrid();
        renderSelected();
        if (!silent) schedulePreview(node, 120);
    };
    modeBtn.onclick = () => applyMode(isSfw() ? "nsfw" : "sfw");
    paintMode();
    header.appendChild(modeBtn);

    // 🎲 随机服装：放在头部，任何视图都能点。
    //    原来只在服装视图的工具栏里（头部下方），扫一眼容易漏掉。
    const diceBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.outfit}`, background: "rgba(232,121,249,0.16)",
        color: THEME.outfit, fontWeight: "600", whiteSpace: "nowrap",
    }, {
        textContent: "🎲 随机服装",
        title: "随机抽一套服装。"
            + "在别的视图点它会自动切到服装视图并按当前筛选抽；"
            + "想限定范围就先点分组（例如「封碧蓝·皇家」）再点它。"
            + "要不要补配饰在服装视图顶部那条勾选。",
    });
    diceBtn.onclick = () => {
        if (view !== "outfits") {
            // 从别的视图过来：先回到「全部」筛选，避免上次留下的窄筛选
            // 让人以为"抽不出来"
            outfitSrc = "all";
            outfitGroup = "all";
            outfitQuery = "";
            setView("outfits");
        }
        randomOutfit();     // 内部已负责重画网格 + 把卡片滚进视野
    };
    header.appendChild(diceBtn);

    const outfitBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.accentLine}`, background: THEME.accentSoft,
        color: THEME.accent, fontWeight: "600", whiteSpace: "nowrap",
    }, { textContent: "👗 服装预设" });
    header.appendChild(outfitBtn);

    const poseBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.poseLine}`, background: THEME.poseSoft,
        color: THEME.pose, fontWeight: "600", whiteSpace: "nowrap",
    }, { textContent: "🧍 姿势参考" });
    header.appendChild(poseBtn);

    const thumbBtn = el("button", {
        padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "11px",
        border: `1px solid ${THEME.line}`, background: THEME.panel2,
        color: showThumbs() ? THEME.text : THEME.dim, whiteSpace: "nowrap",
    }, { textContent: showThumbs() ? "🖼 缩略图 开" : "🖼 缩略图 关",
         title: "预设卡片的预览图来自境外 CDN（jsDelivr / animadex）。"
              + "开着会走后端本地缓存：下过一次就只读本地磁盘，之后不挂 VPN 也能看。"
              + "关掉后只看文字，完全离线。" });
    thumbBtn.onclick = () => {
        setShowThumbs(!showThumbs());
        thumbBtn.textContent = showThumbs() ? "🖼 缩略图 开" : "🖼 缩略图 关";
        thumbBtn.style.color = showThumbs() ? THEME.text : THEME.dim;
        renderGrid();
    };
    header.appendChild(thumbBtn);

    // ---- 缩略图缓存：状态 + 一键缓存 ----
    //
    // 为什么需要这个按钮：缓存是"按需填充"的 —— 用户翻到哪张才下哪张。
    // 但首屏能看到的图有限，用户希望"一次全弄好，之后彻底不用管"，
    // 所以给一个显式的批量预热入口。
    const cacheBtn = el("button", {
        padding: "6px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "11px",
        border: `1px solid ${THEME.line}`, background: THEME.panel2,
        color: THEME.dim, whiteSpace: "nowrap",
    }, { textContent: "⬇ 缓存缩略图",
         title: "把服装/姿势/角色预览图抓到本地（服装+姿势约 727 张，"
              + "角色立绘按当前可见的算）。抓完之后不需要 VPN，也完全离线可用。" });
    header.appendChild(cacheBtn);

    /** 拉一次缓存统计，更新按钮文案 */
    async function refreshCacheStats() {
        try {
            const r = await fetch(THUMB_STATS_URL, { cache: "no-store" });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const s = await r.json();
            if (s && typeof s.files === "number") {
                cacheBtn.textContent = s.files
                    ? `⬇ 已缓存 ${s.files} 张 ${s.mb}MB`
                    : "⬇ 缓存缩略图";
                cacheBtn.style.color = s.files ? THEME.text : THEME.dim;
                cacheBtn.title = `缓存目录：${s.dir}\n`
                    + `文件 ${s.files} 个 / ${s.mb} MB\n`
                    + `命中 ${s.hit || 0} 次 · 下载 ${s.download || 0} 次 · 失败 ${s.fail || 0} 次\n`
                    + `点一下把预览图全部抓到本地；Shift+点 清空缓存。`;
                return s;
            }
        } catch (e) { /* 后端老版本没有这个接口，静默忽略 */ }
        return null;
    }

    let cacheBusy = false;
    cacheBtn.onclick = async (e) => {
        if (cacheBusy) return;
        const stats = await refreshCacheStats();
        if (e?.shiftKey) {
            if (!stats?.files) { toast("缓存本来就是空的"); return; }
            if (!confirm(`清空本地缩略图缓存？（${stats.files} 个文件 / ${stats.mb} MB）`)) return;
            try {
                const r = await fetch(THUMB_CLEAR_URL, {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ confirm: true }),
                });
                const s = await r.json();
                toast(`已清空 ${s.removed || 0} 个文件，释放 ${s.freed_mb || 0} MB`);
            } catch (err) {
                toast(`清空失败：${err.message}`);
            }
            refreshCacheStats();
            return;
        }
        // 角色立绘有 8000 多张（几百 MB），不默认全下 —— 先问一下
        const outfit = (STATE.data?.outfit_presets || []).filter((p) => p.preview).length;
        const pose = (STATE.data?.pose_presets || []).filter((p) => p.preview).length;
        const visChars = (STATE.charData?.chars || []).filter((c) => !c.hidden).length;
        const urls = collectThumbUrls();
        if (!urls.length) { toast("没有可缓存的缩略图"); return; }
        const onlyPresets = outfit + pose;
        const msg = `要缓存 ${urls.length} 张预览图：\n\n`
            + `· 服装预设 ${outfit} 张\n· 姿势参考 ${pose} 张\n`
            + `· 角色立绘 ${visChars} 张（可能较大）\n\n`
            + (urls.length > onlyPresets + 200
                ? "点「确定」全部缓存；点「取消」只缓存服装+姿势（更快更省空间）。"
                : "继续？");
        let list = urls;
        if (!confirm(msg)) {
            list = urls.filter((u) => !u.includes("blobs.animadex.net"));
            if (!list.length) { toast("已取消"); return; }
        }
        cacheBusy = true;
        cacheBtn.textContent = `⏳ 正在缓存 0/${list.length}…`;
        cacheBtn.style.color = THEME.warn;
        // 分批请求，边下边报进度（一次全发会阻塞太久看不到反馈）
        const BATCH = 60;
        let done = 0, failed = 0;
        try {
            for (let i = 0; i < list.length; i += BATCH) {
                const chunk = list.slice(i, i + BATCH);
                const r = await fetch(THUMB_WARM_URL, {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ urls: chunk }),
                });
                const s = await r.json();
                done += (s.downloaded || 0) + (s.already || 0);
                failed += s.failed || 0;
                cacheBtn.textContent = `⏳ 正在缓存 ${Math.min(i + BATCH, list.length)}/${list.length}…`;
            }
            toast(`缓存完成：成功 ${done} 张` + (failed ? `，失败 ${failed} 张` : ""));
        } catch (err) {
            toast(`缓存中断：${err.message}`);
        } finally {
            cacheBusy = false;
            cacheBtn.style.color = THEME.dim;
            await refreshCacheStats();
        }
    };

    const mineBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.mineLine}`, background: THEME.mineSoft,
        color: THEME.mine, fontWeight: "600", whiteSpace: "nowrap",
    }, { textContent: "⭐ 我的" });
    header.appendChild(mineBtn);

    const charBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.charLine}`, background: THEME.charSoft,
        color: THEME.char, fontWeight: "600", whiteSpace: "nowrap",
    }, { textContent: "🧑‍🎤 角色" });
    header.appendChild(charBtn);

    const storyBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
        border: `1px solid ${THEME.storyLine}`, background: THEME.storySoft,
        color: THEME.story, fontWeight: "600", whiteSpace: "nowrap",
    }, { textContent: "📖 剧情" });
    header.appendChild(storyBtn);

    const search = el("input", {
        width: "230px", padding: "6px 10px", borderRadius: "6px",
        border: `1px solid ${THEME.line}`, background: THEME.panel2,
        color: THEME.text, fontSize: "12px", outline: "none",
    }, { placeholder: "搜索中文或英文标签…", type: "text" });
    header.appendChild(search);

    const closeBtn = el("button", {
        padding: "6px 12px", borderRadius: "6px", border: `1px solid ${THEME.line}`,
        background: THEME.panel2, color: THEME.text, cursor: "pointer", fontSize: "12px",
    }, { textContent: "关闭 (Esc)" });
    closeBtn.onclick = () => commit(true);
    header.appendChild(closeBtn);
    box.appendChild(header);

    // ---- 强度档 + 分类 侧栏 ----
    const body = el("div", {
        display: "flex", flexDirection: "row",
        flex: "1 1 auto", minHeight: "0",
        width: "100%", maxWidth: "100%", minWidth: "0",
        overflow: "hidden",
    });
    box.appendChild(body);

    const SIDE_W = "var(--animansfw-side-w, 186px)";
    const side = el("div", {
        width: SIDE_W, minWidth: "0", borderRight: `1px solid ${THEME.line}`,
        padding: "10px",
        overflowY: "auto", overflowX: "auto",
        background: THEME.panel, flexShrink: "0",
    });
    body.appendChild(side);

    /**
     * 窄面板时把侧栏从**左侧竖列**改成**顶部横向条**。
     *
     * ## 为什么不用"收缩侧栏宽度"
     *
     * 用户反馈「左边的选项显示不完整」。我原先的做法是按面板宽度把侧栏从
     * 186px 收到 124px 保住网格 —— 但实测在 420px 视口下面板只有 403px，
     * 侧栏 124px 里塞「露骨 / 强度」这种 4 字按钮（每行 2 个 × 48px + gap）
     * 就已经溢出，按钮文字被裁；再窄就完全没法看。
     *
     * 根子上是"横向空间不够"：403px 要同时放侧栏 + 网格，怎么分都不够。
     * 所以改成**换行**：窄的时候侧栏横过来占满整个面板宽度（403px 足够摆下
     * 三档强度 + 分类按钮自动换行），网格在下面拿满宽度。
     *
     * 阈值 640px：宽于它保持原来的左竖列（现在的观感不变）。
     */
    const NARROW_BREAK = 640;

    function applyResponsiveLayout() {
        const w = box.getBoundingClientRect().width || 1180;
        const narrow = w < NARROW_BREAK;
        box.__animansfwNarrow = narrow;

        if (narrow) {
            body.style.flexDirection = "column";
            side.style.width = "100%";
            side.style.maxWidth = "100%";
            side.style.flex = "0 0 auto";
            side.style.maxHeight = "44vh";
            side.style.borderRight = "none";
            side.style.borderBottom = `1px solid ${THEME.line}`;
            // 分类列表在横条里排成多列，别拉成一长条
            if (catList) {
                catList.style.display = "grid";
                catList.style.gridTemplateColumns = "repeat(auto-fill, minmax(104px, 1fr))";
                catList.style.gap = "2px 6px";
            }
            if (workList) workList.style.display = "none";
        } else {
            body.style.flexDirection = "row";
            side.style.width = "186px";
            side.style.maxWidth = "";
            side.style.flex = "0 0 auto";
            side.style.maxHeight = "";
            side.style.borderRight = `1px solid ${THEME.line}`;
            side.style.borderBottom = "none";
            if (catList) {
                catList.style.display = "block";
                catList.style.gridTemplateColumns = "";
                catList.style.gap = "0";
            }
            if (workList) workList.style.display = "";
        }
    }
    // ⚠️ 首次调用**不在这里** —— 本函数引用 catList / workList，
    //    而它们是后面才创建的 `const`（TDZ：提前访问会 ReferenceError）。
    //    统一放在面板构建末尾调用（见 renderActViewRow() 那一带）。
    // 面板宽度会随窗口变化（96vw），要跟着重算。
    // 用 ResizeObserver（Chrome 64+ / ComfyUI 前端都支持），没有就退回 window resize。
    if (typeof ResizeObserver === "function") {
        try {
            const ro = new ResizeObserver(() => applyResponsiveLayout());
            ro.observe(box);
            overlay.__animansfwRO = ro;      // 关面板时断开（见 commit）
        } catch (e) { /* ignore */ }
    }
    // ⚠️ 必须判 `typeof window.addEventListener === "function"`：
    //    离线冒烟测试用的是**自己搭的 DOM 桩**，里面没有 addEventListener，
    //    直接调用会抛 "window.addEventListener is not a function" 把整个面板
    //    构建打断（实测踩过 —— 表现是"点击后面板浮层没出现"）。
    if (typeof window.addEventListener === "function") {
        window.addEventListener("resize", applyResponsiveLayout);
    }

    side.appendChild(el("div", {
        fontSize: "11px", color: THEME.dim, margin: "2px 0 6px",
    }, { textContent: "强度档位（自动全选一套）" }));

    const intensityRow = el("div", { display: "flex", flexWrap: "wrap", gap: "5px", marginBottom: "12px" });
    for (const key of ["soft", "hard", "extreme"]) {
        const meta = data.intensity?.[key] || {};
        const btn = el("button", {
            flex: "1 1 44%", padding: "6px 4px", borderRadius: "6px", cursor: "pointer",
            fontSize: "11px", border: `1px solid ${key === activeIntensity ? THEME.accentLine : THEME.line}`,
            background: key === activeIntensity ? THEME.accentSoft : THEME.panel2,
            color: key === activeIntensity ? THEME.accent : THEME.text,
        }, { textContent: meta.zh || key, title: meta.desc || "" });
        btn.onclick = () => applyIntensity(key);
        btn.dataset.intensity = key;
        intensityRow.appendChild(btn);
    }
    side.appendChild(intensityRow);

    side.appendChild(el("div", {
        fontSize: "11px", color: THEME.dim, margin: "0 0 6px",
    }, { textContent: "分类" }));

    const catList = el("div", { display: "flex", flexDirection: "column", gap: "3px" });
    side.appendChild(catList);
    const catCounts = new Map();
    for (const t of data.tags) catCounts.set(t.c, (catCounts.get(t.c) || 0) + 1);

    const hiddenTotal = new Map();
    for (const t of data.tags) {
        if (t.hidden) hiddenTotal.set(t.c, (hiddenTotal.get(t.c) || 0) + 1);
    }

    const catButtons = [];
    const addCat = (id, label, count, color, warn) => {
        const btn = el("button", {
            display: "flex", justifyContent: "space-between", alignItems: "center",
            gap: "4px",
            padding: "5px 8px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
            border: "1px solid transparent", background: "transparent", color: THEME.text,
            textAlign: "left", minWidth: "0", maxWidth: "100%",
        });
        // ⚠️ 左侧文字必须 `minWidth: 0` + 省略号：
        //    flex 子项默认 `min-width: auto`（= 内容宽度），长标签会把右边的数字
        //    顶出去，窄视口下看起来就是"左边的选项显示不完整"（实测反馈）。
        const left = el("span", {
            color: color || THEME.text,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            minWidth: "0", flex: "1 1 auto",
        }, { textContent: label });
        const right = el("span", {
            fontSize: "10px", color: THEME.dim, flexShrink: "0",
        }, { textContent: String(count) });
        btn.appendChild(left);
        btn.appendChild(right);
        btn.onclick = () => { activeCat = id; workOpen = ""; syncCatButtons(); renderGrid(); };
        btn.__catId = id;
        catList.appendChild(btn);
        catButtons.push(btn);
    };

    // 「全部标签」的口径 = 非 hidden 的标签（与网格一致，不再显示虚高的数字）
    const visibleTotal = data.tags.filter((t) => !t.hidden).length;
    addCat("all", "全部标签", visibleTotal, THEME.accent);
    for (const cat of categoryList(data)) {
        const shown = (catCounts.get(cat.id) || 0) - (hiddenTotal.get(cat.id) || 0);
        const all = catCounts.get(cat.id) || 0;
        // 全是 hidden 的分类不放进侧栏，避免"点进去什么都没有"
        if (all > 0 && shown === 0) continue;
        // 角色由「游戏/作品」展开查看（8000 个平铺太乱），这里不放分类入口
        if (cat.id === "character") continue;
        // SFW 模式下把 性行为/前戏/自慰/体液 收起来，省得误点
        if (isSfw() && SFW_HIDDEN_CATS.includes(cat.id)) continue;
        addCat(cat.id, cat.zh, shown, cat.color, shown < all);
    }

    // ---- 侧栏：作品 → 角色（可展开）--------------------------------------
    const workList = el("div", {
        display: "flex", flexDirection: "column", gap: "2px", marginTop: "6px",
    });
    let workFilter = "";

    // 作品列表一次显示多少个（合并 copies 后有 235 个作品，一屏放不下）
    const WORK_PAGE = 120;
    let workShown = WORK_PAGE;

    // allWorks() 结果缓存：它依赖 STATE.data / STATE.charData，两者在本面板
    // 生命周期内不变，所以算一次就够（原来每次 renderWorkList 都重算）
    let worksCache = null;

    /**
     * 当前 `activeCat` 是否属于「作品」上下文。
     *
     * ⚠️ 不能只查标签库的**版权标签** —— 角色库里还有一些作品没有对应的版权标签
     * （`closers` 就是，21 个角色），点它们时 isWork 会是 false：
     * 网格不铺角色卡（全空）、作品列表也被清空（看起来像"左栏消失了"）。
     * 改成查 `worksCache`（= allWorks()，已经把版权标签和角色库 copies 合并）。
     */
    function inWorkContext() {
        if (activeCat === "copyright") return true;
        const low = String(activeCat).toLowerCase();
        const works = worksCache || (worksCache = allWorks());
        return works.some((w) => String(w.cp).toLowerCase() === low);
    }

    function renderWorkList() {
        workList.innerHTML = "";
        // ⚠️ 不能只判 `activeCat !== "copyright"` —— 点某个作品后 activeCat 会变成
        //    那个作品名（如 "genshin impact"），列表就整个清空，
        //    看起来像「左侧那一栏消失了」（用户报的）。
        if (!inWorkContext()) return;
        if (!STATE.charData) {
            workList.appendChild(el("div", {
                fontSize: "10px", color: THEME.dim, margin: "4px 0",
                textContent: "正在加载角色库…",
            }));
            return;
        }
        const works = worksCache || (worksCache = allWorks());
        const withChars = works.filter((w) => w.n > 0).length;
        workList.appendChild(el("div", {
            fontSize: "10px", color: THEME.dim, margin: "2px 0 3px", lineHeight: "1.4",
            textContent: `${works.length} 个作品（${withChars} 个有角色）`,
        }));
        const search = el("input", {
            width: "100%", padding: "3px 7px", borderRadius: "6px",
            marginBottom: "3px", boxSizing: "border-box",
            border: `1px solid ${THEME.line}`, background: THEME.panel2,
            color: THEME.text, fontSize: "11px", outline: "none",
        }, { placeholder: "找作品…", type: "text", value: workFilter });
        search.addEventListener("input", () => {
            workFilter = search.value;
            const pos = workFilter.length;
            renderWorkList();
            const again = workList.querySelector("input");
            if (again) { again.focus(); again.setSelectionRange(pos, pos); }
        });
        workList.appendChild(search);

        const box = el("div", {
            maxHeight: "40vh", overflowY: "auto", display: "flex",
            flexDirection: "column", gap: "2px",
        });
        workList.appendChild(box);

        const q = workFilter.trim().toLowerCase();
        const pool = q ? works.filter((w) => (w.zh + " " + w.cp).toLowerCase().includes(q))
                       : works;
        // ⚠️ 合并 copies 后作品有 235 个，`.slice(0, 120)` 会**静默**砍掉一半
        //    （「封印者」这种角色数少的正好排在后面，用户就点不到）。
        const shown = q ? pool : pool.slice(0, workShown);
        if (!shown.length) {
            box.appendChild(el("div", { fontSize: "10px", color: THEME.dim },
                { textContent: "没有匹配的作品" }));
        }
        for (const w of shown) {
            const cp = w.cp;
            const kids = workChars(cp);
            const open = workOpen === cp;
            const row = el("div", { display: "flex", alignItems: "center", gap: "3px" });
            const arrow = el("span", {
                width: "12px", fontSize: "9px", color: THEME.dim, cursor: "pointer",
                textAlign: "center", flexShrink: "0",
            }, { textContent: kids.length ? (open ? "▼" : "▶") : "·" });
            const b = el("button", {
                flex: "1", display: "flex", justifyContent: "space-between",
                alignItems: "center", padding: "3px 6px", borderRadius: "6px",
                cursor: "pointer", fontSize: "11.5px", overflow: "hidden",
                border: `1px solid ${open ? THEME.charLine : "transparent"}`,
                background: open ? THEME.charSoft : "transparent",
                color: open ? THEME.char : THEME.text, textAlign: "left",
            });
            b.appendChild(el("span", {
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: w.zh }));
            b.appendChild(el("span", {
                fontSize: "9px", color: THEME.dim, flexShrink: "0", marginLeft: "4px",
            }, { textContent: w.n ? String(w.n) : "" }));
            b.title = `${w.zh} (${cp})${w.n ? ` · ${w.n} 个角色` : ""}`;
            b.onclick = () => {
                activeCat = cp;
                workOpen = open ? "" : cp;
                syncCatButtons();
                renderGrid();
            };
            arrow.onclick = (e) => {
                e.stopPropagation();
                if (!kids.length) return;
                workOpen = open ? "" : cp;
                syncCatButtons();
                renderGrid();
            };
            row.appendChild(arrow);
            row.appendChild(b);
            box.appendChild(row);

            if (open && kids.length) {
                const subBox = el("div", {
                    margin: "1px 0 4px 15px", maxHeight: "26vh", overflowY: "auto",
                    display: "flex", flexDirection: "column", gap: "1px",
                });
                for (const c of kids.slice(0, CARD_LIMIT)) {
                    const on = selected.has(c.n.toLowerCase());
                    const cb = el("button", {
                        padding: "2px 6px", borderRadius: "5px", cursor: "pointer",
                        fontSize: "11px", textAlign: "left",
                        border: `1px solid ${on ? THEME.char : "transparent"}`,
                        background: on ? THEME.charSoft : "transparent",
                        color: on ? THEME.char : THEME.dim,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }, { textContent: c.z || c.n, title: `${c.z || ""} ${c.n}` });
                    cb.onclick = (e) => {
                        e.stopPropagation();
                        if (!selected.has(c.n.toLowerCase())) select(c.n);
                        syncCatButtons();
                        sync();
                    };
                    subBox.appendChild(cb);
                }
                if (kids.length > CARD_LIMIT) {
                    subBox.appendChild(el("div", {
                        fontSize: "10px", color: THEME.dim,
                        textContent: `还有 ${kids.length - CARD_LIMIT} 个，用搜索框找`,
                    }));
                }
                box.appendChild(subBox);
            }
        }
        if (!q && pool.length > shown.length) {
            // ⚠️ 合并角色库的 copies 后有 235 个作品，原来只显示前 120 并静默截断 ——
            //    角色数少的作品（如「封印者」21 个）正好排在后面，用户就点不到。
            //    给一个明确的「显示更多」，别让人以为"就这么多"。
            const moreBtn = el("button", {
                marginTop: "4px", width: "100%", padding: "4px 8px",
                borderRadius: "6px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${THEME.line}`, background: THEME.panel2,
                color: THEME.text,
            }, {
                textContent: `显示更多（还有 ${pool.length - shown.length} 个作品）`,
            });
            moreBtn.onclick = () => {
                workShown += WORK_PAGE;
                renderWorkList();
            };
            workList.appendChild(moreBtn);
        } else if (!q && pool.length > WORK_PAGE) {
            const lessBtn = el("button", {
                marginTop: "4px", width: "100%", padding: "4px 8px",
                borderRadius: "6px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${THEME.line}`, background: THEME.panel2,
                color: THEME.dim,
            }, { textContent: "收起到前 120 个" });
            lessBtn.onclick = () => {
                workShown = WORK_PAGE;
                renderWorkList();
            };
            workList.appendChild(lessBtn);
        }
    }

    // ---- 种子控制行 ----
    const seedRow = el("div", {
        display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap",
        margin: "2px 0 8px", padding: "6px 8px", borderRadius: "7px",
        border: `1px solid ${THEME.line}`, background: THEME.panel2,
    });
    seedRow.appendChild(el("span", { fontSize: "11px", color: THEME.dim, flexShrink: "0" },
        { textContent: "🎲 种子" }));

    const seedSel = el("select", {
        padding: "3px 6px", borderRadius: "6px", fontSize: "11px", cursor: "pointer",
        border: `1px solid ${THEME.line}`, background: THEME.panel, color: THEME.text,
        flex: "1 1 120px", minWidth: "110px",
    });
    for (const m of SEED_MODES) {
        const opt = el("option", {}, { textContent: m });
        opt.value = m;
        if (m === seedMode) opt.selected = true;
        seedSel.appendChild(opt);
    }
    seedRow.appendChild(seedSel);

    const seedInput = el("input", {
        width: "96px", padding: "3px 6px", borderRadius: "6px", fontSize: "11px",
        border: `1px solid ${THEME.line}`, background: THEME.panel, color: THEME.text,
        outline: "none", fontFamily: "ui-monospace,Consolas,monospace",
    }, { type: "number", value: String(seedValue), min: "0", step: "1" });
    seedRow.appendChild(seedInput);

    const seedDice = el("button", {
        padding: "3px 9px", borderRadius: "6px", cursor: "pointer", fontSize: "11px",
        border: `1px solid ${THEME.accentLine}`, background: THEME.accentSoft,
        color: THEME.accent, flexShrink: "0",
    }, { textContent: "🎲 抽一个", title: "随机生成一个种子（并切到「每次随机」）" });
    seedRow.appendChild(seedDice);

    const seedHint = el("span", {
        fontSize: "10px", color: THEME.dim, flex: "1 1 100%", lineHeight: "1.4",
    });
    seedRow.appendChild(seedHint);

    function syncSeedHint() {
        const n = downstreamNodes(node).filter((d) => seedWidgetOf(d)).length;
        const parts = [];
        if (seedMode === "固定（每次同图）") {
            parts.push(`固定 seed = ${seedValue}，每次生成同一张图`);
        } else if (seedMode === "每次随机") {
            parts.push("每次生成都换图（采样器设为 randomize）");
        } else {
            parts.push(`每生成一次自动${seedMode === "递增 +1" ? "加 1" : "减 1"}`);
        }
        parts.push(n ? `将写入 ${n} 个采样器` : "未连到采样器（不生效）");
        seedHint.textContent = parts.join(" · ");
    }
    syncSeedHint();

    seedSel.onchange = () => {
        seedMode = seedSel.value;
        if (seedMode === "每次随机") {
            seedValue = randomSeed();
            seedInput.value = String(seedValue);
        }
        syncSeedHint();
    };
    seedInput.onchange = () => {
        const v = Number(seedInput.value || 0);
        seedValue = Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0;
        seedInput.value = String(seedValue);
        syncSeedHint();
    };
    seedDice.onclick = () => {
        seedMode = "每次随机";
        seedSel.value = seedMode;
        seedValue = randomSeed();
        seedInput.value = String(seedValue);
        syncSeedHint();
    };

    side.appendChild(seedRow);

    // ---- 隐藏标签开关 ----
    const hiddenRow = el("div", {
        marginTop: "10px", paddingTop: "8px", borderTop: `1px solid ${THEME.line}`,
        display: "flex", alignItems: "center", gap: "6px", cursor: "pointer",
        fontSize: "11px", color: THEME.dim,
    });
    const hiddenBox = el("input", { margin: "0", cursor: "pointer" }, { type: "checkbox" });
    hiddenBox.checked = showHidden;
    hiddenRow.appendChild(hiddenBox);
    hiddenRow.appendChild(el("span", {}, {
        textContent: `显示隐藏标签 (${hiddenTotal.size ? [...hiddenTotal.values()].reduce((a, b) => a + b, 0) : 0})`,
    }));
    hiddenRow.onclick = (e) => {
        if (e.target !== hiddenBox) hiddenBox.checked = !hiddenBox.checked;
        showHidden = hiddenBox.checked;
        renderGrid();
    };
    hiddenRow.title = "预设补充里的细碎单品词（发色/饰品/手持物等）。"
        + "默认不显示以免淹掉常用标签；勾上后它们在各自分类里都能看到。";
    side.appendChild(workList);
    side.appendChild(hiddenRow);
    function syncCatButtons() {
        for (const btn of catButtons) {
            const on = btn.__catId === activeCat;
            btn.style.background = on ? THEME.accentSoft : "transparent";
            btn.style.borderColor = on ? THEME.accentLine : "transparent";
            // SFW 模式下把 性行为/前戏/自慰/体液 四个分类整条收起来。
            // 分类按钮是启动时一次性建好的，这里每次同步时按当前模式重新算显隐，
            // 否则切换模式后侧栏不会变。
            if (btn.__catId === "all") continue;
            const hide = isSfw() && SFW_HIDDEN_CATS.includes(btn.__catId);
            btn.style.display = hide ? "none" : "flex";
        }
        renderWorkList();
    }

    // ---- 主区：标签网格 ----
    const main = el("div", { flex: "1", display: "flex", flexDirection: "column", minWidth: "0" });
    body.appendChild(main);

    const selectedBar = el("div", {
        padding: "8px 12px", borderBottom: `1px solid ${THEME.line}`,
        display: "flex", flexWrap: "wrap", gap: "4px", alignItems: "center",
        minHeight: "40px", maxHeight: "108px", overflowY: "auto", background: THEME.panel2,
    });
    main.appendChild(selectedBar);

    const grid = el("div", {
        flex: "1", overflowY: "auto", padding: "10px 12px",
        display: "flex", flexWrap: "wrap", gap: "6px", alignContent: "flex-start",
    });
    main.appendChild(grid);

    // ---- 当前服装预设提示条 ----
    const outfitRow = el("div", {
        display: "none", padding: "5px 12px", fontSize: "11px", gap: "6px",
        alignItems: "center", flexWrap: "wrap",
        borderBottom: `1px solid ${THEME.line}`, background: "rgba(232,121,249,0.10)",
        color: THEME.outfit,
    });
    main.insertBefore(outfitRow, selectedBar);

    // ---- 服装预设：分组条（只在预设视图显示）----
    const outfitBar = el("div", {
        display: "none", padding: "6px 10px", gap: "5px", alignItems: "center",
        flexWrap: "wrap", borderBottom: `1px solid ${THEME.line}`, background: THEME.panel,
    });
    main.insertBefore(outfitBar, selectedBar);

    // ---- 随机服装栏（只在服装视图显示，紧跟在分组条下面）----
    const randomBar = el("div", {
        display: "none", padding: "6px 10px", gap: "10px", alignItems: "center",
        flexWrap: "wrap", borderBottom: `1px solid ${THEME.line}`,
        background: THEME.panel,
    });
    main.insertBefore(randomBar, selectedBar);

    // ---- 姿势参考：分组条（只在姿势视图显示）----
    const poseBar = el("div", {
        display: "none", padding: "6px 10px", gap: "5px", alignItems: "center",
        flexWrap: "wrap", borderBottom: `1px solid ${THEME.line}`, background: THEME.panel,
    });
    main.insertBefore(poseBar, selectedBar);

    // ---- 剧情视图：主角/故事线/分镜条（只在剧情视图显示）----
    const storyBar = el("div", {
        display: "none", padding: "8px 10px", gap: "6px", alignItems: "flex-start",
        flexDirection: "column", borderBottom: `1px solid ${THEME.line}`,
        background: THEME.panel, maxHeight: "42vh", overflowY: "auto",
    });
    main.insertBefore(storyBar, selectedBar);

    // ---- 角色浏览器：作品筛选条（只在角色视图显示）----
    const charBar = el("div", {
        display: "none", padding: "6px 10px", gap: "5px", alignItems: "center",
        flexWrap: "wrap", borderBottom: `1px solid ${THEME.line}`, background: THEME.panel,
    });
    main.insertBefore(charBar, selectedBar);

    // ---- 我的库：类型条 + 操作（只在「我的」视图显示）----
    const mineBar = el("div", {
        display: "none", padding: "6px 10px", gap: "5px", alignItems: "center",
        flexWrap: "wrap", borderBottom: `1px solid ${THEME.line}`, background: THEME.panel,
    });
    main.insertBefore(mineBar, selectedBar);

    // ---- 动作 / 视角 快速选择条 ----
    //
    // 用户要的是「动作」「视角」能单独当选项选，而不用去侧栏分类里翻。
    //
    // 为什么每个组只给「常用前几个」而不是全部：`act_pose` 有 27 个、
    // `view_angle` 有 13 个，全铺开要占三四行、把网格挤没。所以这里放最常用的，
    // 完整清单在侧栏「动作/姿势」「镜头/视角」两个分类里（点「更多」跳过去）。
    //
    // 组内互斥交给 select() —— 它本来就会清掉同组的其它标签；
    // 跨组（例如「坐着」+「翘腿」+「侧面」）可以叠加。
    const QUICK_ACTION = [
        ["stand", "站立", "standing"],
        ["sit", "坐着", "sitting"],
        ["lie", "躺下", "lying"],
        ["face_down", "趴着", "lying on stomach"],
        ["side_lie", "侧躺", "lying on side"],
        ["kneel", "跪姿", "kneeling"],
        ["squat", "蹲姿", "squatting"],
        ["crouch", "蹲伏", "crouching"],
        ["bent", "弯腰前倾", "bent over"],
        ["allfours", "四肢着地", "on all fours"],
        ["walk", "行走", "walking"],
        ["run", "奔跑", "running"],
        ["jump", "跳跃", "jumping"],
        ["lean_fwd", "身体前倾", "leaning forward"],
        ["lean_back", "身体后仰", "leaning back"],
    ];
    // 腿部/手臂：不互斥，可以和主姿态叠加
    const QUICK_LIMB = [
        ["crossed", "翘腿", "crossed legs", "act_legs"],
        ["knees_up", "屈膝", "knees up", "act_legs"],
        ["legs_open", "张腿", "spread legs", "act_legs"],
        ["legs_up", "抬腿", "legs up", "act_legs"],
        ["tiptoes", "踮脚", "tiptoes", "act_legs"],
        ["arms_head", "抱头", "arms behind head", "act_arms"],
        ["arms_back", "双手背后", "arms behind back", "act_arms"],
        ["cheek", "手托腮", "hand on own cheek", "act_arms"],
        ["hip", "手扶腰", "hand on own hip", "act_arms"],
        ["cover_mouth", "捂嘴", "covering mouth", "act_arms"],
    ];
    const QUICK_VIEW = [
        ["front", "正面", "front view", "view_angle"],
        ["three_q", "四分之三侧", "three-quarter view", "view_angle"],
        ["side", "侧面", "from side", "view_angle"],
        ["above", "俯视", "from above", "view_angle"],
        ["below", "仰视", "from below", "view_angle"],
        ["high", "高角度", "high angle", "view_angle"],
        ["low", "低角度", "low angle", "view_angle"],
        ["dutch", "荷兰角", "dutch angle", "view_angle"],
        ["topdown", "正上方", "top-down view", "view_angle"],
        ["pov", "主观视角", "pov", "view_pov"],
        ["behind", "背面", "from behind", "view_dir"],
        ["look", "看向观众", "looking at viewer", "view_dir"],
        ["away", "视线移开", "looking away", "view_dir"],
        ["face_away", "背对", "facing away", "view_dir"],
        ["closeup", "特写", "close-up", "view_framing"],
        ["upper", "上半身", "upper body", "view_framing"],
        ["full", "全身", "full body", "view_framing"],
        ["wide", "远景", "wide shot", "view_framing"],
    ];

    const actViewRow = el("div", {
        display: "flex", flexDirection: "column", gap: "3px",
        padding: "6px 10px", borderBottom: `1px solid ${THEME.line}`,
        background: THEME.panel, maxHeight: "132px", overflowY: "auto",
    });
    main.insertBefore(actViewRow, selectedBar);

    /** 画一行「标签 + 若干 chip」；组内互斥由 select() 负责 */
    function quickRow(label, items, color, groupOf) {
        const row = el("div", {
            display: "flex", flexWrap: "wrap", gap: "3px", alignItems: "center",
        });
        row.appendChild(el("span", {
            fontSize: "10.5px", color: THEME.dim, flexShrink: "0",
            width: "34px", textAlign: "right", marginRight: "2px",
        }, { textContent: label }));
        for (const it of items) {
            const [key, zh, tag] = it;
            const explicit = it[3] || null;
            const info = tagInfo(tag);
            const g = explicit || info?.g || null;
            const on = selected.has(tag.toLowerCase());
            const b = el("button", {
                padding: "1.5px 7px", borderRadius: "7px", cursor: "pointer",
                fontSize: "10.5px", lineHeight: "1.5",
                border: `1px solid ${on ? color : THEME.line}`,
                background: on ? `${color}2e` : THEME.panel2,
                color: on ? color : THEME.text,
                whiteSpace: "nowrap",
            }, { textContent: zh, title: `${tag}${g ? `  ·  组 ${g}（同组互斥）` : ""}` });
            b.__qTag = tag;
            b.__qGroup = g;
            b.__qKey = key;
            b.onclick = () => {
                if (!selected.has(tag.toLowerCase())) {
                    // 先清掉同组其它（保险起见；select() 也会做一遍）
                    if (g) {
                        for (const k of [...order]) {
                            const ki = tagInfo(k);
                            if (ki?.g === g && k.toLowerCase() !== tag.toLowerCase()) {
                                selected.delete(k.toLowerCase());
                                const idx = order.indexOf(k);
                                if (idx >= 0) order.splice(idx, 1);
                            }
                        }
                    }
                    select(tag);
                } else {
                    select(tag);
                }
                sync();
            };
            row.appendChild(b);
        }
        // 「更多」直接跳侧栏分类
        const more = el("button", {
            padding: "1.5px 7px", borderRadius: "7px", cursor: "pointer",
            fontSize: "10.5px", lineHeight: "1.5", marginLeft: "2px",
            border: `1px dashed ${THEME.line}`, background: "transparent",
            color: THEME.dim, whiteSpace: "nowrap",
        }, { textContent: "更多…", title: "跳到侧栏的完整分类" });
        more.onclick = () => {
            activeCat = groupOf;
            workOpen = "";
            syncCatButtons();
            renderGrid();
        };
        row.appendChild(more);
        return row;
    }

    /** chip 的选中态要跟着 selected 变（点标签卡、清空、预设写入都要同步） */
    function paintQuickRow() {
        for (const b of actViewRow.querySelectorAll("button")) {
            if (!b.__qTag) continue;
            const color = b.__qColor || THEME.accent;
            const on = selected.has(b.__qTag.toLowerCase());
            b.style.border = `1px solid ${on ? color : THEME.line}`;
            b.style.background = on ? `${color}2e` : THEME.panel2;
            b.style.color = on ? color : THEME.text;
        }
    }

    function renderActViewRow() {
        actViewRow.innerHTML = "";
        const action = quickRow("动作", QUICK_ACTION, "#4ade80", "action");
        const limb = quickRow("腿/手", QUICK_LIMB, "#86efac", "action");
        const view = quickRow("视角", QUICK_VIEW, "#5eead4", "view");
        for (const [row, color] of [[action, "#4ade80"], [limb, "#86efac"], [view, "#5eead4"]]) {
            for (const b of row.querySelectorAll("button")) b.__qColor = color;
            actViewRow.appendChild(row);
        }
        paintQuickRow();
    }

    // ---- 底部：预览 + 操作 ----
    const footer = el("div", {
        borderTop: `1px solid ${THEME.line}`, background: THEME.panel,
        padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px",
    });
    box.appendChild(footer);

    const previewBox = el("div", {
        background: THEME.panel2, border: `1px solid ${THEME.line}`, borderRadius: "6px",
        padding: "8px 10px", fontSize: "12px", lineHeight: "1.5", maxHeight: "140px",
        overflowY: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
        fontFamily: "ui-monospace,Consolas,monospace", color: THEME.text,
    });
    footer.appendChild(previewBox);

    const actions = el("div", { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" });
    footer.appendChild(actions);

    const stats = el("div", { fontSize: "11px", color: THEME.dim, flex: "1" });
    actions.appendChild(stats);

    const mkBtn = (label, bg, fg) => el("button", {
        padding: "7px 14px", borderRadius: "6px", border: "none", cursor: "pointer",
        fontSize: "12px", background: bg, color: fg, fontWeight: "600",
    }, { textContent: label });

    const clearBtn = mkBtn("清空", THEME.panel2, THEME.text);
    clearBtn.style.border = `1px solid ${THEME.line}`;
    clearBtn.onclick = () => { selected.clear(); order.length = 0; sync(); };
    actions.appendChild(clearBtn);

    const copyBtn = mkBtn("复制提示词", THEME.panel2, THEME.text);
    copyBtn.style.border = `1px solid ${THEME.line}`;
    copyBtn.onclick = async () => {
        const done = await copyText(previewBox.dataset.prompt || "");
        copyBtn.textContent = done ? "已复制 ✓" : "复制失败";
        setTimeout(() => { copyBtn.textContent = "复制提示词"; }, 1200);
    };
    actions.appendChild(copyBtn);

    const applyBtn = mkBtn("应用并关闭", THEME.accent, "#1a0a12");
    applyBtn.onclick = () => commit(true);
    actions.appendChild(applyBtn);

    // ---- 逻辑 ----

    function tagInfo(tag) {
        return index.get(String(tag).toLowerCase()) || null;
    }

    /**
     * 选中/取消一个标签。
     *
     * 返回值：本次**受影响的标签键**（自己 + 互斥组里被顶掉的）。
     * `sync()` 拿它做局部重绘 —— 只改这几张卡片的样式，不重建整个网格。
     */
    function select(tag) {
        const key = tag.toLowerCase();
        const info = tagInfo(tag);
        if (selected.has(key)) {
            selected.delete(key);
            const i = order.findIndex((t) => t.toLowerCase() === key);
            if (i >= 0) order.splice(i, 1);
            return [key];
        }
        const touched = [key];
        // 同组互斥
        if (info?.g) {
            for (const other of [...order]) {
                const oi = tagInfo(other);
                if (oi?.g === info.g && other.toLowerCase() !== key) {
                    selected.delete(other.toLowerCase());
                    const i = order.indexOf(other);
                    if (i >= 0) order.splice(i, 1);
                    touched.push(other.toLowerCase());
                }
            }
        }
        selected.add(key);
        order.push(tag);
        return touched;
    }

    function applyIntensity(level) {
        activeIntensity = level;
        const w = findWidget(node, "intensity");
        if (w) w.value = level;
        for (const btn of intensityRow.children) {
            const on = btn.dataset.intensity === level;
            btn.style.borderColor = on ? THEME.accentLine : THEME.line;
            btn.style.background = on ? THEME.accentSoft : THEME.panel2;
            btn.style.color = on ? THEME.accent : THEME.text;
        }
        const ceiling = { soft: 1, hard: 2, extreme: 3 }[level] || 2;
        // 去掉超档标签
        for (const tag of [...order]) {
            const info = tagInfo(tag);
            if (info && Number(info.lvl) > ceiling) {
                selected.delete(tag.toLowerCase());
                order.splice(order.indexOf(tag), 1);
            }
        }
        // 补齐该档位的基础套件（只补一次，不覆盖用户选择）
        const bundle = INTENSITY_BUNDLES[level] || [];
        for (const tag of bundle) {
            const info = tagInfo(tag);
            if (!info) continue;
            if (Number(info.lvl) > ceiling) continue;
            if (!selected.has(tag.toLowerCase())) select(tag);
        }
        sync();
    }

    // 预览请求防抖：连续点标签时只发最后一次（原来每点一次就 POST 一次）
    let syncPreviewTimer = 0;
    let syncPreviewSeq = 0;

    async function fetchPreviewText() {
        const seq = ++syncPreviewSeq;
        try {
            const resp = await fetch(PREVIEW_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(nodePayload(node)),
            });
            const data = await resp.json();
            if (seq !== syncPreviewSeq) return;      // 已经有更新的请求了，丢弃
            previewBox.textContent = data.positive || "";
            previewBox.dataset.prompt = data.positive || "";
            node.__animansfwPreview = data;
            renderPreviewWidget(node);
        } catch (e) {
            if (seq !== syncPreviewSeq) return;
            previewBox.textContent = `预览失败: ${e.message}`;
        }
    }

    async function sync(previewNow, touched) {
        const tagStr = joinTags(order);
        writeTagsSilently(node, tagStr);
        renderSelected();
        // 动作/视角快速条的选中态要跟着走 —— 点标签卡、清空、套用预设都会改 selected，
        // 不重绘的话 chip 的亮/暗会和实际选中不一致。
        try { paintQuickRow(); } catch (e) { /* 面板可能还没建好 */ }
        // 只重画受影响的卡片（被点的 + 互斥组里被顶掉的），不重建整个网格。
        // 传了 touched 就局部重绘；分类切换 / 搜索等场景没有 touched，走整体重建。
        if (touched && touched.length && tagCards.size && !query.trim()) {
            for (const key of touched) {
                const hit = tagCards.get(key);
                if (hit) paintTagCard(hit.card, hit.info);
            }
        } else {
            renderGrid();
        }
        stats.textContent = `已选 ${order.length} 个标签 · ${tagStr.length} 字符`;
        // 防抖 220ms：连点标签时不再每次都打后端
        clearTimeout(syncPreviewTimer);
        if (previewNow) {
            await fetchPreviewText();
        } else {
            syncPreviewTimer = setTimeout(fetchPreviewText, 220);
        }
    }

    function writeTagsSilently(target, value) {
        const w = findWidget(target, "tags");
        if (!w) return;
        w.value = value;
        target.setDirtyCanvas?.(true, true);
    }

    // ------------------------------------------------------------------
    // 服装预设
    // ------------------------------------------------------------------

    function writePresetSilently(target, value) {
        const w = findWidget(target, "outfit_preset");
        if (!w) return;
        w.value = value;
        target.setDirtyCanvas?.(true, true);
    }

    function presetCount() {
        return (STATE.data?.outfit_presets || []).length;
    }

    function applyPresetOutfit(preset) {
        if (!preset) return;
        // 留一条记录：测试与调试用（node.__animansfwLastPreset.zh / .g / .id）
        try {
            node.__animansfwLastPreset = {
                id: preset.id, zh: preset.zh, g: preset.g, src: preset.src,
                lock: !!preset.lock, nTags: (preset.tags || []).length,
                at: Date.now(),
            };
        } catch (e) { /* 忽略 */ }
        // 同一条再点一次 = 取消
        if (currentPreset && currentPreset.id === preset.id) {
            currentPreset = null;
            writePresetSilently(node, "");
            renderOutfitRow();
            sync();
            return;
        }
        currentPreset = preset;
        writePresetSilently(node, encodeOutfitPreset(preset));
        // 服装本体标签与预设自身互斥：先把用户已选的 outfit_base 清掉，避免打架
        const baseGroup = new Set();
        for (const t of preset.tags) {
            const info = tagInfo(t);
            if (info?.g) baseGroup.add(info.g);
        }
        for (const tag of [...order]) {
            const info = tagInfo(tag);
            if (info?.g && baseGroup.has(info.g)) {
                selected.delete(tag.toLowerCase());
                order.splice(order.indexOf(tag), 1);
            }
        }
        renderOutfitRow();
        sync();
    }

    function renderOutfitRow() {
        outfitRow.innerHTML = "";
        const parts = [];
        if (currentPreset) {
            parts.push({ label: "服装预设", value: currentPreset, color: THEME.outfit,
                         lock: currentPreset.lock, onCancel: () => applyPresetOutfit(currentPreset) });
        }
        if (currentPose) {
            parts.push({ label: "姿势参考", value: currentPose, color: THEME.pose,
                         lock: false, onCancel: () => applyPosePreset(currentPose) });
        }
        if (!parts.length) {
            outfitRow.style.display = "none";
            return;
        }
        outfitRow.style.display = "flex";
        outfitRow.innerHTML = "";
        for (const p of parts) {
            const seg = el("span", {
                display: "inline-flex", alignItems: "center", gap: "5px",
                marginRight: "12px",
            });
            seg.appendChild(el("span", { fontWeight: "600", color: p.color },
                { textContent: `${p.lock ? "🔒 " : ""}${p.label}：${p.value.zh}` }));
            seg.appendChild(el("span", { color: THEME.dim, fontSize: "10px" },
                { textContent: `${p.value.tags.length} 个标签` }));
            const rm = el("button", {
                padding: "1px 7px", borderRadius: "9px", cursor: "pointer",
                border: `1px solid ${p.color}66`, background: "transparent",
                color: p.color, fontSize: "10px",
            }, { textContent: "取消" });
            rm.onclick = p.onCancel;
            seg.appendChild(rm);
            outfitRow.appendChild(seg);
        }
    }

    function setView(next) {
        view = next;
        const isOutfit = view === "outfits";
        const isPose = view === "poses";
        const isMine = view === "mine";
        outfitBtn.style.background = isOutfit ? THEME.outfit : THEME.accentSoft;
        outfitBtn.style.color = isOutfit ? "#1a0a12" : THEME.accent;
        outfitBtn.textContent = isOutfit ? "🏷 返回标签" : `👗 服装预设 (${presetCount()})`;
        poseBtn.style.background = isPose ? THEME.pose : THEME.poseSoft;
        poseBtn.style.color = isPose ? "#0a1520" : THEME.pose;
        poseBtn.textContent = isPose ? "🏷 返回标签" : `🧍 姿势参考 (${poseCount()})`;
        mineBtn.style.background = isMine ? THEME.mine : THEME.mineSoft;
        mineBtn.style.color = isMine ? "#1a1206" : THEME.mine;
        mineBtn.textContent = isMine ? "🏷 返回标签" : `⭐ 我的 (${customCount()})`;
        const isChar = view === "chars";
        charBtn.style.background = isChar ? THEME.char : THEME.charSoft;
        charBtn.style.color = isChar ? "#0d1024" : THEME.char;
        charBtn.textContent = isChar ? "🏷 返回标签"
            : `🧑‍🎤 角色 (${(STATE.charData?.chars || []).length || 0})`;
        const isStory = view === "story";
        storyBtn.style.background = isStory ? THEME.story : THEME.storySoft;
        storyBtn.style.color = isStory ? "#12100a" : THEME.story;
        storyBtn.textContent = isStory ? "🏷 返回标签" : "📖 剧情";
        const overlayView = isOutfit || isPose || isMine || isChar || isStory;
        search.style.display = overlayView ? "none" : "";
        side.style.display = overlayView ? "none" : "";
        // 动作/视角快速条只在「标签」视图显示 —— 它操作的是标签选择，
        // 在服装/姿势/角色这些覆盖视图里显示出来只会让人误以为能一起用。
        actViewRow.style.display = overlayView ? "none" : "flex";
        outfitBar.style.display = isOutfit ? "flex" : "none";
        randomBar.style.display = isOutfit ? "flex" : "none";
        poseBar.style.display = isPose ? "flex" : "none";
        mineBar.style.display = isMine ? "flex" : "none";
        charBar.style.display = isChar ? "flex" : "none";
        storyBar.style.display = isStory ? "flex" : "none";
        renderGrid();
    }

    function renderOutfitBar() {
        outfitBar.innerHTML = "";
        const all = STATE.data?.outfit_presets || [];
        outfitBar.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
            { textContent: "来源" }));
        const mkSrc = (id, label) => {
            const on = outfitSrc === id;
            const b = el("button", {
                padding: "2px 8px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${on ? THEME.outfit : THEME.line}`,
                background: on ? "rgba(232,121,249,0.18)" : THEME.panel2,
                color: on ? THEME.outfit : THEME.text,
            }, { textContent: label });
            b.onclick = () => { outfitSrc = id; renderOutfitBar(); renderGrid(); };
            return b;
        };
        const nCur = all.filter((p) => p.src === "curated").length;
        const nImp = all.filter((p) => p.src === "import").length;
        outfitBar.appendChild(mkSrc("all", `全部 ${all.length}`));
        outfitBar.appendChild(mkSrc("curated", `手工精选 ${nCur}`));
        outfitBar.appendChild(mkSrc("import", `服装库 ${nImp}`));

        outfitBar.appendChild(el("span", {
            fontSize: "10px", color: THEME.dim, marginLeft: "10px",
        }, { textContent: "分组" }));
        const groups = STATE.data?.outfit_groups || [];
        const mk = (id, label, count, color) => {
            const on = outfitGroup === id;
            const b = el("button", {
                padding: "2px 8px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${on ? (color || THEME.outfit) : THEME.line}`,
                background: on ? `${color || THEME.outfit}2e` : THEME.panel2,
                color: on ? (color || THEME.outfit) : THEME.text,
            }, { textContent: `${label}${count != null ? ` ${count}` : ""}` });
            // data-g 给测试用：从按钮反查它对应的分组 id，避免测试里写死 id
            // （写死过 "al_royal"，v1.9.9 改成 "gc_al_royal" 后测试就假失败了）
            b.setAttribute("data-g", id);
            b.onclick = () => {
                outfitGroup = id;
                // 记一笔，供测试/调试核对"抽出来的这套是不是在这个组里"
                if (node) node.__animansfwLastGroup = id;
                renderOutfitBar();
                renderGrid();
            };
            return b;
        };
        outfitBar.appendChild(mk("all", "全部", null));
        for (const g of groups) {
            const n = all.filter((p) => p.g === g.id && (outfitSrc === "all" || p.src === outfitSrc)).length;
            if (!n) continue;
            outfitBar.appendChild(mk(g.id, `${g.icon || ""}${g.zh}`, n));
        }
        outfitBar.appendChild(el("span", { flex: "1" }));
        const inp = el("input", {
            width: "200px", padding: "4px 8px", borderRadius: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2,
            color: THEME.text, fontSize: "11px", outline: "none",
        }, { placeholder: "搜索预设 / 角色名 / 标签…", type: "text", value: outfitQuery });
        inp.addEventListener("input", () => {
            outfitQuery = inp.value;
            clearTimeout(outfitTimer);
            outfitTimer = setTimeout(renderGrid, 140);
        });
        outfitBar.appendChild(inp);
        renderRandomBar();
    }

    // ------------------------------------------------------------------
    // 随机服装
    // ------------------------------------------------------------------
    let randomWithAccessories = false;   // 是否顺带随机配饰
    let lastRandomId = "";               // 避免连续抽到同一套

    /** 当前筛选条件下可抽的预设池（和网格看到的一致） */
    function randomPool() {
        const q = outfitQuery.trim().toLowerCase();
        return (STATE.data?.outfit_presets || []).filter((p) => {
            if (outfitSrc !== "all" && p.src !== outfitSrc) return false;
            if (outfitGroup !== "all" && p.g !== outfitGroup) return false;
            if (q && !(`${p.zh} ${p.en} ${(p.tags || []).join(" ")}`.toLowerCase().includes(q))) {
                return false;
            }
            return true;
        });
    }

    function randomOutfit() {
        const pool = randomPool();
        if (!pool.length) { toast("当前筛选下没有可抽的预设"); return; }
        let pick = pool[Math.floor(Math.random() * pool.length)];
        // 池子大于 1 时避免连续重复
        if (pool.length > 1) {
            for (let i = 0; i < 6 && pick.id === lastRandomId; i++) {
                pick = pool[Math.floor(Math.random() * pool.length)];
            }
        }
        lastRandomId = pick.id;

        // 配饰补全：只影响这次写入的 tags，不改预设对象本身
        let toApply = pick;
        let added = [];
        if (randomWithAccessories) {
            const tags = withRandomAccessories(pick, 1 + Math.floor(Math.random() * 2));
            added = tags.filter((x) => !(pick.tags || []).includes(x));
            if (added.length) toApply = Object.assign({}, pick, { tags });
        }
        applyPresetOutfit(toApply);
        try {
            if (node.__animansfwLastPreset) {
                node.__animansfwLastPreset.random = true;
                node.__animansfwLastPreset.added = added;
            }
        } catch (e) { /* 忽略 */ }

        // 重画网格：让「当前套用」标记落到正确的卡片上，并滚进视野
        if (view === "outfits") {
            renderGrid();
            setTimeout(() => {
                const cur = grid.querySelector('button[data-preset-current]');
                if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
            }, 40);
        }

        const g = (STATE.data?.outfit_groups || []).find((x) => x.id === pick.g);
        toast(`🎲 ${pick.zh}${g ? `（${g.zh}）` : ""}`
            + (added.length ? ` ＋ ${added.join("、")}` : "")
            + (pick.lock ? " · 含角色锁定" : ""));
    }

    function renderRandomBar() {
        randomBar.innerHTML = "";
        const btn = el("button", {
            padding: "4px 12px", borderRadius: "10px", cursor: "pointer",
            fontSize: "11px", fontWeight: "700",
            border: `1px solid ${THEME.outfit}`,
            background: "rgba(232,121,249,0.16)", color: THEME.outfit,
        }, {
            textContent: "🎲 随机一套服装",
            title: "在「当前来源 + 当前分组 + 搜索词」筛选出的预设里随机抽一套。"
                + "每一套预设本身就是成套的，所以搭配一定合理；"
                + "勾上「＋配饰」会再补 1~2 个同色系配饰。",
        });
        btn.onclick = randomOutfit;
        randomBar.appendChild(btn);

        const chk = el("label", {
            display: "inline-flex", alignItems: "center", gap: "4px",
            fontSize: "11px", color: THEME.dim, cursor: "pointer",
        });
        const box = el("input", { cursor: "pointer" }, { type: "checkbox" });
        box.checked = randomWithAccessories;
        box.addEventListener("change", () => { randomWithAccessories = box.checked; });
        chk.appendChild(box);
        chk.appendChild(el("span", {}, { textContent: "＋配饰（同色系，1~2 个）" }));
        randomBar.appendChild(chk);

        const cnt = randomPool().length;
        randomBar.appendChild(el("span", {
            fontSize: "10px", color: THEME.dim,
        }, { textContent: `可抽 ${cnt} 套` }));
    }

    function wireOutfitView() {
        outfitBtn.onclick = () => setView(view === "outfits" ? "tags" : "outfits");
        poseBtn.onclick = () => setView(view === "poses" ? "tags" : "poses");
        mineBtn.onclick = () => setView(view === "mine" ? "tags" : "mine");
        charBtn.onclick = () => {
            const next = view === "chars" ? "tags" : "chars";
            setView(next);
            if (next === "chars") loadChars();
        };
        storyBtn.onclick = () => {
            const next = view === "story" ? "tags" : "story";
            setView(next);
            if (next === "story") loadStory();
        };
        renderOutfitBar();
        renderPoseBar();
        renderMineBar();
        renderOutfitRow();
        setView("tags");
        // 后台把自定义库拉起来，切到「我的」时就不用等
        loadCustom().then(() => { if (view === "mine") renderMineBar(); }).catch(() => {});
    }

    // ------------------------------------------------------------------
    // 我的库（触发词 / 角色 / 服装 / 姿势）
    // ------------------------------------------------------------------

    function customCount(kind) {
        const d = CUSTOM.data;
        if (!d) return 0;
        if (kind) return (d[kind] || []).length;
        return CUSTOM_KINDS.reduce((n, k) => n + (d[k] || []).length, 0);
    }

    function renderMineBar() {
        mineBar.innerHTML = "";
        mineBar.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
            { textContent: "类型" }));
        for (const k of CUSTOM_KINDS) {
            const meta = CUSTOM_META[k];
            const on = mineKind === k;
            const b = el("button", {
                padding: "2px 9px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${on ? meta.color : THEME.line}`,
                background: on ? `${meta.color}2e` : THEME.panel2,
                color: on ? meta.color : THEME.text,
            }, { textContent: `${meta.icon}${meta.zh} ${customCount(k)}` });
            b.onclick = () => { mineKind = k; mineQuery = ""; renderMineBar(); renderGrid(); };
            mineBar.appendChild(b);
        }
        mineBar.appendChild(el("span", { flex: "1" }));
        const add = el("button", {
            padding: "3px 12px", borderRadius: "8px", cursor: "pointer", fontSize: "11px",
            border: "none", background: THEME.mine, color: "#1a1206", fontWeight: "600",
        }, { textContent: "＋ 新建" });
        add.onclick = () => openCustomEditor(mineKind, null);
        mineBar.appendChild(add);

        const imp = el("button", {
            padding: "3px 10px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2, color: THEME.text,
        }, { textContent: "导入" });
        imp.onclick = importCustomLibrary;
        mineBar.appendChild(imp);

        const exp = el("button", {
            padding: "3px 10px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2, color: THEME.text,
        }, { textContent: "导出" });
        exp.onclick = () => { window.open(`${CUSTOM_URL}/export`, "_blank"); };
        mineBar.appendChild(exp);

        const inp = el("input", {
            width: "170px", padding: "4px 8px", borderRadius: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2,
            color: THEME.text, fontSize: "11px", outline: "none",
        }, { placeholder: "搜索我的条目…", type: "text", value: mineQuery });
        inp.addEventListener("input", () => {
            mineQuery = inp.value;
            clearTimeout(mineTimer);
            mineTimer = setTimeout(renderGrid, 120);
        });
        mineBar.appendChild(inp);
    }

    async function importCustomLibrary() {
        const file = el("input", { type: "file", accept: ".json" });
        file.onchange = async () => {
            const f = file.files?.[0];
            if (!f) return;
            try {
                const data = JSON.parse(await f.text());
                const resp = await fetch(`${CUSTOM_URL}/import`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ data }),
                });
                const j = await resp.json();
                if (j?.ok) {
                    CUSTOM.data = normalizeCustom(j.data);
                    try { localStorage.setItem(CUSTOM_LS_KEY, JSON.stringify(CUSTOM.data)); } catch (e) { /* ignore */ }
                    renderMineBar(); renderGrid();
                    toast("导入完成（同名条目已覆盖）");
                } else {
                    toast(`导入失败：${j?.error || "未知错误"}`);
                }
            } catch (e) {
                toast(`导入失败：${e.message}`);
            }
        };
        file.click();
    }

    async function applyCustomEntry(kind, entry) {
        const meta = CUSTOM_META[kind];
        if (kind === "trigger") {
            // 触发词拼到最前面（extra_front），不动用户已选的标签
            const w = findWidget(node, "extra_front");
            const cur = String(w?.value || "").trim();
            const add = [entry.trigger, ...(entry.tags || [])].filter(Boolean).join(", ");
            if (add && !cur.includes(add)) {
                if (w) {
                    w.value = cur ? `${add}, ${cur}` : add;
                    node.setDirtyCanvas?.(true, true);
                }
                const inp = footer.querySelector('textarea');
                if (inp) inp.value = w?.value || "";
            }
            toast(`已把触发词「${entry.name}」加到前置文本`);
        } else if (kind === "outfit") {
            applyPresetOutfit({
                id: entry.id, zh: entry.name, en: entry.name,
                tags: entry.tags, lock: false, src: "mine", g: "", r: "soft",
            });
            toast(`已套用服装「${entry.name}」`);
        } else if (kind === "pose") {
            applyPosePreset({
                id: entry.id, zh: entry.name, en: entry.name,
                tags: entry.tags, lock: false, src: "mine", g: "", r: "soft",
            });
            toast(`已套用姿势「${entry.name}」`);
        } else {
            // 角色：角色名 + 标签一起铺进标签选择
            const all = [entry.trigger, ...(entry.tags || [])].filter(Boolean);
            for (const t of all) {
                if (!selected.has(t.toLowerCase())) select(t);
            }
            renderOutfitRow();
            sync();
            toast(`已铺开角色「${entry.name}」（${all.length} 个标签）`);
        }
    }

    function openCustomEditor(kind, entry) {
        const meta = CUSTOM_META[kind];
        const editing = !!entry;
        // 「存为…」按钮传进来的预填内容（只用一次）
        const pre = (!editing && PENDING_PREFILL?.kind === kind) ? PENDING_PREFILL : null;
        PENDING_PREFILL = null;
        const mask = el("div", {
            position: "fixed", inset: "0", zIndex: "100300",
            background: "rgba(0,0,0,0.6)", display: "flex",
            alignItems: "center", justifyContent: "center",
        });
        const box = el("div", {
            background: THEME.bg, border: `1px solid ${THEME.line}`, borderRadius: "10px",
            padding: "16px", width: "460px", display: "flex", flexDirection: "column",
            gap: "10px", color: THEME.text,
            fontFamily: "'Segoe UI','Microsoft YaHei',sans-serif",
        });
        mask.appendChild(box);
        box.appendChild(el("div", { fontSize: "14px", fontWeight: "600", color: meta.color },
            { textContent: `${editing ? "编辑" : "新建"} ${meta.zh}` }));
        box.appendChild(el("div", { fontSize: "11px", color: THEME.dim },
            { textContent: meta.hint }));

        const mkField = (label, value, placeholder, multiline, height) => {
            const wrap = el("div", { display: "flex", flexDirection: "column", gap: "3px" });
            wrap.appendChild(el("span", { fontSize: "11px", color: THEME.dim },
                { textContent: label }));
            const input = multiline
                ? el("textarea", {
                    height: height || "72px", resize: "vertical", padding: "6px 8px",
                    borderRadius: "6px", border: `1px solid ${THEME.line}`,
                    background: THEME.panel2, color: THEME.text, fontSize: "12px",
                    outline: "none", fontFamily: "inherit",
                })
                : el("input", {
                    padding: "6px 8px", borderRadius: "6px",
                    border: `1px solid ${THEME.line}`, background: THEME.panel2,
                    color: THEME.text, fontSize: "12px", outline: "none",
                });
            input.placeholder = placeholder || "";
            input.value = value || "";
            wrap.appendChild(input);
            box.appendChild(wrap);
            return input;
        };

        const nameIn = mkField("名字（面板上显示）", entry?.name ?? pre?.name, "例如：我的本命角色");
        const trigIn = mkField(
            kind === "trigger" ? "触发词（会拼到提示词最前面）" : "角色触发词（可留空）",
            entry?.trigger ?? pre?.trigger,
            kind === "trigger" ? "例如：my_lora_trigger" : "例如：hakurei reimu, touhou");
        const tagsIn = mkField("标签（逗号或换行分隔）",
            entry ? (entry.tags || []).join(", ")
                  : (pre?.tags || (kind === "character" ? readTags(node) : "")),
            "例如：1girl, long hair, blue eyes", true, kind === "character" ? "96px" : "72px");

        const row = el("div", { display: "flex", gap: "8px", justifyContent: "flex-end" });
        box.appendChild(row);
        const mkBtn = (label, bg, fg, border) => {
            const b = el("button", {
                padding: "7px 16px", borderRadius: "6px", cursor: "pointer",
                fontSize: "12px", fontWeight: "600", border: border || "none",
            }, { textContent: label });
            b.style.background = bg;
            b.style.color = fg;
            if (border) b.style.border = border;
            return b;
        };
        const cancel = mkBtn("取消", THEME.panel2, THEME.text, `1px solid ${THEME.line}`);
        cancel.onclick = () => mask.remove();
        row.appendChild(cancel);

        if (editing) {
            const del = mkBtn("删除", "transparent", THEME.danger, `1px solid ${THEME.danger}88`);
            del.onclick = async () => {
                await deleteCustomEntry(kind, entry.id);
                mask.remove();
                renderMineBar(); renderGrid();
                toast("已删除");
            };
            row.appendChild(del);
        }

        const save = mkBtn("保存", meta.color, "#1a1206");
        save.onclick = async () => {
            const name = nameIn.value.trim();
            if (!name) { toast("名字不能为空"); nameIn.focus(); return; }
            const trigger = trigIn.value.trim();
            const tags = tagsIn.value;
            if (kind === "trigger" && !trigger && !tags.trim()) {
                toast("触发词至少要填一个");
                trigIn.focus();
                return;
            }
            const saved = await saveCustomEntry(kind, {
                id: entry?.id, name, trigger, tags,
            });
            if (saved) {
                mask.remove();
                renderMineBar(); renderGrid();
                toast(`已保存「${name}」`);
            }
        };
        row.appendChild(save);

        mask.addEventListener("mousedown", (e) => { if (e.target === mask) mask.remove(); });
        document.body.appendChild(mask);
        setTimeout(() => nameIn.focus(), 40);
    }


    // ------------------------------------------------------------------
    // 角色浏览器（约 8000 个角色，按作品筛选 + 搜索）
    // ------------------------------------------------------------------

    async function loadChars() {
        if (STATE.charData) { renderCharBar(); renderGrid(); return STATE.charData; }
        if (STATE.charLoading) return STATE.charLoading;
        charBar.innerHTML = "";
        charBar.appendChild(el("span", { fontSize: "11px", color: THEME.dim },
            { textContent: "正在加载角色库…" }));
        STATE.charLoading = (async () => {
            const resp = await fetch(CHAR_URL, { cache: "no-cache" });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            STATE.charData = await resp.json();
            return STATE.charData;
        })();
        try {
            const d = await STATE.charLoading;
            // ⚠️ 必须让作品列表缓存失效：allWorks() 的「每个作品有几个角色」
            //    依赖 charData，缓存下来的话角色数会永远是 0。
            worksCache = null;
            workShown = WORK_PAGE;
            renderWorkList();
            renderCharBar();
            renderGrid();
            return d;
        } catch (e) {
            charBar.innerHTML = "";
            charBar.appendChild(el("span", { fontSize: "11px", color: THEME.danger },
                { textContent: `角色库加载失败：${e.message}` }));
        } finally {
            STATE.charLoading = null;
        }
    }

    function charWorks() {
        const m = new Map();
        for (const c of STATE.charData?.chars || []) {
            const k = c.c || "(未标注作品)";
            m.set(k, (m.get(k) || 0) + 1);
        }
        return [...m.entries()].sort((a, b) => b[1] - a[1]);
    }

    function workLabel(cp) {
        return STATE.charData?.copies?.[cp] || cp;
    }

    function renderCharBar() {
        charBar.innerHTML = "";
        if (!STATE.charData) return;
        const works = charWorks();
        charBar.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
            { textContent: "作品" }));
        const mk = (id, label, count) => {
            const on = charWork === id;
            const b = el("button", {
                padding: "2px 8px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${on ? THEME.char : THEME.line}`,
                background: on ? THEME.charSoft : THEME.panel2,
                color: on ? THEME.char : THEME.text,
                whiteSpace: "nowrap",
            }, { textContent: `${label}${count != null ? " " + count : ""}` });
            b.onclick = () => { charWork = id; renderCharBar(); renderGrid(); };
            return b;
        };
        charBar.appendChild(mk("all", "全部", STATE.charData.chars.length));
        for (const [cp, n] of works.slice(0, 16)) {
            charBar.appendChild(mk(cp, workLabel(cp), n));
        }
        if (works.length > 16) {
            charBar.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
                { textContent: `…共 ${works.length} 个作品；想按作品逐个看，`
                    + `到左侧分类「游戏/作品」点作品名展开` }));
        }
        charBar.appendChild(el("span", { flex: "1" }));
        const inp = el("input", {
            width: "220px", padding: "4px 8px", borderRadius: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2,
            color: THEME.text, fontSize: "11px", outline: "none",
        }, { placeholder: "搜索角色（中文/英文/作品）…", type: "text", value: charQuery });
        inp.addEventListener("input", () => {
            charQuery = inp.value;
            clearTimeout(charTimer);
            charTimer = setTimeout(renderGrid, 130);
        });
        charBar.appendChild(inp);
    }


    /** 作品清单 = 标签库里的版权 tag + 角色库里有角色的作品（合并去重，按角色数排） */
    function allWorks() {
        const seen = new Set();
        const out = [];
        for (const t of STATE.data?.tags || []) {
            if (t.c !== "copyright" || seen.has(t.t)) continue;
            seen.add(t.t);
            out.push({ cp: t.t, zh: t.zh || t.t, n: workChars(t.t).length });
        }
        const copies = STATE.charData?.copies || {};
        for (const cp of Object.keys(copies)) {
            if (seen.has(cp)) continue;
            seen.add(cp);
            out.push({ cp, zh: copies[cp] || cp, n: workChars(cp).length });
        }
        return out.sort((a, b) => b.n - a.n || a.zh.localeCompare(b.zh));
    }

    /** 角色卡片（作品视图与角色视图共用）：3:4 立绘 + 名字 + 作品/热度 */
    function makeCharCard(c) {
        const en = c.n;
        const on = selected.has(en.toLowerCase());
        const card = el("button", {
            width: "148px", padding: "0", borderRadius: "9px", cursor: "pointer",
            textAlign: "left", display: "flex", flexDirection: "column", gap: "0",
            overflow: "hidden", verticalAlign: "top",
            border: `1px solid ${on ? THEME.char : THEME.line}`,
            background: on ? THEME.charSoft : THEME.panel2, color: THEME.text,
        });

        // 立绘（关掉缩略图时不出图，省流量，也能完全离线）
        if (showThumbs()) {
            const thumb = makeThumb(charThumbUrl(en, c.c), { width: 148, height: 197 });
            thumb.style.border = "none";
            thumb.style.borderRadius = "0";
            thumb.style.width = "100%";
            card.appendChild(thumb);
        }

        const info = el("div", {
            padding: "5px 7px 6px", display: "flex", flexDirection: "column", gap: "1px",
        });
        const title = el("div", {
            fontSize: "12px", fontWeight: "600", lineHeight: "1.25",
            color: on ? THEME.char : THEME.text,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }, { textContent: c.z || en });
        info.appendChild(title);
        info.appendChild(el("div", {
            fontSize: "9.5px", color: THEME.dim, lineHeight: "1.3",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }, { textContent: c.z ? en : workLabel(c.c) }));
        info.appendChild(el("div", {
            fontSize: "9.5px", color: THEME.dim, opacity: "0.8",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }, { textContent: `${workLabel(c.c)} · 热度 ${c.p}` }));
        card.appendChild(info);

        // ⚠️ 性别数据存疑时**明说**，不要装作没问题。
        // 背景：Danbooru 上 `mistilteinn (closers)` 有 144 帖标 1boy，但它的 wiki
        // 写的是「Lancer class playable character」—— 那是 Closers 的女性角色米斯丁，
        // 标记是错的。所以拿不准的角色在卡片上标出来，让用户自己判断。
        if (c.gender === "uncertain") {
            info.appendChild(el("div", {
                fontSize: "9.5px", color: THEME.warn || "#fbbf24", lineHeight: "1.3",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: "⚠ 性别标注不可靠" }));
        }

        card.title = `${c.z || en} (${en})\n${workLabel(c.c)}\n`
            + `${(c.t || []).length} 个推荐标签\n${(c.t || []).join(", ")}`
            + (c.gender === "uncertain"
                ? `\n\n⚠ 这个角色的性别标注不可靠，建议自己确认后再用「补齐推荐标签」`
                  + (c.gender_note ? `\n原因：${c.gender_note}` : "")
                : "");
        card.onclick = () => {
            if (!selected.has(en.toLowerCase())) select(en);
            else {
                selected.delete(en.toLowerCase());
                const i = order.findIndex((x) => x.toLowerCase() === en.toLowerCase());
                if (i >= 0) order.splice(i, 1);
            }
            sync();
        };
        return card;
    }

    // ---- 角色网格分页：滚到底自动加载下一批（避免一次建几千个 DOM + 图片）----
    const CHAR_BATCH = 60;
    let charShown = CHAR_BATCH;
    let charObserver = null;

    function charGridReset() {
        charShown = CHAR_BATCH;
        try { charObserver?.disconnect(); } catch (e) { /* ignore */ }
        charObserver = null;
    }

    /** 卡片列表 + 懒加载哨兵 + 「补齐推荐标签」提示条 */
    function renderCharCards(list, note) {
        const box = el("div", {
            width: "100%", display: "flex", flexWrap: "wrap", gap: "7px",
            alignItems: "flex-start",
        });
        if (note) {
            box.appendChild(el("div", {
                width: "100%", fontSize: "11px", color: THEME.char, marginBottom: "2px",
            }, { textContent: note }));
        }
        grid.appendChild(box);

        const draw = (from, to) => {
            const frag = document.createDocumentFragment();
            for (const c of list.slice(from, to)) frag.appendChild(makeCharCard(c));
            box.appendChild(frag);
        };
        draw(0, Math.min(charShown, list.length));

        if (list.length > charShown) {
            const sentinel = el("div", {
                width: "100%", padding: "10px", textAlign: "center",
                fontSize: "11px", color: THEME.dim,
            }, {
                textContent: `已显示 ${Math.min(charShown, list.length)} / ${list.length} ——`
                    + ` 往下滚自动加载更多`,
            });
            box.appendChild(sentinel);
            const more = () => {
                const from = charShown;
                charShown += CHAR_BATCH;
                draw(from, Math.min(charShown, list.length));
                if (charShown >= list.length) {
                    sentinel.textContent = `已全部显示（${list.length} 个）`;
                    try { charObserver?.disconnect(); } catch (e) { /* ignore */ }
                } else {
                    sentinel.textContent = `已显示 ${charShown} / ${list.length} ——`
                        + ` 往下滚自动加载更多`;
                }
            };
            if (typeof IntersectionObserver === "function") {
                charObserver = new IntersectionObserver((entries) => {
                    if (entries.some((e) => e.isIntersecting)) more();
                }, { root: box, rootMargin: "300px" });
                charObserver.observe(sentinel);
            } else {
                // 老前端没有 IntersectionObserver：给个按钮手动加载
                const btn = el("button", {
                    marginTop: "4px", padding: "4px 14px", borderRadius: "8px",
                    cursor: "pointer", fontSize: "11px", border: `1px solid ${THEME.charLine}`,
                    background: THEME.charSoft, color: THEME.char,
                }, { textContent: "加载更多" });
                btn.onclick = more;
                sentinel.textContent = `已显示 ${charShown} / ${list.length}`;
                sentinel.appendChild(el("div", {}, {})).appendChild(btn);
            }
        }
        return box;
    }


    // ------------------------------------------------------------------
    // 📖 剧情模式：主角固定 + 分镜连续性
    // ------------------------------------------------------------------

    async function loadStory() {
        // ⚠️ 并发去重：快速切进/切出剧情视图会重复发请求。之前没有守卫，
        //    两次并发 fetch 时后回来的那次会重写 storyBar；而且如果请求一直不返回，
        //    界面就停在「正在加载剧情库…」上不动（实测见过这个状态）。
        if (STATE.storyLoading) return STATE.storyLoading;
        if (storyCache) { renderStoryBar(); renderGrid(); return storyCache; }
        storyBar.innerHTML = "";
        storyBar.appendChild(el("span", { fontSize: "11px", color: THEME.dim },
            { textContent: "正在加载剧情库…" }));
        STATE.storyLoading = (async () => {
            const resp = await fetch(STORY_URL, { cache: "no-cache" });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return resp.json();
        })();
        try {
            storyCache = await STATE.storyLoading;
            if (!storyArc && storyCache.arcs?.length) storyArc = storyCache.arcs[0].id;
            renderStoryBar();
            renderGrid();
            return storyCache;
        } catch (e) {
            storyBar.innerHTML = "";
            storyBar.appendChild(el("span", { fontSize: "11px", color: THEME.danger },
                { textContent: `剧情库加载失败：${e.message}` }));
        } finally {
            STATE.storyLoading = null;
        }
    }

    function currentArc() {
        return (storyCache?.arcs || []).find((a) => a.id === storyArc) || null;
    }

    /** 当前故事的主角逐个候选 */
    function arcCastKeys(arc) {
        return (arc?.cast || []).filter((k) => storyCache?.cast?.[k]);
    }

    function currentCastKey() {
        const arc = currentArc();
        const keys = arcCastKeys(arc);
        return storyCast && keys.includes(storyCast) ? storyCast : (keys[0] || "");
    }

    function castThumb(key) {
        const c = storyCache?.cast?.[key];
        if (!c) return "";
        return charThumbUrl(c.name, c.copyright);
    }

    /** 从节点当前的 tags 控件重建面板的选中态（套用剧情/预设后必须调用） */
    function syncSelectionFromNode() {
        const now = parseTags(readTags(node));
        selected.clear();
        order.length = 0;
        for (const t of now) {
            const k = String(t).toLowerCase();
            if (!k) continue;
            selected.add(k);
            order.push(t);
        }
    }

    function renderStoryBar() {        storyBar.innerHTML = "";
        if (!storyCache) return;
        const arcs = storyCache.arcs || [];

        // ---- 第一行：故事线 ----
        const row1 = el("div", { display: "flex", gap: "5px", flexWrap: "wrap",
                                 alignItems: "center", width: "100%" });
        row1.appendChild(el("span", { fontSize: "10px", color: THEME.dim, flexShrink: "0" },
            { textContent: "故事" }));
        for (const a of arcs) {
            const on = a.id === storyArc;
            const b = el("button", {
                padding: "3px 9px", borderRadius: "8px", cursor: "pointer", fontSize: "11px",
                border: `1px solid ${on ? THEME.story : THEME.line}`,
                background: on ? THEME.storySoft : THEME.panel2,
                color: on ? THEME.story : THEME.text, whiteSpace: "nowrap",
            }, { textContent: a.title, title: a.zh + "\n" + a.summary });
            b.onclick = () => {
                storyArc = a.id;
                storyCast = "";
                renderStoryBar();
                renderGrid();
            };
            row1.appendChild(b);
        }
        storyBar.appendChild(row1);

        const arc = currentArc();
        if (!arc) return;

        // ---- 第二行：主角（带立绘）----
        const row2 = el("div", { display: "flex", gap: "6px", flexWrap: "wrap",
                                 alignItems: "center", width: "100%" });
        row2.appendChild(el("span", { fontSize: "10px", color: THEME.dim, flexShrink: "0" },
            { textContent: "主角" }));
        const cur = currentCastKey();
        for (const key of arcCastKeys(arc)) {
            const c = storyCache.cast[key];
            const on = key === cur;
            const box = el("button", {
                display: "flex", alignItems: "center", gap: "5px", padding: "3px 8px 3px 3px",
                borderRadius: "9px", cursor: "pointer", fontSize: "11px",
                border: `1px solid ${on ? THEME.story : THEME.line}`,
                background: on ? THEME.storySoft : THEME.panel2,
                color: on ? THEME.story : THEME.text,
            });
            if (showThumbs()) {
                const th = makeThumb(castThumb(key), { width: 26, height: 34 });
                th.style.borderRadius = "5px";
                th.style.width = "26px";
                th.style.height = "34px";
                box.appendChild(th);
            }
            box.appendChild(el("span", {}, { textContent: c.zh || c.name }));
            box.title = `${c.zh} (${c.name})\n${c.copyright}`;
            box.onclick = () => {
                storyCast = key;
                renderStoryBar();
                renderGrid();
            };
            row2.appendChild(box);
        }
        storyBar.appendChild(row2);

        // ---- 第三行：这一卷的说明 ----
        storyBar.appendChild(el("div", {
            fontSize: "10.5px", color: THEME.dim, lineHeight: "1.5", width: "100%",
        }, {
            textContent: `${arc.zh} ｜ ${arc.genre} ｜ 尺度 ${arc.level} ｜ `
                + `${(arc.scenes || []).length} 拍\n${arc.summary}\n`
                + "点下面任意一拍即可套进节点；主角的发色/瞳色/服装跨图保持一致。",
        }));
    }

    function renderStoryGrid() {
        grid.innerHTML = "";
        if (!storyCache) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "正在加载剧情库…" }));
            return;
        }
        const arc = currentArc();
        if (!arc) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "没有可用的故事线" }));
            return;
        }
        const key = currentCastKey();
        const cast = storyCache.cast[key] || {};
        const wrap = el("div", {
            width: "100%", display: "flex", flexWrap: "wrap", gap: "8px",
            alignItems: "flex-start",
        });
        grid.appendChild(wrap);

        for (const sc of arc.scenes || []) {
            const card = el("div", {
                width: "268px", padding: "0", borderRadius: "9px", overflow: "hidden",
                border: `1px solid ${THEME.line}`, background: THEME.panel2,
                display: "flex", flexDirection: "column",
            });
            // 头部：第几拍 + 本拍标题
            const head = el("div", {
                display: "flex", alignItems: "center", gap: "5px",
                padding: "5px 8px", background: THEME.storySoft,
                borderBottom: `1px solid ${THEME.line}`,
            });
            head.appendChild(el("span", {
                fontSize: "10px", fontWeight: "700", color: THEME.story,
                padding: "0 5px", borderRadius: "5px", background: THEME.storySoft,
            }, { textContent: `#${sc.id}` }));
            head.appendChild(el("span", {
                fontSize: "11.5px", fontWeight: "600", color: THEME.text,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: sc.beat || "" }));
            card.appendChild(head);

            // 主体：立绘（主角） + 台词
            const body = el("div", { display: "flex", gap: "7px", padding: "7px 8px" });
            if (showThumbs()) {
                const th = makeThumb(castThumb(key), { width: 62, height: 82 });
                th.style.flexShrink = "0";
                th.title = `${cast.zh || ""} —— 这一拍的主角（用主角立绘占位，实际出图是这一幕）`;
                body.appendChild(th);
            }
            const txt = el("div", { display: "flex", flexDirection: "column",
                                    gap: "3px", minWidth: "0", flex: "1" });
            txt.appendChild(el("div", {
                fontSize: "11px", color: THEME.text, lineHeight: "1.45",
            }, { textContent: sc.dialogue || sc.dialogue_en || "" }));
            txt.appendChild(el("div", {
                fontSize: "9.5px", color: THEME.dim, lineHeight: "1.35",
                fontStyle: "italic",
            }, { textContent: sc.dialogue_en || "" }));
            txt.appendChild(el("div", {
                fontSize: "9px", color: THEME.dim, opacity: "0.75", lineHeight: "1.35",
                overflow: "hidden", textOverflow: "ellipsis",
            }, { textContent: `${(sc.tags || []).length} 个场景标签` }));
            body.appendChild(txt);
            card.appendChild(body);

            // 底部：套用按钮
            const foot = el("div", { display: "flex", gap: "5px", padding: "0 8px 8px" });
            const use = el("button", {
                flex: "1", padding: "5px 0", borderRadius: "7px", cursor: "pointer",
                fontSize: "11.5px", fontWeight: "600", border: "none",
                background: THEME.story, color: "#12100a",
            }, { textContent: "🎬 套用这一拍" });
            use.onclick = () => applyStoryScene(arc, sc, key);
            foot.appendChild(use);
            const copy = el("button", {
                padding: "5px 9px", borderRadius: "7px", cursor: "pointer",
                fontSize: "11.5px", border: `1px solid ${THEME.line}`,
                background: THEME.panel, color: THEME.text,
            }, { textContent: "复制台词", title: "复制中文台词" });
            copy.onclick = async () => {
                const ok = await copyText(sc.dialogue || "");
                copy.textContent = ok ? "已复制" : "失败";
                setTimeout(() => { copy.textContent = "复制台词"; }, 1200);
            };
            foot.appendChild(copy);
            card.appendChild(foot);
            wrap.appendChild(card);
        }

        // 连续性说明
        wrap.appendChild(el("div", {
            width: "100%", marginTop: "6px", padding: "8px 10px", borderRadius: "8px",
            border: `1px solid ${THEME.storyLine}`, background: THEME.storySoft,
            fontSize: "11px", color: THEME.text, lineHeight: "1.6",
        }, {
            textContent: "🔗 连续性怎么保证：每一拍都自动带上同一个 char_lock 主角 + "
                + "同一个作品 + 这套立绘标签（"
                + (cast.look || []).slice(0, 6).join(", ") + " …） + 固定服装（"
                + (cast.outfit || []).slice(0, 4).join(", ") + " …） + 同一套镜头与风格；"
                + "套用时会把种子模式自动切到「递增 +1」，这样连画 6 张就是一条序列。",
        }));
        wrap.appendChild(el("div", {
            width: "100%", marginTop: "4px", fontSize: "10.5px", color: THEME.dim,
        }, {
            textContent: "提示：想一次画完 6 张，把「种子模式」保持在递增、"
                + "连点 6 次生成即可；想改剧情走向，套用后直接在标签面板里加/减标签。",
        }));
    }

    /** 把某一拍套进节点 */
    function applyStoryScene(arc, sc, castKey) {
        (async () => {
            try {
                const url = `${STORY_URL}/scene?arc=${encodeURIComponent(arc.id)}`
                    + `&scene=${sc.id}&cast=${encodeURIComponent(castKey)}`;
                const resp = await fetch(url, { cache: "no-cache" });
                const data = await resp.json();
                if (!data.ok) throw new Error(data.error || "未知错误");
                const s = data.scene;

                // 1) 标签
                // ⚠️ 台词**不写进 caption_text**：caption_text 会拼进正面提示词，
                //    模型会把英文台词当字幕画在图上（实测出现底部乱码字幕 + 假 logo）。
                //    台词只在面板上给你读，需要的话点卡片上的「复制台词」。
                writeTags(node, s.tags);
                const cw = findWidget(node, "caption_text");
                if (cw) cw.value = "";
                // ⚠️ 同时要把面板内部的选中态换成这一拍的标签。
                // 否则「应用/关闭」时会用旧的 selected/order 覆盖回去
                //（commit 里写的是 joinTags(order)），套用就白做了。
                syncSelectionFromNode();

                // 2) 主角服装（锁定角色，保证跨图一致）
                const cast = s.cast || {};
                const outfit = (cast.outfit || []).slice();
                currentPreset = {
                    zh: `${cast.zh || cast.name}·${arc.title} #${s.scene_no}`,
                    en: arc.id,
                    tags: outfit,
                    lock: true,
                };
                const pw = findWidget(node, "outfit_preset");
                if (pw) pw.value = encodeOutfitPreset(currentPreset);

                // 3) 种子：递增，让 6 张连成一条序列
                seedMode = SEED_MODES[2];
                const smw = findWidget(node, "seed_mode");
                if (smw) smw.value = seedMode;
                const sdw = findWidget(node, "seed");
                if (sdw && !sdw.value) sdw.value = seedValue;
                const res = applySeedToGraph(node, seedMode, seedValue);

                // 4) 切回标签视图并刷新预览
                setView("tags");
                try { await refreshPreview(node, true); } catch (e) { /* ignore */ }
                sync();
                toast(`已套用「${arc.title}」第 ${s.scene_no} 拍 · `
                    + `台词：${(s.dialogue || "").slice(0, 24)}`
                    + `（主角 ${cast.zh || cast.name}`
                    + `${res.count ? `，种子已设为递增·${res.count} 个采样器` : ""}）`);
            } catch (e) {
                alert(`套用剧情失败：${e.message}`);
            }
        })();
    }

    function renderCharGrid() {
        grid.innerHTML = "";
        if (!STATE.charData) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "正在加载角色库…" }));
            return;
        }
        const q = charQuery.trim().toLowerCase();
        const all = STATE.charData.chars || [];
        const list = all.filter((c) => {
            if (charWork !== "all" && (c.c || "(未标注作品)") !== charWork) return false;
            if (!q) return true;
            return `${c.n} ${c.z || ""} ${c.c || ""} ${workLabel(c.c)}`
                .toLowerCase().includes(q);
        });
        if (!list.length) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "没有匹配的角色" }));
            return;
        }
        if (grid.__charKey !== `chars|${charWork}|${q}`) {
            grid.__charKey = `chars|${charWork}|${q}`;
            charGridReset();
        }
        const label = charWork === "all" ? "全部角色" : workLabel(charWork);
        renderCharCards(list, `${label} · ${list.length} 个`);
        // 选中角色时，顺手提示可直接套用它的推荐标签
        const active = order.find((x) => {
            const c = all.find((y) => y.n.toLowerCase() === x.toLowerCase());
            return !!c;
        });
        if (active) {
            const c = all.find((y) => y.n.toLowerCase() === active.toLowerCase());
            const box = el("div", {
                width: "100%", marginTop: "8px", padding: "8px 10px",
                borderRadius: "8px", border: `1px solid ${THEME.charLine}`,
                background: THEME.charSoft, fontSize: "11px", color: THEME.text,
                display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap",
            });
            box.appendChild(el("span", {},
                { textContent: `已选角色「${c.z || c.n}」，可一键补上它的 ${(c.t || []).length} 个推荐标签：` }));
            const b = el("button", {
                padding: "3px 12px", borderRadius: "6px", cursor: "pointer",
                fontSize: "11px", border: "none", background: THEME.char,
                color: "#0d1024", fontWeight: "600",
            }, { textContent: "补齐推荐标签" });
            b.onclick = () => {
                // ⚠️ 先把用户已有的**性别锚点**清掉，再用角色自己的。
                //
                // `1girl` / `1boy` / 2girls / multiple boys … 全在互斥组 `count`，
                // 只保留最后一个。面板默认标签就带 `1girl`，如果不清，就得看
                // 「角色名 vs 1girl」谁排在后面 —— 顺序一变结果就变（实测踩过）。
                //
                // 清掉之后由角色自己的锚点唯一决定，与顺序无关。
                const COUNT = "count";
                for (const t of [...order]) {
                    const inf = tagInfo(t);
                    if (inf && inf.g === COUNT) {
                        selected.delete(t.toLowerCase());
                        const i = order.indexOf(t);
                        if (i >= 0) order.splice(i, 1);
                    }
                }
                for (const t of (c.t || [])) {
                    // 角色带来的性别锚点打 char_anchor: 标记（后端据此判定，并剥掉）
                    const info = tagInfo(t);
                    const tagged = (info && info.g === COUNT) ? `char_anchor:${t}` : t;
                    if (!selected.has(tagged.toLowerCase())) select(tagged);
                }
                sync();
                toast(`已补上「${c.z || c.n}」的推荐标签`
                    + `（性别锚点按角色自带，已清掉冲突项）`);
            };
            box.appendChild(b);
            grid.appendChild(box);
        }
    }

    function renderMineGrid() {
        grid.innerHTML = "";
        const list = (CUSTOM.data?.[mineKind] || []);
        const q = mineQuery.trim().toLowerCase();
        const shown = list.filter((e) => {
            if (!q) return true;
            return `${e.name} ${e.trigger} ${(e.tags || []).join(" ")}`.toLowerCase().includes(q);
        });
        const meta = CUSTOM_META[mineKind];

        if (!shown.length) {
            const tip = el("div", {
                width: "100%", color: THEME.dim, fontSize: "12px",
                display: "flex", flexDirection: "column", gap: "8px",
            });
            tip.appendChild(el("div", { textContent: q ? "没有匹配的条目" : `${meta.zh}还是空的。` }));
            tip.appendChild(el("div", { fontSize: "11px", textContent: meta.hint }));
            const b = el("button", {
                alignSelf: "flex-start", padding: "6px 14px", borderRadius: "6px",
                cursor: "pointer", fontSize: "12px", border: "none",
                background: meta.color, color: "#1a1206", fontWeight: "600",
            }, { textContent: "＋ 新建一条" });
            b.onclick = () => openCustomEditor(mineKind, null);
            tip.appendChild(b);
            grid.appendChild(tip);
            return;
        }

        const frag = document.createDocumentFragment();
        for (const e of shown) {
            const card = el("div", {
                width: "264px", padding: "8px 10px", borderRadius: "9px",
                border: `1px solid ${THEME.line}`, background: THEME.panel2,
                display: "flex", flexDirection: "column", gap: "4px",
            });
            const title = el("div", {
                display: "flex", alignItems: "center", gap: "5px",
                fontSize: "12.5px", fontWeight: "600", color: meta.color,
            });
            title.appendChild(el("span", {}, { textContent: `${meta.icon} ${e.name}` }));
            card.appendChild(title);
            if (e.trigger) {
                card.appendChild(el("div", {
                    fontSize: "10px", color: THEME.text, opacity: "0.9",
                    fontFamily: "ui-monospace,Consolas,monospace",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }, { textContent: `触发: ${e.trigger}` }));
            }
            card.appendChild(el("div", {
                fontSize: "10px", color: THEME.dim,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: `${(e.tags || []).length} 个标签` }));
            card.appendChild(el("div", {
                fontSize: "10px", color: THEME.dim, lineHeight: "1.35",
                maxHeight: "28px", overflow: "hidden",
                fontFamily: "ui-monospace,Consolas,monospace", opacity: "0.85",
            }, { textContent: (e.tags || []).join(", ") }));

            const btns = el("div", { display: "flex", gap: "5px", marginTop: "2px" });
            const mk = (label, color, fn) => {
                const b = el("button", {
                    padding: "3px 10px", borderRadius: "6px", cursor: "pointer",
                    fontSize: "11px", border: `1px solid ${color}77`,
                    background: `${color}22`, color: color,
                }, { textContent: label });
                b.onclick = fn;
                return b;
            };
            const applyLabel = mineKind === "trigger" ? "加到前置"
                : (mineKind === "character" ? "铺开标签" : "套用");
            btns.appendChild(mk(applyLabel, meta.color, () => applyCustomEntry(mineKind, e)));
            btns.appendChild(mk("编辑", THEME.dim, () => openCustomEditor(mineKind, e)));
            card.appendChild(btns);
            card.title = `${e.name}\n${e.trigger ? "触发: " + e.trigger + "\n" : ""}${(e.tags || []).join(", ")}`;
            frag.appendChild(card);
        }
        grid.appendChild(frag);
    }

    // ------------------------------------------------------------------
    // 姿势参考预设
    // ------------------------------------------------------------------

    function poseCount() {
        return (STATE.data?.pose_presets || []).length;
    }

    function writePoseSilently(target, value) {
        const w = findWidget(target, "pose_preset");
        if (!w) return;
        w.value = value;
        target.setDirtyCanvas?.(true, true);
    }

    function applyPosePreset(preset) {
        if (!preset) return;
        if (currentPose && currentPose.id === preset.id) {
            currentPose = null;
            writePoseSilently(node, "");
            renderOutfitRow();
            sync();
            return;
        }
        currentPose = preset;
        writePoseSilently(node, encodeOutfitPreset(preset));
        renderOutfitRow();
        sync();
    }

    function renderPoseBar() {
        poseBar.innerHTML = "";
        const all = STATE.data?.pose_presets || [];
        poseBar.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
            { textContent: "分组" }));
        const mk = (id, label, count) => {
            const on = poseGroup === id;
            const b = el("button", {
                padding: "2px 8px", borderRadius: "8px", cursor: "pointer", fontSize: "10px",
                border: `1px solid ${on ? THEME.pose : THEME.line}`,
                background: on ? THEME.poseSoft : THEME.panel2,
                color: on ? THEME.pose : THEME.text,
            }, { textContent: `${label}${count != null ? ` ${count}` : ""}` });
            b.onclick = () => { poseGroup = id; renderPoseBar(); renderGrid(); };
            return b;
        };
        poseBar.appendChild(mk("all", "全部", all.length));
        for (const g of STATE.data?.pose_groups || []) {
            const n = all.filter((p) => p.g === g.id).length;
            if (!n) continue;
            poseBar.appendChild(mk(g.id, `${g.icon || ""}${g.zh}`, n));
        }
        poseBar.appendChild(el("span", { flex: "1" }));
        const inp = el("input", {
            width: "210px", padding: "4px 8px", borderRadius: "10px",
            border: `1px solid ${THEME.line}`, background: THEME.panel2,
            color: THEME.text, fontSize: "11px", outline: "none",
        }, { placeholder: "搜索姿势 / 标签…", type: "text", value: poseQuery });
        inp.addEventListener("input", () => {
            poseQuery = inp.value;
            clearTimeout(poseTimer);
            poseTimer = setTimeout(renderGrid, 140);
        });
        poseBar.appendChild(inp);
    }

    // ------------------------------------------------------------------

    function renderSelected() {
        selectedBar.innerHTML = "";
        if (!order.length) {
            selectedBar.appendChild(el("span", { color: THEME.dim, fontSize: "11px" },
                { textContent: "还没选标签。可以从左侧强度档位一键铺底，或直接在下方点选。" }));
            return;
        }
        for (const tag of order) {
            const info = tagInfo(tag);
            const color = RATING_COLORS[info?.r || "soft"] || THEME.dim;
            const chip = el("span", {
                display: "inline-flex", alignItems: "center", gap: "4px",
                padding: "2px 6px", borderRadius: "10px", fontSize: "11px",
                background: `${color}22`, color: color, border: `1px solid ${color}66`,
                cursor: "pointer",
            });
            chip.appendChild(el("span", {}, { textContent: info?.zh ? `${info.zh}` : tag }));
            chip.appendChild(el("span", { opacity: "0.8", fontWeight: "700" }, { textContent: "×" }));
            chip.title = tag;
            chip.onclick = () => { sync(false, select(tag)); };
            selectedBar.appendChild(chip);
        }
    }

    // 当前已渲染的「标签键 → { card, info }」。点标签时只重画受影响的这几张，
    // 不用把整个网格拆掉重建（原来每个标签点击都会重建，实测 115 个 DOM 节点）。
    const tagCards = new Map();

    /** 单张标签卡的选中态（务必和 renderGrid 里的初始样式保持一致） */
    function paintTagCard(card, info) {
        const on = selected.has(String(info.t).toLowerCase());
        const color = RATING_COLORS[info.r] || THEME.dim;
        const s = card.style;
        s.border = `1px solid ${on ? color : THEME.line}`;
        s.background = on ? `${color}2e` : THEME.panel2;
        s.color = on ? color : THEME.text;
        const en = card.lastChild;
        if (en && en.style) en.style.color = on ? color : THEME.dim;
    }

    function renderGrid() {
        tagCards.clear();
        if (view === "outfits") {
            renderOutfitGrid();
            return;
        }
        if (view === "poses") {
            renderPoseGrid();
            return;
        }
        if (view === "mine") {
            renderMineGrid();
            return;
        }
        if (view === "chars") {
            renderCharGrid();
            return;
        }
        if (view === "story") {
            renderStoryGrid();
            return;
        }
        grid.innerHTML = "";
        const q = query.trim().toLowerCase();

        // 选中某个作品时：先用卡片铺开这个作品的角色，再显示作品标签本身。
        // ⚠️ 同样不能只查版权标签 —— `closers` 这类只存在于角色库里的作品
        //    会被判成"不是作品"，网格全空（用户报的「点封印者没角色」）。
        const isWork = activeCat !== "all" && inWorkContext();
        // 换了作品/分类/搜索词就回到第一批
        if (grid.__charKey !== `${activeCat}|${q}`) {
            grid.__charKey = `${activeCat}|${q}`;
            charGridReset();
        }
        if (isWork && STATE.charData) {
            const kidsAll = workChars(activeCat);
            const kids = kidsAll.filter((c) => !q
                || `${c.n} ${c.z || ""}`.toLowerCase().includes(q));
            renderCharCards(kids, `${workLabel(activeCat)} · ${kidsAll.length} 个角色`
                + (q && kids.length !== kidsAll.length ? `（匹配 ${kids.length}）` : ""));
            grid.appendChild(el("div", {
                width: "100%", height: "1px", background: THEME.line, margin: "9px 0 5px",
            }));
            grid.appendChild(el("div", {
                width: "100%", fontSize: "11px", color: THEME.dim, marginBottom: "4px",
                textContent: "作品名标签（与上面的角色一起用效果最好）",
            }));
        }

        const list = data.tags.filter((t) => {
            // hidden 的标签（预设补充里的细碎词）默认不显示，选中或开了开关才露面
            if (t.hidden && !showHidden && !selected.has(t.t.toLowerCase())) return false;
            // SFW 模式：会把被拦下的标签从网格里藏掉（已选中的仍显示，方便取消）
            if (sfwBlocked(t.t) && !selected.has(t.t.toLowerCase())) return false;
            if (activeCat !== "all" && t.c !== activeCat) return false;
            if (!q) return true;
            return t.t.toLowerCase().includes(q) || String(t.zh || "").includes(query.trim());
        });
        if (!list.length) {
            const box = el("div", {
                color: THEME.dim, fontSize: "12px", maxWidth: "560px", lineHeight: "1.6",
            });
            box.appendChild(el("div", { textContent: "没有匹配的标签" }));
            if (activeCat === "all" && !showHidden && !q) {
                box.appendChild(el("div", {
                    marginTop: "8px", fontSize: "11px",
                    textContent: "「预设补充」里的细碎标签默认隐藏，"
                        + "勾选左侧「显示隐藏标签」即可看到。",
                }));
            }
            grid.appendChild(box);
            return;
        }
        // ⚠️ 必须分页！这里曾经漏掉 slice，导致一次建 11097 张卡片
        //    （11 万 DOM 节点 + 62 万次样式写入，全同步）—— 面板一开就卡死。
        const shown = list.slice(0, CARD_LIMIT);
        const frag = document.createDocumentFragment();
        for (const t of shown) {
            const on = selected.has(t.t.toLowerCase());
            const color = RATING_COLORS[t.r] || THEME.dim;
            const item = el("button", {
                padding: "5px 9px", borderRadius: "12px", cursor: "pointer",
                fontSize: "12px", lineHeight: "1.2", textAlign: "left",
                border: `1px solid ${on ? color : THEME.line}`,
                background: on ? `${color}2e` : THEME.panel2,
                color: on ? color : THEME.text,
                display: "inline-flex", flexDirection: "column", gap: "1px",
                maxWidth: "220px",
            });
            item.appendChild(el("span", { fontSize: "12px" }, { textContent: t.zh || t.t }));
            item.appendChild(el("span", {
                fontSize: "10px", color: on ? color : THEME.dim, opacity: "0.85",
            }, { textContent: t.t }));
            item.title = `${t.t}${t.g ? ` · 互斥组: ${t.g}` : ""}`;
            item.onclick = () => { sync(false, select(t.t)); };
            tagCards.set(t.t.toLowerCase(), { card: item, info: t });
            frag.appendChild(item);
        }
        grid.appendChild(frag);
        if (list.length > shown.length) {
            appendMoreHint(list.length - shown.length, () => {});
        }
    }

    /** 分组名 → 可搜索文本（"碧蓝·皇家" / "封印者·基础" …），懒建并缓存 */
    function groupHaystack() {
        if (!STATE.__groupHay) {
            const m = {};
            for (const g of STATE.data?.outfit_groups || []) {
                m[g.id] = `${g.zh || ""} ${g.en || ""}`.toLowerCase();
            }
            STATE.__groupHay = m;
        }
        return STATE.__groupHay;
    }

    function renderOutfitGrid() {
        grid.innerHTML = "";
        const all = STATE.data?.outfit_presets || [];
        const q = outfitQuery.trim().toLowerCase();
        const list = all.filter((p) => {
            if (outfitSrc !== "all" && p.src !== outfitSrc) return false;
            if (outfitGroup !== "all" && p.g !== outfitGroup) return false;
            if (!q) return true;
            // ⚠️ 搜索范围必须包含**分组名**：游戏 COS 的预设名是「皇家·海军制服」，
            //    标签里也没有「碧蓝」，用户搜「碧蓝」本来一个都搜不到（实测 0 张）。
            const hay = `${p.zh} ${p.en} ${(p.tags || []).join(" ")} `
                + `${groupHaystack()[p.g] || ""} ${p.g || ""}`.toLowerCase();
            return hay.includes(q);
        });
        if (!list.length) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "没有匹配的服装预设" }));
            return;
        }
        const frag = document.createDocumentFragment();
        const shown = list.slice(0, CARD_LIMIT);
        for (const p of shown) {
            frag.appendChild(makeOutfitCard(p));
        }
        grid.appendChild(frag);
        appendMoreHint(list.length - shown.length, () => { /* 用搜索/分组收窄 */ });
        if (currentPreset && currentPreset.id === "__from_widget__") {
            grid.appendChild(el("div", {
                width: "100%", fontSize: "11px", color: THEME.dim, marginTop: "6px",
            }, { textContent: `当前生效的预设：${currentPreset.zh}（点上方提示条可取消）` }));
        }
    }

    function makeOutfitCard(p) {
        const on = currentPreset?.zh === p.zh;
        const color = on ? THEME.outfit : (RATING_COLORS[p.r] || THEME.dim);
        const card = el("button", {
            width: showThumbs() ? "264px" : "248px", padding: "7px 8px", borderRadius: "9px",
            cursor: "pointer", textAlign: "left", display: "flex", gap: "8px",
            alignItems: "stretch",
            border: `1px solid ${on ? THEME.outfit : THEME.line}`,
            background: on ? "rgba(232,121,249,0.16)" : THEME.panel2,
            color: THEME.text,
        });
        if (showThumbs()) {
            card.appendChild(makeThumb(p.preview, { width: 84, height: 126 }));
        }
        const body = el("div", {
            display: "flex", flexDirection: "column", gap: "3px",
            minWidth: "0", flex: "1",
        });
        const title = el("div", {
            display: "flex", alignItems: "center", gap: "4px",
            fontSize: "12.5px", fontWeight: "600",
            color: on ? THEME.outfit : THEME.text,
        });
        if (p.lock) title.appendChild(el("span", { fontSize: "11px" }, { textContent: "🔒" }));
        const titleText = p.src === "import" ? p.en : p.zh;
        title.appendChild(el("span", {
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }, { textContent: titleText, title: titleText }));
        body.appendChild(title);
        body.appendChild(el("div", {
            fontSize: "10px", color: THEME.dim,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }, {
            textContent: p.src === "import"
                ? `${p.zh} · ${p.tags.length}标签 · 服装库`
                : `${p.tags.length} 标签 · ${p.lock ? "锁定角色" : "仅服装"}`,
        }));
        const preview = el("div", {
            fontSize: "10px", color: on ? THEME.outfit : THEME.dim,
            lineHeight: "1.35", maxHeight: showThumbs() ? "66px" : "30px",
            overflow: "hidden", fontFamily: "ui-monospace,Consolas,monospace",
            opacity: "0.9",
        }, { textContent: (p.tags || []).join(", ") });
        body.appendChild(preview);
        card.appendChild(body);
        card.title = `${p.zh} (${p.en})\n${(p.tags || []).join(", ")}`;
        card.onclick = () => applyPresetOutfit(p);
        // 标记「当前套用的那一套」，方便滚动定位 / 视觉强调
        if (currentPreset && currentPreset.id === p.id) card.dataset.presetCurrent = "1";
        return card;
    }

    function renderPoseGrid() {
        grid.innerHTML = "";
        const all = STATE.data?.pose_presets || [];
        const q = poseQuery.trim().toLowerCase();
        const list = all.filter((p) => {
            if (poseGroup !== "all" && p.g !== poseGroup) return false;
            if (!q) return true;
            const hay = `${p.zh} ${p.en} ${(p.tags || []).join(" ")}`.toLowerCase();
            return hay.includes(q);
        });
        if (!list.length) {
            grid.appendChild(el("div", { color: THEME.dim, fontSize: "12px" },
                { textContent: "没有匹配的姿势参考" }));
            return;
        }
        const frag = document.createDocumentFragment();
        const shown = list.slice(0, CARD_LIMIT);
        for (const p of shown) {
            const on = currentPose?.zh === p.zh;
            const card = el("button", {
                width: showThumbs() ? "184px" : "200px", padding: "7px 8px",
                borderRadius: "9px", cursor: "pointer", textAlign: "left",
                display: "flex", flexDirection: "column", gap: "5px",
                border: `1px solid ${on ? THEME.pose : THEME.line}`,
                background: on ? THEME.poseSoft : THEME.panel2,
                color: THEME.text,
            });
            if (showThumbs()) {
                const thumb = makeThumb(p.preview, { width: 166, height: 150 });
                thumb.style.width = "100%";
                card.appendChild(thumb);
            }
            const title = el("div", {
                display: "flex", alignItems: "center", gap: "4px",
                fontSize: "12px", fontWeight: "600",
                color: on ? THEME.pose : THEME.text,
            });
            const t = p.en || p.zh;
            title.appendChild(el("span", {
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: t, title: t }));
            card.appendChild(title);
            card.appendChild(el("div", {
                fontSize: "10px", color: THEME.dim,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }, { textContent: `${p.zh} · ${p.tags.length}标签` }));
            const tags = el("div", {
                fontSize: "10px", color: on ? THEME.pose : THEME.dim,
                lineHeight: "1.32", maxHeight: "26px", overflow: "hidden",
                fontFamily: "ui-monospace,Consolas,monospace", opacity: "0.9",
            }, { textContent: (p.tags || []).join(", ") });
            card.appendChild(tags);
            card.title = `${p.zh} (${p.en})\n${(p.tags || []).join(", ")}`;
            card.onclick = () => applyPosePreset(p);
            frag.appendChild(card);
        }
        grid.appendChild(frag);
        appendMoreHint(list.length - shown.length, () => { /* 用搜索/分组收窄 */ });
        if (currentPose && currentPose.id === "__from_widget__") {
            grid.appendChild(el("div", {
                width: "100%", fontSize: "11px", color: THEME.dim, marginTop: "6px",
            }, { textContent: `当前生效的姿势参考：${currentPose.zh}（点上方提示条可取消）` }));
        }
    }

    function appendMoreHint(hidden, _onMore) {
        if (hidden <= 0) return;
        grid.appendChild(el("div", {
            width: "100%", fontSize: "11px", color: THEME.dim, marginTop: "2px",
        }, {
            textContent: `另有 ${hidden} 张卡片未渲染（避免一次性建太多 DOM）——`
                + `用上面的分组或搜索框收窄即可看到。`,
        }));
    }

    let committed = false;
    function commit(fromPanel) {
        if (committed) return;
        committed = true;
        // 收尾：断开布局监听，避免面板关掉后还占着 ResizeObserver / resize 回调
        try { overlay.__animansfwRO?.disconnect?.(); } catch (e) { /* ignore */ }
        try {
            if (typeof window.removeEventListener === "function") {
                window.removeEventListener("resize", applyResponsiveLayout);
            }
        } catch (e) { /* ignore */ }
        writeTags(node, joinTags(order));
        // 种子：先写本节点控件，再推给下游采样器
        const smw = findWidget(node, "seed_mode");
        if (smw) smw.value = seedMode;
        if (seedMode === "每次随机") {
            seedValue = randomSeed();
            seedInput.value = String(seedValue);
        }
        const sdw = findWidget(node, "seed");
        if (sdw) sdw.value = seedValue;
        const seedRes = applySeedToGraph(node, seedMode, seedValue);
        const w = findWidget(node, "intensity");
        if (w) w.value = activeIntensity;
        const pw = findWidget(node, "outfit_preset");
        if (pw) pw.value = currentPreset ? encodeOutfitPreset(currentPreset) : "";
        const qw = findWidget(node, "pose_preset");
        if (qw) qw.value = currentPose ? encodeOutfitPreset(currentPose) : "";
        refreshPreview(node, true).catch(() => {});
        if (fromPanel && seedRes.count) {
            toast(`种子已应用：${seedMode}${seedMode === "固定（每次同图）" ? " " + seedValue : ""}`
                + `（${seedRes.names.join(", ")}）`);
        }
        closePanel();
    }

    // ---- 事件 ----
    // 搜索防抖 160ms：快速打字时不用每个按键都把网格重建一遍
    let searchTimer = 0;
    search.addEventListener("input", () => {
        query = search.value;            // 立刻记下来，预览/统计用的是最新值
        clearTimeout(searchTimer);
        searchTimer = setTimeout(renderGrid, 160);
    });
    overlay.addEventListener("keydown", (e) => {
        if (e.key === "Escape") commit(true);
    });
    document.addEventListener("keydown", onEsc);
    function onEsc(e) {
        if (e.key === "Escape") {
            document.removeEventListener("keydown", onEsc);
            commit(true);
        }
    }

    buildTextInputs(footer, node, sync);
    syncCatButtons();
    // 窄面板布局（侧栏横到顶部）—— 必须放在这里：它引用 catList / workList，
    // 那两个 `const` 在上面才创建好（提前调用会 TDZ 报错）。
    applyResponsiveLayout();
    // ⚠️ 必须在这里先建好动作/视角快速条：sync() → renderGrid() → renderSelected()
    //    里会调 paintQuickRow()，晚建的话 chip 的选中态第一次同步不上。
    renderActViewRow();
    renderSelected();
    renderGrid();
    wireOutfitView();
    sync();
    // 预取角色库（侧栏「游戏/作品」要靠它算每个作品的角色数）。
    // 必须在 buildPanel 作用域内调用 —— loadChars 是本函数的内部函数。
    // ⚠️ 但要**等首屏渲染完再取**：角色库有 1.7 MB，开面板时立刻去拉会和
    //    标签库抢带宽和主线程（解析 + 建索引），首屏明显变慢。
    //    用 requestIdleCallback 推到浏览器空闲时；老前端没有就退回定时器。
    const prefetchChars = () => loadChars().catch(() => {});
    if (typeof requestIdleCallback === "function") {
        requestIdleCallback(prefetchChars, { timeout: 2500 });
    } else {
        setTimeout(prefetchChars, 400);
    }
    // 让侧栏/网格按节点上已有的 mode 值渲染
    applyMode(mode, true);
    // 缩略图缓存统计（按钮上显示"已缓存 N 张"）。放在最后，
    // 不跟首屏抢带宽 —— 它只是个头部的数字。
    refreshCacheStats();
    setTimeout(() => search.focus(), 40);
    return overlay;
}

function buildTextInputs(container, node, onChange) {
    const row = el("div", {
        display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "flex-end",
    });
    container.insertBefore(row, container.firstChild);

    const add = (label, widgetName, width, placeholder, multiline) => {
        const wrap = el("div", { display: "flex", flexDirection: "column", gap: "3px", width });
        wrap.appendChild(el("span", { fontSize: "10px", color: THEME.dim }, { textContent: label }));
        const input = multiline
            ? el("textarea", {
                height: "38px", resize: "vertical", padding: "4px 6px", borderRadius: "5px",
                border: `1px solid ${THEME.line}`, background: THEME.panel2, color: THEME.text,
                fontSize: "11px", outline: "none", fontFamily: "inherit",
            })
            : el("input", {
                padding: "4px 6px", borderRadius: "5px",
                border: `1px solid ${THEME.line}`, background: THEME.panel2, color: THEME.text,
                fontSize: "11px", outline: "none",
            });
        input.placeholder = placeholder || "";
        const w = findWidget(node, widgetName);
        input.value = String(w?.value ?? "");
        input.addEventListener("input", () => {
            if (w) {
                w.value = input.value;
                node.setDirtyCanvas?.(true, true);
            }
            onChange?.();
        });
        wrap.appendChild(input);
        row.appendChild(wrap);
    };

    add("前置（质量词之后 / 触发词）", "extra_front", "26%", "可留空，例如 LoRA 触发词、画师名", true);
    add("后置（提示词最后）", "extra_tail", "22%", "可留空", true);
    add("自定义描述（留空=自动）", "caption_text", "30%", "留空则由标签自动生成自然语言描述", true);
    add("描述种子", "caption_seed", "10%", "0", false);

    // 保存按钮：把当前节点里的内容一键存进「我的」
    const saveRow = el("div", {
        display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center",
        marginTop: "6px",
    });
    container.insertBefore(saveRow, row.nextSibling);
    saveRow.appendChild(el("span", { fontSize: "10px", color: THEME.dim },
        { textContent: "存进「我的」：" }));

    const mkSave = (label, color, make) => {
        const b = el("button", {
            padding: "3px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "11px",
            border: `1px solid ${color}77`, background: `${color}22`, color: color,
        }, { textContent: label });
        b.onclick = () => {
            PENDING_PREFILL = make() || {};
            openCustomEditor(PENDING_PREFILL.kind || "trigger", null);
        };
        return b;
    };

    saveRow.appendChild(mkSave("🔑 存为触发词", CUSTOM_META.trigger.color, () => {
        const w = findWidget(node, "extra_front");
        const v = String(w?.value || "").trim();
        return { kind: "trigger", name: v ? v.split(",")[0].trim().slice(0, 20) : "我的触发词",
                 trigger: v, tags: v };
    }));
    saveRow.appendChild(mkSave("🧑 存为角色", CUSTOM_META.character.color, () => {
        const cur = readTags(node);
        const first = cur.split(",")[0].trim();
        return { kind: "character", name: first || "我的角色",
                 trigger: first, tags: cur };
    }));

    const importBtn = el("button", {
        padding: "3px 10px", borderRadius: "6px", cursor: "pointer", fontSize: "11px",
        border: `1px solid ${THEME.line}`, background: THEME.panel2, color: THEME.text,
    }, { textContent: "📂 导入自定义库" });
    importBtn.onclick = () => importCustomLibrary();
    saveRow.appendChild(importBtn);
}

// 强度档位一键铺底用的套件
const INTENSITY_BUNDLES = {
    soft: ["1girl", "solo", "blush", "looking at viewer", "large breasts", "cleavage",
           "lingerie", "upper body", "soft lighting", "detailed skin"],
    hard: ["1girl, 1boy", "sex", "missionary", "nude", "large breasts", "nipples",
           "pussy", "blush", "sweat", "ahegao", "cum", "on bed", "close-up",
           "best quality", "absurdres", "explicit", "uncensored"],
    extreme: ["1girl, 2boys", "gangbang", "double penetration", "ahegao", "rolling eyes",
              "tongue out", "drooling", "excessive cum", "cum overflow", "squirting",
              "bondage", "rope", "collar", "crotch focus", "best quality", "absurdres",
              "explicit", "uncensored"],
};

// ---------------------------------------------------------------------------
// 扩展注册
// ---------------------------------------------------------------------------

app.registerExtension({
    name: "AnimaNsfwPanel.extension",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== BUILDER_NODE && nodeData.name !== NEGATIVE_NODE) return;

        const origOnCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origOnCreated?.apply(this, arguments);
            try {
                if (nodeData.name === BUILDER_NODE) setupBuilder(this);
                else setupNegative(this);
            } catch (e) {
                console.error("[AnimaNSFW] 节点初始化失败", e);
            }
            return r;
        };

        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origOnConfigure?.apply(this, arguments);
            try {
                if (nodeData.name === BUILDER_NODE) {
                    ensurePreviewWidget(this);
                    schedulePreview(this, 400);
                }
            } catch (e) { /* ignore */ }
            return r;
        };

        if (nodeData.name === BUILDER_NODE) {
            const origOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                origOnExecuted?.apply(this, arguments);
                const payload = message?.animansfw_preview?.[0];
                if (payload && typeof payload === "object") {
                    this.__animansfwPreview = { positive: payload.positive, info: payload };
                    renderPreviewWidget(this);
                }
            };
        }
    },
});

function setupBuilder(node) {
    hideWidget(findWidget(node, "tags"));
    hideWidget(findWidget(node, "caption_text"));
    hideWidget(findWidget(node, "extra_front"));
    hideWidget(findWidget(node, "extra_tail"));
    // outfit_preset / pose_preset 故意保持可见：面板选了什么套装能直接看到，也能手改
    const pw = findWidget(node, "outfit_preset");
    if (pw) {
        pw.label = "服装预设";
        if (pw.value === undefined || pw.value === null) pw.value = "";
    }
    const qw = findWidget(node, "pose_preset");
    if (qw) {
        qw.label = "姿势参考";
        if (qw.value === undefined || qw.value === null) qw.value = "";
    }

    ensurePreviewWidget(node);

    const btn = node.addWidget("button", "🎛 打开 NSFW 面板", null, () => openPanel(node));
    btn.serialize = false;
    btn.options = btn.options || {};
    btn.options.serialize = false;
    styleButton(btn, THEME.accent, THEME.accentSoft);

    const refresh = node.addWidget("button", "↻ 仅刷新预览", null, () => {
        refreshPreview(node, true).catch((e) => alert(e.message));
    });
    refresh.serialize = false;
    // ⚠️ 老前端（1.12.x）的 addWidget 不一定带 options 字段，
    //    直接写 refresh.options.serialize 会抛 TypeError
    refresh.options = refresh.options || {};
    refresh.options.serialize = false;
    styleButton(refresh, "#38bdf8", "rgba(56,189,248,0.14)");

    // 面板外改动（例如手动贴字符串）也要刷新预览
    for (const name of ["intensity", "quality_preset", "caption_enabled", "sort_tags", "caption_seed"]) {
        const w = findWidget(node, name);
        if (!w || w.__animansfwHooked) continue;
        w.__animansfwHooked = true;
        const orig = w.callback;
        w.callback = function () {
            const r = orig?.apply(this, arguments);
            schedulePreview(node);
            return r;
        };
    }

    raf(() => {
        try {
            node.setSize?.([Math.max(node.size?.[0] || 0, 430), node.size?.[1] || 320]);
            node.setDirtyCanvas?.(true, true);
            schedulePreview(node, 600);
        } catch (e) { /* 规模/尺寸调整失败不影响使用 */ }
    });
}

function setupNegative(node) {
    hideWidget(findWidget(node, "extra_text"));
    const btn = node.addWidget("button", "📋 一键填满 NSFW 常用负面", null, () => {
        for (const name of ["手部修复", "面部修复", "人体结构", "NSFW 安全", "防伪影"]) {
            const w = findWidget(node, name);
            if (w) w.value = true;
        }
        const base = findWidget(node, "base_enabled");
        if (base) base.value = true;
        const extra = findWidget(node, "extra_text");
        if (extra && !String(extra.value || "").trim()) {
            extra.value = "extra digits, fewer digits, poorly drawn hands, "
                + "asymmetrical eyes, bad proportions";
        }
        node.setDirtyCanvas?.(true, true);
    });
    btn.serialize = false;
    btn.options = btn.options || {};
    btn.options.serialize = false;
    styleButton(btn, "#a78bfa", "rgba(167,139,250,0.16)");
}

function styleButton(widget, color, bg) {
    if (!widget) return;
    widget.label = widget.name;
    widget.computeSize = (width) => [width, 28];
    // 完全接管绘制：ComfyUI 的按钮默认绘制会画标签，叠加自己的绘制会重影。
    widget.draw = function (ctx, node, widgetWidth, y, widgetHeight) {
        try {
            ctx.save();
            const m = 6;
            ctx.fillStyle = bg;
            roundRect(ctx, m, y + 2, widgetWidth - m * 2, widgetHeight - 4, 6);
            ctx.fill();
            ctx.strokeStyle = color + "88";
            ctx.lineWidth = 1;
            roundRect(ctx, m, y + 2, widgetWidth - m * 2, widgetHeight - 4, 6);
            ctx.stroke();
            ctx.fillStyle = color;
            ctx.font = "600 12px 'Segoe UI','Microsoft YaHei',sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(this.label || this.name, widgetWidth / 2, y + widgetHeight / 2 + 1);
            ctx.restore();
        } catch (e) { /* ignore */ }
    };
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// 预取标签库，缩短第一次打开面板的等待。
// ⚠️ 这里只能调模块级函数。loadChars / loadCustom 定义在 buildPanel / 面板作用域内，
//    在模块作用域调用会抛 ReferenceError，导致整个扩展注册失败、
//    节点上的「打开面板」按钮点了没反应。
loadTagData().catch(() => {});
