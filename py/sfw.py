# -*- coding: utf-8 -*-
"""SFW 模式：一个节点两用（NSFW / SFW）。

思路：**不靠 rating（分级）判**。分级太粗 —— `school swimsuit`、
`black thighhighs`、`leotard` 都被标成 hard，但它们是正常服装；
反过来 `nipples`、`covered nipples` 是 soft，却显然不该出现在 SFW 里。

所以这里用**两层判据**：

1. ``BLOCK`` —— 显式露骨词表（性行为 / 性器官 / 体液 / 束缚 / 裸露 / 泳装内衣等）
   命中即拦下。这是主判据，`ALLOW` 可以豁免其中的例外。
2. ``ALLOW`` —— 服装白名单。泳装、内衣、thighhighs 这类**具体单品**：
   只有在 SFW 模式下**由预设自动带进来**才豁免（芭蕾的 leotard 要留着），
   用户如果自己在 NSFW 分类里手点，仍会被拦下。

SFW 模式下还会：

- 追加 ``SFW_QUALITY``（``rating:safe, safe, general``）—— 这是 booru / Anima
  系模型最强的一道保险，从训练数据分布上把画面推向全年龄
- 用 ``NEGATIVE_SFW`` 替换「NSFW 安全」那段负面词
- 在自然语言描述里换成 SFW 的收尾句式，不提身体局部与情色氛围
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# 模式
# ---------------------------------------------------------------------------
MODE_NSFW = "NSFW（不限）"
MODE_SFW = "SFW（全年龄）"
MODES = (MODE_NSFW, MODE_SFW)

# ⚠️ 注意 "nsfw" 里**包含** "sfw" 子串，所以不能用 `"sfw" in s` 判断
#    （早期版本这么写，结果 NSFW 也被当成 SFW）。这里改成：
#    先看有没有明确的 NSFW 标记，再看 SFW 标记。
_NSFW_HINTS = ("nsfw", "not safe", "r18", "r-18", "18+", "成人", "不限")
_SFW_HINTS = ("sfw", "safe", "全年龄", "安全", "一般向")


def is_sfw(mode: object) -> bool:
    s = str(mode or "").strip().lower()
    if not s:
        return False
    if any(h in s for h in _NSFW_HINTS):
        return False
    return any(h in s for h in _SFW_HINTS)


# ---------------------------------------------------------------------------
# 显式露骨词表（命中即拦下）
# ---------------------------------------------------------------------------
BLOCK: Set[str] = set()

# 性行为 / 体位
# ⚠️ `nsfw` 本身也要拦 —— 它是 booru 上的"少儿不宜"标记，留着会直接推翻 SFW 意图
BLOCK |= {"nsfw", "explicit", "questionable", "r-18", "r18", "adult content"}

BLOCK |= {
    "sex", "vaginal", "anal", "anal sex", "oral", "fellatio", "blowjob",
    "deepthroat", "irrumatio", "cunnilingus", "licking penis", "licking pussy",
    "licking nipple", "69", "face sitting", "missionary", "cowgirl position",
    "reverse cowgirl position", "girl on top", "boy on top", "doggystyle",
    "sex from behind", "standing sex", "suspended congress", "spooning",
    "mating press", "full nelson", "paizuri", "titjob", "handjob", "fingering",
    "fingering herself", "finger in pussy", "penetration", "double penetration",
    "gangbang", "threesome", "group sex", "orgy", "bukkake", "facial",
    "cum", "cumshot", "creampie", "cum in pussy", "cum in ass", "cum on body",
    "cum on stomach", "cum on back", "cum on hair", "cum on face", "cum on breasts",
    "excessive cum", "cum overflow", "cum pool", "cum string", "precum",
    "squirting", "female ejaculation", "orgasm", "climax", "afterglow",
    "pussy juice", "saliva", "spit", "drooling", "excessive saliva",
    "tentacle sex", "tentacles", "bestiality", "rape", "netorare", "ntr",
    "lactation", "milking", "pregnant", "impregnation", "oviposition",
    "ahegao", "rolling eyes", "empty eyes", "heart-shaped pupils",
    "futanari", "futa", "dickgirl", "shemale", "trap", "gender bender",
    "spread legs", "spread pussy", "legs up", "m legs", "presenting",
    "presenting anus", "presenting pussy", "inviting",
}

# 性器官 / 裸露
BLOCK |= {
    "nude", "completely nude", "naked", "topless", "bottomless", "undressing",
    "no panties", "no bra", "panties", "bra", "lingerie", "underwear",
    "underboob", "sideboob", "downblouse", "upskirt", "panty pull", "panty lift",
    "pussy", "pussies", "anus", "asshole", "penis", "testicles", "balls",
    "nipples", "covered nipples", "areola", "areola slip", "nipple slip",
    "cleavage", "breasts curtain", "breasts out", "breast hold", "grabbing own breast",
    "clit", "clitoris", "clit stimulation", "nipple stimulation", "pubic hair",
    "crotch", "crotch focus", "crotchless", "crotchless panties",
    "crotchless pantyhose", "pasties", "see-through", "transparent clothing",
    "wet clothes", "wet shirt", "nipple", "pelvic curtain", "clothing aside",
    "clothes pull", "clothes lift", "shirt lift", "skirt lift", "dress lift",
    "torn clothes", "torn clothes", "breast slip", "wardrobe malfunction",
    "vibrator", "sex toy", "dildo", "anal beads", "onahole", "condom",
    "used condom", "sex machine", "hitachi magic wand", "magic wand",
    "hand between legs", "touching self", "masturbating", "masturbation",
    "grabbing own breast", "biting lip",
}

# 束缚 / BDSM。⚠️ 这里只放**明确的束缚道具**，不放 corset / choker / fishnet /
# stockings / leather —— 那些是正常服装（哥特、朋克、女仆装都在用），
# 早期版本把它们放进来会把大量服装预设误杀。
BLOCK |= {
    "bondage", "bdsm", "shibari", "rope", "ropes", "restrained", "bound",
    "bound wrists", "bound ankles", "hogtie", "suspension", "spreader bar",
    "handcuffs", "leash", "chain leash", "blindfold", "gag",
    "ball gag", "ring gag", "tape gag", "chastity belt", "collar and leash",
    "whip", "paddle", "riding crop", "clamps", "nipple clamps",
    "latex", "latex gloves", "latex boots", "spiked collar", "o-ring",
    "cuff", "cuffs", "sex dungeon", "glory hole",
}

# 泳装 / 内衣（作为"服装类别"整体拦下）
BLOCK |= {
    "swimsuit", "school swimsuit", "one-piece swimsuit", "competition swimsuit",
    "bikini", "micro bikini", "white bikini", "black bikini", "red bikini",
    "side-tie bikini bottom", "bikini under clothes", "bikini skirt",
    "sports bra", "briefs", "boxer briefs", "thong", "g-string",
    "babydoll", "chemise", "negligee", "nightgown", "sleepwear", "pajamas",
    "bunny suit", "playboy bunny", "bunny girl", "cat lingerie", "santa lingerie",
    "highleg leotard", "highleg", "highleg briefs",
    "bikini armor", "micro bikini", "slingshot swimsuit",
}

# 场景 / 氛围
BLOCK |= {
    "love hotel", "brothel", "strip club", "messy bed", "used bed",
    "after sex", "post-coital", "bedroom eyes", "seductive smile",
    "public restroom",
}

# ---------------------------------------------------------------------------
# 服装白名单：这些是"正常服装单品"，SFW 下如果由预设带进来就豁免
# ---------------------------------------------------------------------------
ALLOW: Set[str] = {
    "leotard", "leotards", "ballet", "tutu", "swim cap", "goggles",
    "thighhighs", "black thighhighs", "white thighhighs", "thighhigh boots",
    "pantyhose", "black pantyhose", "white pantyhose", "tights",
    "stockings", "black stockings", "white stockings",
    "gym uniform", "bloomers", "school uniform", "serafuku", "sailor dress",
    "cheerleader", "sports bra", "bike shorts", "tracksuit",
    "corset", "corset dress", "choker", "necklace", "garter belt",
    "fishnet", "fishnet stockings", "leather", "shiny clothes",
    "maid", "waitress", "nurse", "nurse cap", "police uniform", "office lady",
    "wedding dress", "hanfu", "kimono", "yukata", "qipao", "cheongsam",
    "shrine maiden", "miko", "witch hat", "magical girl", "idol",
    "shower", "bathtub", "onsen", "hot spring", "sauna", "changing room",
    "locker room", "spanking",
}

# ---------------------------------------------------------------------------
# SFW 补充：正向质量/安全词 + 负面词
# ---------------------------------------------------------------------------
SFW_QUALITY = "rating:safe, safe, general"

NEGATIVE_SFW = (
    "nsfw, explicit, nude, naked, topless, bottomless, nipples, pussy, penis, "
    "sex, cum, cumshot, creampie, ahegao, bondage, blood, gore, violence, "
    "weapon pointed at viewer, provocative pose"
)

# 自然语言描述的 SFW 收尾（替换掉原先生理/情色向的句子）
SFW_TAIL = [
    "The overall mood stays light and wholesome.",
    "Nothing in the frame goes beyond an all-ages illustration.",
    "The composition keeps the subject fully and modestly dressed.",
    "The scene reads as an everyday, family-friendly moment.",
]

SFW_SOLO_TAIL = [
    "She is alone in frame, and the composition leans on her posture and expression.",
    "The image is a single-subject study with an all-ages feel.",
    "The mood stays cheerful and modest throughout.",
]


# ---------------------------------------------------------------------------
# 分类建议：前端据此把整个分类从侧栏收起来
# ---------------------------------------------------------------------------
# 注意：`outfit` / `body` / `scene` / `face` 里有大量正常标签，不能整类收起，
# 只把「性行为 / 前戏 / 自慰 / 体液」这几类整体隐藏。
HIDDEN_CATEGORIES_IN_SFW = ("act", "foreplay", "solo", "fluid")


def blocked(token: str, allow: Optional[Iterable[str]] = None) -> bool:
    """这个标签在 SFW 模式下是否该被拦下。

    ``allow`` 传入「豁免来源」—— 由预设自动带进来的标签会带上豁免资格。
    """
    key = str(token or "").strip().lower().replace("_", " ")
    if not key:
        return False
    if key.startswith("char_lock:"):
        key = key.split(":", 1)[1]
    allow_set = ALLOW if allow is None else set(allow)
    if key in allow_set:
        return False
    return key in BLOCK


def filter_tokens(tokens: Sequence[str],
                  preset_tokens: Sequence[str] = ()) -> Tuple[List[str], List[str]]:
    """SFW 过滤。返回 ``(保留, 被拦下)``。

    ``preset_tokens`` 里的标签享有白名单豁免 —— 用户选了「芭蕾舞服」，
    预设带的 ``leotard`` 要留着；但用户自己去点 ``leotard`` 就会被拦。
    """
    preset_keys = {str(t).strip().lower().replace("_", " ") for t in preset_tokens}
    preset_keys = {k.split(":", 1)[1] if k.startswith("char_lock:") else k
                   for k in preset_keys}
    kept, dropped = [], []
    for tok in tokens:
        key = str(tok).strip().lower().replace("_", " ")
        bare = key.split(":", 1)[1] if key.startswith("char_lock:") else key
        if bare not in BLOCK:
            kept.append(tok)
        elif bare in preset_keys and bare in ALLOW:
            kept.append(tok)          # 预设带的正常服装单品，豁免
        else:
            dropped.append(tok)
    return kept, dropped


def counts() -> Dict[str, int]:
    return {
        "block": len(BLOCK),
        "allow": len(ALLOW),
        "hidden_categories": len(HIDDEN_CATEGORIES_IN_SFW),
    }
