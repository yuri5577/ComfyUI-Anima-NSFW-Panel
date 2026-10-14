# -*- coding: utf-8 -*-
"""Anima NSFW 提示词合成核心逻辑。

被 ``nodes.py``（节点执行）和 ``api.py``（实时预览）共用，保证面板里看到的预览
和实际送进采样器的一致。

Anima 的写作习惯（参考官方 Base v1 教程与 Anima prompt grammar）：

    正面：质量标签 → 角色数量 → 身份/外观 → 姿势动作 → 构图 → 场景 → 光照 →
          风格 → 最后一段自然语言描述
    负面：worst quality, ... 这类安全 + 人体修复词

因此本模块把「逗号标签」与「自然语言描述」严格分开：标签做去重 / 互斥约束 /
强度过滤，描述段落单独生成再拼到末尾。
"""

from __future__ import annotations

import random
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .sfw import (
    MODE_NSFW,
    MODE_SFW,
    NEGATIVE_SFW,
    SFW_QUALITY,
    SFW_SOLO_TAIL,
    SFW_TAIL,
    is_sfw,
)
from .sfw import filter_tokens as _sfw_filter
from .tags import (LOCKED_CHARACTERS, NEGATIVE_BASE, NEGATIVE_EXTRA,
                    QUALITY_PRESETS, TAG_INDEX)

# ---------------------------------------------------------------------------
# 标签清洗
# ---------------------------------------------------------------------------

_PAREN_WEIGHT = re.compile(r"^\((.*):\s*[0-9.]+\)$")


def strip_weight(token: str) -> str:
    """去掉 ``(tag:1.2)`` 形式的权重包装，只留下标签本体。"""
    token = token.strip()
    m = _PAREN_WEIGHT.match(token)
    if m:
        return m.group(1).strip()
    if token.startswith("(") and token.endswith(")") and ":" not in token:
        return token[1:-1].strip()
    return token


def normalize_token(token: str) -> str:
    token = strip_weight(token)
    # ⚠️ 先把内部标记前缀保护起来：它们含下划线，而下面的规范化会把下划线换成
    #    空格 —— "char_lock:asuna" 会变成 "char lock:asuna"、
    #    "char_anchor:1boy" 会变成 "char anchor:1boy"，
    #    前缀失效、互斥组也认不出，最后这串垃圾文本还会进提示词。
    #    实测两种都踩过（char_lock 那次导致整张全黑）。
    _PREFIXES = (CHAR_LOCK_PREFIX, CHAR_ANCHOR_PREFIX)
    hit = None
    low = token.lower()
    for pre in _PREFIXES:
        if low.startswith(pre):
            hit = pre
            break
    if hit:
        token = token[len(hit):]
    token = token.replace("_", " ").strip().strip(",")
    token = re.sub(r"\s+", " ", token)
    if hit and token:
        token = hit + token
    return token


def split_tokens(raw: str) -> List[str]:
    """兼容中英文逗号、顿号、换行的切分。"""
    if not raw:
        return []
    parts = re.split(r"[,，、\n]+", str(raw))
    return [normalize_token(p) for p in parts if normalize_token(p)]


def rank_of(tag: str) -> int:
    """标签在 Anima 提示词里的推荐顺序（越小越靠前）。

    姿势预设走单独一档：Anima 语法里「外观 → 姿势 → 动作」，
    所以姿势词排在身体之后、性交动作之前。
    """
    cat = (TAG_INDEX.get(tag.lower()) or {}).get("c")
    order = {
        "style": 0,
        "subject": 1,
        "outfit": 2,
        "body": 3,
        "pose": 4,
        "act": 5,
        "foreplay": 6,
        "solo": 6,
        "prop": 7,
        "fluid": 8,
        "face": 8,
        "scene": 9,
    }
    return order.get(cat, 7)


def dedupe(tokens: Iterable[str]) -> List[str]:
    """去重：忽略大小写与下划线/空格差异，保留首次出现的写法。"""
    seen = {}
    out = []
    for t in tokens:
        s = str(t).strip()
        # ⚠️ 两点都很重要：
        #   1. 必须 strip —— 预设标签和用户标签可能只差一个尾随空格
        #   2. 带 char_lock: 前缀的，要拿**去掉前缀**的部分做键，
        #      否则「锁定预设的第一个标签」和「用户手里的同一个标签」
        #      会被当成两个，前缀一剥就出现重复标签（实测出现过）
        key = s.lower()
        if key.startswith(CHAR_LOCK_PREFIX):
            key = key[len(CHAR_LOCK_PREFIX):]
        key = re.sub(r"\s+", " ", key.replace("_", " ")).strip()
        if not key or key in seen:
            continue
        seen[key] = True
        out.append(s)
    return out


def enforce_groups(tokens: Sequence[str]) -> Tuple[List[str], List[str]]:
    """互斥组约束：同一组只保留最后一个（即用户最近点的那个）。

    返回 ``(保留的标签, 被移除的标签)``。

    角色锁定有两重保障：
      1. 标签本身在角色库索引里（``character_base`` 组）—— 主要机制，
         因为角色库有 8000 个角色，覆盖了绝大多情况
      2. 内部标记 ``char_lock:`` 前缀（面板套用「锁定角色」预设时写入）
         —— 兜底，用于角色库里没有、但预设里锁定的角色名
    """
    group_of: Dict[int, str] = {}
    for idx, tok in enumerate(tokens):
        low = tok.lower()
        info = TAG_INDEX.get(low)
        if low.startswith(CHAR_LOCK_PREFIX):
            group_of[idx] = "char_lock"
        elif info and info.get("g"):
            group_of[idx] = info["g"]
        elif low in LOCKED_CHARACTERS:
            # 角色库里没有、但预设锁定的角色名
            group_of[idx] = "character_base"

    last_in_group: Dict[str, int] = {}
    for idx, grp in group_of.items():
        last_in_group[grp] = idx

    # 性别锚点：只看**带标记的**那个。
    # ⚠️ 不要去"猜"角色的 count 标签 —— 角色名（character_base 组）和它的
    #    `1boy`（count 组）是两个独立 token，从 `1boy` 本身看不出它是不是角色带来的。
    #    实测那种猜法对「角色名在前、锚点在后」的顺序完全失效。
    #    所以由前端在「补齐推荐标签」时打上 char_anchor: 前缀（见面板 JS）。
    anchor_idx = None
    for idx, tok in enumerate(tokens):
        if tok.lower().startswith(CHAR_ANCHOR_PREFIX):
            anchor_idx = idx
            group_of[idx] = "count"
    if anchor_idx is not None:
        # 让这个索引成为 count 组唯一保留项
        for idx in list(group_of):
            if idx != anchor_idx and group_of[idx] == "count":
                group_of[idx] = "count_overridden"
        last_in_group["count"] = anchor_idx
        last_in_group["count_overridden"] = anchor_idx + 1000000


    dropped = []
    kept = []
    for idx, tok in enumerate(tokens):
        grp = group_of.get(idx)
        if grp is not None and last_in_group.get(grp) != idx:
            dropped.append(tok)
        else:
            kept.append(tok)
    return kept, dropped


# 角色锁定前缀：面板里「锁定」类服装预设的英文触发词会带这个前缀，
# 它在提示词里只用于标记互斥与回溯，实际发出去前会被剥掉。
CHAR_LOCK_PREFIX = "char_lock:"

# 角色带来的**性别锚点**标记。`1girl` / `1boy` / `2girls` … 全在互斥组 `count`
# 里只保留最后一个，而面板默认标签就有 `1girl` —— 男性角色（角色库标签是 `1boy`）
# 会被顶掉，出图画成女孩。用这个前缀把"这个锚点来自角色"标出来。
CHAR_ANCHOR_PREFIX = "char_anchor:"


def strip_char_lock(tokens: Sequence[str]) -> List[str]:
    """剥掉内部标记前缀（char_lock: / char_anchor:）—— 它们只用于互斥判定。"""
    out = []
    for t in tokens:
        low = str(t).lower()
        if low.startswith(CHAR_LOCK_PREFIX):
            out.append(str(t)[len(CHAR_LOCK_PREFIX):].strip())
        elif low.startswith(CHAR_ANCHOR_PREFIX):
            out.append(str(t)[len(CHAR_ANCHOR_PREFIX):].strip())
        else:
            out.append(t)
    return out


def preset_tags_to_tokens(tags: Sequence[str], locked: bool = False) -> List[str]:
    """把服装预设里的标签转成内部 token；锁定角色时给第一个标签加前缀。"""
    out = []
    for i, t in enumerate(tags):
        tok = normalize_token(t)
        if not tok:
            continue
        if locked and i == 0:
            tok = CHAR_LOCK_PREFIX + tok
        out.append(tok)
    return out


def filter_by_intensity(tokens: Sequence[str], intensity: str) -> Tuple[List[str], List[str]]:
    """按强度档位过滤：标签自带 lvl，高于当前档位的会被剔除。"""
    ceiling = {"soft": 1, "hard": 2, "extreme": 3}.get(str(intensity).lower(), 2)
    kept, dropped = [], []
    for tok in tokens:
        info = TAG_INDEX.get(tok.lower())
        lvl = int(info["lvl"]) if info else 0
        if lvl > ceiling:
            dropped.append(tok)
        else:
            kept.append(tok)
    return kept, dropped


def sort_tokens(tokens: Sequence[str], sort_tags: bool = True) -> List[str]:
    if not sort_tags:
        return list(tokens)
    return sorted(tokens, key=lambda t: (rank_of(t), tokens.index(t)))


# ---------------------------------------------------------------------------
# 自然语言描述生成
# ---------------------------------------------------------------------------

_CAPTION_TAIL = [
    "The pose is held with visible tension, and the framing keeps the whole gesture readable.",
    "Every line of the body reads as weight and heat rather than stiffness.",
    "The camera stays close enough that the smallest reactions carry the image.",
    "Light wraps the figures and keeps the mood intimate and deliberate.",
]

_SOLO_TAIL = [
    "She is alone in frame, and the composition leans on her body language.",
    "The image is a single-subject study, with attention on posture and expression.",
]

_SUBJECT_PHRASE = {
    "1girl": "A single young woman",
    "1boy": "A single young man",
    "solo": "A single figure",
    "2girls": "Two young women",
    "2boys": "Two young men",
    "1girl, 1boy": "A young woman and a young man",
    "1girl, 1boy, 1girl": "A young woman and a young man",
    "1futa": "A futanari figure",
    "1girl, 1futa": "A young woman and a futanari figure",
    "2futas": "Two futanari figures",
    "seated": "A seated figure",
}

_ACT_PHRASE = {
    "missionary": "in a missionary position",
    "cowgirl position": "riding on top",
    "reverse cowgirl position": "riding in reverse",
    "doggystyle": "taken from behind",
    "sex from behind": "held from behind",
    "standing sex": "standing and pressed together",
    "suspended congress": "lifted clear off the ground",
    "spooning": "lying on their sides",
    "mating press": "pinned down with legs folded back",
    "prone bone": "pressed flat onto the surface",
    "piledriver": "inverted with hips raised high",
    "full nelson": "locked in a full nelson",
    "anal": "in an anal scene",
    "vaginal": "joined in a vaginal scene",
    "gangbang": "surrounded by several partners",
    "threesome": "shared between three people",
    "orgy": "in a crowded group scene",
    "fellatio": "with lips wrapped around the shaft",
    "oral": "in an oral scene",
    "deepthroat": "taking it deep down the throat",
    "cunnilingus": "with a mouth pressed between her thighs",
    "paizuri": "cradled between her breasts",
    "handjob": "worked with one hand",
    "footjob": "held between her feet",
    "thigh sex": "clenched between her thighs",
    "masturbating": "touching herself",
    "fingering": "with fingers buried inside",
    "69": "in a mutual oral arrangement",
    "face sitting": "seated over a waiting mouth",
}

_FACE_PHRASE = {
    "ahegao": "her face is slack with overload, eyes rolled back",
    "rolling eyes": "her eyes have rolled back", 
    "tongue out": "her tongue lolls out",
    "drooling": "drool escapes the corner of her mouth",
    "tears": "tears gather at the corners of her eyes",
    "teary eyes": "her eyes shine wet",
    "blush": "a deep flush runs across her cheeks",
    "sweat": "sweat beads on her skin",
    "trembling": "she is trembling through the whole frame",
    "half-closed eyes": "her lids hang half closed",
    "heavy-lidded eyes": "her gaze is heavy and unfocused",
    "looking at viewer": "she looks straight into the camera",
    "looking back": "she glances back over her shoulder",
    "orgasm": "she is right at the edge of release",
    "ecstasy": "pleasure has taken over her expression",
    "mind break": "her expression has gone blank with overload",
    "expressionless": "her expression stays carefully blank",
    "naughty face": "her expression is openly lewd",
    "open mouth": "her lips stay parted",
    "moaning": "a low moan shapes her mouth",
}

_FLUID_PHRASE = {
    "cum": "cum catches the light on her skin",
    "creampie": "the aftermath is thick and evident",
    "cum in pussy": "the aftermath is thick and evident",
    "excessive cum": "far too much cum to stay contained",
    "cum on face": "cum streaks across her face",
    "cum on body": "cum is painted across her body",
    "cum overflow": "it overflows and runs down",
    "pussy juice": "wetness glistens between her thighs",
    "wet pussy": "wetness glistens between her thighs",
    "squirting": "a clear spray catches the light",
    "saliva": "saliva strings between them",
    "saliva trail": "a thin string of saliva connects them",
    "lactation": "milk beads at her nipples",
    "precum": "a bead of precum glistens at the tip",
}

_SCENE_PHRASE = {
    "on bed": "on a rumpled bed",
    "messy bed": "on sheets already pulled loose",
    "bedroom": "in a dim bedroom",
    "love hotel": "in a rented room",
    "bathroom": "in a tiled bathroom",
    "shower": "under running water",
    "bathtub": "half submerged in the tub",
    "onsen": "in a steaming hot spring",
    "classroom": "in an empty classroom",
    "office": "in a quiet office",
    "desk": "against a desk",
    "car": "in the confined space of a car",
    "backseat": "across the back seat",
    "against wall": "pressed up against a wall",
    "against glass": "flattened against glass",
    "mirror": "with a mirror catching the reflection",
    "outdoors": "out in the open air",
    "night": "under low night light",
    "dim lighting": "lit only dimly",
    "candlelight": "lit by candlelight",
    "neon lights": "cut by neon colour",
    "steam": "veiled in steam",
}

# 动作/姿势 → 自然语言。只有 act_pose 是互斥的（不可能又站又躺），
# 腿部/手臂/动态可以和主姿态叠加，所以这里按"主姿态 + 叠加细节"来写。
_ACTION_PHRASE = {
    # 主姿态
    "standing": "standing",
    "sitting": "seated",
    "lying": "lying down",
    "lying on back": "lying on her back",
    "lying on stomach": "lying face down",
    "lying on side": "lying on her side",
    "on back": "flat on her back",
    "on stomach": "flat on her front",
    "on side": "curled onto one side",
    "prone": "pressed flat and prone",
    "kneeling": "kneeling",
    "squatting": "crouched down low",
    "crouching": "in a low crouch",
    "walking": "walking",
    "running": "running",
    "jumping": "caught mid-jump",
    "leaning forward": "leaning forward",
    "leaning back": "leaning back",
    "bent over": "bent over",
    "arched back": "with her back arched",
    "on all fours": "up on all fours",
    "sitting on knees": "kneeling with her weight on her heels",
    "w-sitting": "seated in a W shape",
    "lotus position": "seated cross-legged",
    "fetal position": "curled up small",
    "handstand": "balanced upside down",
    "top-down bottom-up": "inverted with hips raised",
    "suspended motion": "held suspended in mid-air",
    # 腿部叠加
    "crossed legs": "with her legs crossed",
    "knees up": "with her knees drawn up",
    "knees together": "with her knees pressed together",
    "legs up": "with her legs raised",
    "legs apart": "with her legs apart",
    "spread legs": "with her legs spread wide",
    "foot up": "with one foot lifted",
    "tiptoes": "up on her toes",
    # 手臂叠加
    "arms behind head": "with both arms folded behind her head",
    "arms behind back": "with her arms held behind her back",
    "arms up": "with both arms raised",
    "hand on own cheek": "one hand resting against her cheek",
    "hand on own chest": "one hand laid on her chest",
    "hand on own hip": "one hand on her hip",
    "hand on own thigh": "one hand resting on her thigh",
    "hand between legs": "one hand slipped between her legs",
    "hands on own knees": "both hands on her knees",
    "stretching": "stretching out",
    "stretching arms": "stretching her arms out",
    "hugging own legs": "hugging her own legs",
    "covering mouth": "a hand over her mouth",
    "covering face": "hiding behind one hand",
    # 动态叠加
    "trembling": "trembling",
    "motion blur": "blurred with motion",
    "motion lines": "traced with motion lines",
    "sweatdrop": "a bead of sweat at her temple",
}

# 机位/朝向/景别的补充（原来只有 17 条，视角拆出来之后要补全）
_ANGLE_PHRASE_EXTRA = {
    "front view": "framed head-on",
    "three-quarter view": "framed at three-quarters",
    "profile": "framed in clean profile",
    "high angle": "framed from a high angle",
    "low angle": "framed from a low angle",
    "top-down view": "framed straight down",
    "over-the-shoulder": "framed over her shoulder",
    "facing viewer": "square to the camera",
    "facing away": "turned away",
    # ⚠️ `looking at viewer` / `looking back` 不在这里 —— `_FACE_PHRASE` 已经写了
    #    更自然的句子（"she looks straight into the camera" /
    #    "she glances back over her shoulder"）。两边都写会让描述重复，
    #    而且视角那条是名词性的（"her eyes on the viewer"），单独成句就是病句。
    "looking away": "turned slightly away, gaze sliding off frame",
    "looking to the side": "facing forward with her gaze off to one side",
    "looking up": "standing with her chin lifted",
    "looking down": "standing with her gaze cast down",
    "eye contact": "holding steady eye contact",
    "portrait": "kept to a portrait crop",
    "wide shot": "pulled back to a wide shot",
    "depth of field": "with a shallow depth of field",
    "symmetry": "built on a symmetrical composition",
    "rule of thirds": "placed off-centre on the thirds",
    "reflection": "with a reflection caught alongside",
    "silhouette": "rendered as a silhouette",
}

_ANGLE_PHRASE = {
    "pov": "shot from the viewer's own point of view",
    "from below": "framed from a low angle",
    "from above": "framed from above",
    "from behind": "framed from behind",
    "from side": "framed in profile",
    "close-up": "held in a tight close-up",
    "extreme close-up": "pushed into an extreme close-up",
    "dutch angle": "tilted off axis",
    "worm's-eye view": "shot from ground level",
    "bird's-eye view": "shot from directly overhead",
    "crotch focus": "composed around the hips",
    "ass focus": "composed around her hips and back",
    "breast focus": "composed around her chest",
    "feet focus": "composed around her feet",
    "full body": "kept as a full-body frame",
    "upper body": "kept to the upper body",
    "cowboy shot": "kept to a three-quarter frame",
}
# 视角分类拆出来后新增的标签，短语并进来
_ANGLE_PHRASE.update(_ANGLE_PHRASE_EXTRA)

_PROP_PHRASE = {
    "bondage": "restrained and unable to move freely",
    "shibari": "tied in decorative rope",
    "rope": "held by taut rope",
    "collar": "wearing a collar",
    "leash": "kept on a short leash",
    "handcuffs": "wrist cuffed",
    "blindfold": "blindfolded",
    "gag": "gagged",
    "ball gag": "gagged with a ball",
    "spreader bar": "held open by a bar",
    "sex toy": "a toy within reach",
    "vibrator": "a vibrator pressed to her skin",
    "dildo": "a toy in play",
    "anal beads": "beads worked into the scene",
    "whip": "a whip in frame",
    "spanking": "the sting of a slap still fresh",
    "latex": "clad in glossy latex",
    "leather": "clad in tight leather",
    "fishnet": "in fishnet stockings",
    "crotchless panties": "in crotchless underwear",
    "tentacle sex": "held by something that is not human",
}


def _pick(mapping: Dict[str, str], tokens: Sequence[str], limit: int = 1) -> List[str]:
    hits = [mapping[t.lower()] for t in tokens if t.lower() in mapping]
    out = []
    for h in hits:
        if h not in out:
            out.append(h)
    return out[:limit]


def _subject_phrase(tokens: Sequence[str]) -> str:
    for tok in tokens:
        key = tok.lower()
        if key in _SUBJECT_PHRASE:
            return _SUBJECT_PHRASE[key]
    lowered = {t.lower() for t in tokens}
    if "2girls" in lowered or "multiple girls" in lowered:
        return "Two young women"
    if "1boy" in lowered and "1girl" in lowered:
        return "A young woman and a young man"
    if "1boy" in lowered:
        return "A young man"
    return "A young woman"


def _nude_phrase(tokens: Sequence[str]) -> str:
    lowered = {t.lower() for t in tokens}
    if "completely nude" in lowered or "nude" in lowered:
        return "She is fully nude"
    if "topless" in lowered:
        return "She is bare above the waist"
    if "bottomless" in lowered or "no panties" in lowered:
        return "She is bare below the waist"
    if "lingerie" in lowered or "lace panties" in lowered:
        return "She is still in her underwear"
    if "wet clothes" in lowered:
        return "Her clothes cling wet to her skin"
    if "torn clothes" in lowered:
        return "Her clothes have been pulled open"
    if "undressing" in lowered or "clothes pull" in lowered:
        return "Her clothes are being pulled aside"
    return ""


def _is_plural(subject: str) -> bool:
    return subject.startswith(("Two", "Three", "Several", "Multiple", "A group"))


def _pronoun(tokens: Sequence[str], subject: str) -> Tuple[str, str]:
    """返回 (主语代词, be 动词)。"""
    lowered = {t.lower() for t in tokens}
    female = bool(lowered & {"1girl", "2girls", "3girls", "multiple girls", "1futa",
                             "1girl, 1futa", "2futas"})
    male = bool(lowered & {"1boy", "2boys", "multiple boys", "1futa, 1boy", "1girl, 2boys"})
    if _is_plural(subject):
        return "They", "are"
    if male and not female:
        return "He", "is"
    return "She", "is"


def build_caption(tokens: Sequence[str], seed: int = 0, style: str = "anima",
                  sfw: bool = False) -> str:
    """从已选标签生成一段 Anima 风格的自然语言描述（不需要 LLM）。"""
    rng = random.Random(int(seed) & 0xFFFFFFFF)
    lowered = [t.lower() for t in tokens]

    subject = _subject_phrase(tokens)
    pronoun, be = _pronoun(tokens, subject)
    # SFW 模式下不写性行为 / 体液 / 裸露
    act = [] if sfw else _pick(_ACT_PHRASE, tokens, 1)
    face = _pick(_FACE_PHRASE, tokens, 2)
    fluid = [] if sfw else _pick(_FLUID_PHRASE, tokens, 2)
    scene = _pick(_SCENE_PHRASE, tokens, 1)
    # 视角取 4 个：机位 + 朝向 + 景别 可能同时命中，要都写进描述。
    # （原来只取 2 个，加了朝向类之后「看向观众」会被挤掉。）
    angle = _pick(_ANGLE_PHRASE, tokens, 4)
    # 动作/姿势：最多取 3 个（主姿态 + 腿部/手臂/动态叠加）
    action = _pick(_ACTION_PHRASE, tokens, 3)
    prop = [] if sfw else _pick(_PROP_PHRASE, tokens, 1)
    nude = "" if sfw else _nude_phrase(tokens)

    clauses: List[str] = []
    head = subject
    if nude:
        head += ". " + nude
    clauses.append(head + ".")

    if act:
        clauses.append(f"{pronoun} {be} " + act[0] + ".")
    elif action:
        # ⚠️ 动作要单独成句。原来没有这一段，加了 sitting / standing 之后
        #    描述里完全体现不出来（只有性行为/表情/场景/镜头）。
        clauses.append(f"{pronoun} {be} " + ", ".join(action) + ".")
    if prop:
        clauses.append(f"{pronoun} {be} " + prop[0] + ".")

    body: List[str] = []
    if face:
        body.append(face[0])
    if len(face) > 1:
        body.append(face[1])
    if fluid:
        body.extend(fluid)
    if body:
        sentence = ", ".join(body)
        clauses.append(sentence[0].upper() + sentence[1:] + ".")

    # ⚠️ 原来 scene 和 angle 拼成 "The scene is set X and it is Y."，
    #    只有 angle 时就变成以 "and it is" 开头的病句（缺主语）。
    #    改成两句独立的话。
    if scene:
        clauses.append("The scene is set " + scene[0] + ".")
    if angle:
        # ⚠️ 「朝向」类短语（看向观众 / 视线移开 / 眼神交汇）不能套 "The frame is ..."。
        #    实测病句：`The frame is her eyes on the viewer, held in a tight close-up.`
        #    这类要当成独立小句，以代词开头。
        _DIR_WORDS = ("eye", "gaze", "glance", "chin", "facing", "turned")
        dirs = [a for a in angle if any(w in a for w in _DIR_WORDS)]
        frames = [a for a in angle if a not in dirs]
        if dirs:
            # 朝向短语一律改写成能接 "She is ..." 的形式（见 _ANGLE_PHRASE_EXTRA），
            # 所以直接套主谓即可，不需要特殊分支。
            clauses.append(f"{pronoun.capitalize()} {be} " + dirs[0] + ".")
        if frames:
            text = "The frame is " + frames[0]
            if len(frames) > 1:
                text += ", " + frames[1]
            clauses.append(text + ".")

    if sfw:
        soloish = any(k in lowered for k in ("solo", "1girl", "1boy"))
        clauses.append(rng.choice(SFW_SOLO_TAIL if soloish else SFW_TAIL))
    elif any(k in lowered for k in
             ("solo", "masturbating", "fingering", "presenting", "spread legs")):
        clauses.append(rng.choice(_SOLO_TAIL))
    else:
        clauses.append(rng.choice(_CAPTION_TAIL))

    caption = " ".join(clauses)
    caption = re.sub(r"\s+", " ", caption).strip()
    if style == "anima" and not caption.endswith("."):
        caption += "."
    return caption


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def _join(parts: Sequence[str]) -> str:
    """拼接提示词片段，并顺带做一次逗号级去重。

    ``preset_tags_to_tokens`` + ``split_tokens`` 的去重管不到「质量预置」这种
    直接拼接的片段，所以这里再兜一次底（例如质预置写了 best quality，
    标签里也有 best quality）。
    """
    out: List[str] = []
    seen = set()
    for part in parts:
        if not part:
            continue
        for raw in str(part).split(","):
            text = raw.strip()
            if not text:
                continue
            key = text.lower().replace("_", " ")
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
    return ", ".join(out)


def compose_prompt(
    tags: str = "",
    intensity: str = "hard",
    quality_preset: str = "base（原版 28~32 步）",
    extra_front: str = "",
    extra_tail: str = "",
    caption_enabled: bool = True,
    caption_seed: int = 0,
    caption_text: str = "",
    sort_tags: bool = True,
    dedupe_tags: bool = True,
    separator: str = ", ",
    upstream_prompt: str = "",
    token_budget_warn: int = 0,
    outfit_preset: Optional[Dict[str, object]] = None,
    pose_preset: Optional[Dict[str, object]] = None,
    mode: str = "NSFW（不限）",
) -> Dict[str, object]:
    """核心合成函数。返回 dict（含 prompt / caption / debug 信息）。

    ``outfit_preset`` / ``pose_preset`` 是面板写入的预设，形如::

        {"zh": "女仆装", "tags": ["maid", "white apron", ...], "lock": False}

    预设标签会被插到用户标签**之前**（角色/服装属于身份层，按 Anima 语法要更靠前），
    然后整体一起去重与互斥。``lock=True`` 时第一个标签（角色触发词）会带上
    ``char_lock:`` 前缀，保证「一次只锁一个角色」。
    """
    preset = outfit_preset or {}
    preset_name = str(preset.get("zh") or "").strip()
    preset_raw = [str(t) for t in (preset.get("tags") or [])]
    locked = bool(preset.get("lock"))

    pose = pose_preset or {}
    pose_name = str(pose.get("zh") or "").strip()
    pose_raw = [str(t) for t in (pose.get("tags") or [])]

    preset_tokens = preset_tags_to_tokens(preset_raw, locked=locked) + \
        preset_tags_to_tokens(pose_raw, locked=False)
    preset_has_lock = locked or any(
        t.split(":", 1)[-1].lower() in LOCKED_CHARACTERS for t in preset_tokens
    )

    # 服装预设是「整套指定」，所以是权威的：用户标签里和预设同组（例如同样属于
    # outfit_base 的另一套服装）的先清掉，避免出现「预设是死库水、还留着校服」。
    preset_groups = set()
    for tok in preset_tokens:
        low = tok.split(":", 1)[-1].lower() if tok.lower().startswith(CHAR_LOCK_PREFIX) else tok.lower()
        info = TAG_INDEX.get(low)
        if info and info.get("g"):
            preset_groups.add(info["g"])
    if preset_has_lock:
        preset_groups.add("char_lock")

    user_tokens = []
    dropped_by_preset: List[str] = []
    for tok in split_tokens(tags):
        low = tok.lower()
        info = TAG_INDEX.get(low)
        in_group = bool(info and info.get("g") in preset_groups)
        is_char = low.startswith(CHAR_LOCK_PREFIX) or low in LOCKED_CHARACTERS
        if in_group or (is_char and preset_has_lock):
            dropped_by_preset.append(tok)
            continue
        user_tokens.append(tok)

    # 服装预设属于「用户显式指定」，所以放在用户标签之前，去重时优先保留
    raw_tokens = preset_tokens + user_tokens

    dropped_intensity: List[str] = []
    if intensity and str(intensity).lower() != "all":
        raw_tokens, dropped_intensity = filter_by_intensity(raw_tokens, intensity)

    # SFW 模式：把露骨标签整体拦下（预设带进来的正常服装单品豁免）
    sfw = is_sfw(mode)
    dropped_sfw: List[str] = []
    if sfw:
        raw_tokens, dropped_sfw = _sfw_filter(raw_tokens, preset_tokens=preset_tokens)

    tokens = raw_tokens
    if dedupe_tags:
        tokens = dedupe(tokens)
    tokens, dropped_group = enforce_groups(tokens)
    if sort_tags:
        tokens = sort_tokens(tokens)
    # char_lock: 是内部标记，发出去之前剥掉
    tokens = strip_char_lock(tokens)

    tag_line = separator.join(tokens)

    user_caption = (caption_text or "").strip()
    if user_caption:
        caption = user_caption
    elif caption_enabled:
        caption = build_caption(tokens, seed=caption_seed, sfw=sfw)
    else:
        caption = ""

    if sfw:
        quality_preset = _join([quality_preset, SFW_QUALITY])
    # ⚠️ 这里收到的可能是**档位名**（「无（自己写）」「base（原版 28~32 步）」…）
    #    而不是实际质量词 —— 面板与 preview() 都会先查表翻译，但 compose_prompt
    #    能被外部脚本直接调用，所以这里也兜一层。
    #    「无（自己写）」的表值是空字符串；不兜的话档位名会当标签进提示词
    #    （实测出现过 `无（自己写）, best quality, 1girl…`）。
    if quality_preset in QUALITY_PRESETS:
        quality_preset = QUALITY_PRESETS[quality_preset]
    elif quality_preset.startswith("无"):
        quality_preset = ""
    head = _join([quality_preset, extra_front, tag_line])
    body = _join([head, caption])
    body = _join([body, extra_tail])
    if upstream_prompt and upstream_prompt.strip():
        body = _join([body, upstream_prompt.strip()])

    info = {
        "tags": tokens,
        "tag_count": len(tokens),
        "outfit_preset": preset_name,
        "pose_preset": pose_name,
        "dropped_by_intensity": dropped_intensity,
        "dropped_by_group": dropped_group,
        "dropped_by_preset": dropped_by_preset,
        "dropped_by_sfw": dropped_sfw,
        "mode": "sfw" if sfw else "nsfw",
        "caption": caption,
    }
    if token_budget_warn and len(body) > int(token_budget_warn):
        info["warn"] = f"提示词长度 {len(body)} 字符，超过建议上限 {token_budget_warn}"
    return {"prompt": body, "info": info}


def compose_negative(
    base_enabled: bool = True,
    extras: Optional[Sequence[str]] = None,
    extra_text: str = "",
    upstream_negative: str = "",
    separator: str = ", ",
    mode: str = "NSFW（不限）",
) -> Dict[str, object]:
    sfw = is_sfw(mode)
    # 段落名容错：「NSFW 安全」/「NSFW安全」、「人体结构」等写法都能匹配上。
    # 之前前端发的是不带空格的 "NSFW安全"，而字典键是 "NSFW 安全"，
    # 结果那段词永远命中不了 —— 勾了也没效果。
    def resolve(name: str) -> Optional[str]:
        s = str(name or "").strip()
        if s in NEGATIVE_EXTRA:
            return s
        squashed = s.replace(" ", "").replace("　", "")
        for key in NEGATIVE_EXTRA:
            if key.replace(" ", "").replace("　", "") == squashed:
                return key
        return None

    chunks: List[str] = []
    if base_enabled:
        chunks.append(NEGATIVE_BASE)
    for name in (extras or []):
        key = resolve(name)
        if key is None:
            continue
        # SFW 模式下「NSFW 安全」这段换成全年龄向的反向词
        if sfw and key == "NSFW 安全":
            chunks.append(NEGATIVE_SFW)
            continue
        chunks.append(NEGATIVE_EXTRA[key])
    if sfw:
        chunks.append(NEGATIVE_SFW)
    if extra_text and extra_text.strip():
        chunks.append(extra_text.strip())
    if upstream_negative and upstream_negative.strip():
        chunks.append(upstream_negative.strip())

    tokens = dedupe(normalize_token(t) for c in chunks for t in split_tokens(c))
    return {"prompt": separator.join(tokens), "info": {"tag_count": len(tokens)}}
    if extra_text and extra_text.strip():
        chunks.append(extra_text.strip())
    if upstream_negative and upstream_negative.strip():
        chunks.append(upstream_negative.strip())

    tokens = dedupe(normalize_token(t) for c in chunks for t in split_tokens(c))
    return {"prompt": separator.join(tokens), "info": {"tag_count": len(tokens)}}


def preview(payload: Dict[str, object]) -> Dict[str, object]:
    """给前端预览用：返回正/负面 + 结构化信息。

    ⚠️ `quality_preset` 这里收到的是**档位名**（面板就是这么传的，例如「无（自己写）」），
    必须先查表翻译成实际质量词。查不到才当成字面标签串（兼容外部脚本直接传
    "best quality, absurdres"）。

    直接把它当标签串会出事：「无（自己写）」这个档位的表值是**空字符串**（即不加质量词），
    但字面档位名会被当成标签写进提示词 —— 实测预览里出现过 `无（自己写）, best quality, 1girl…`。
    节点路径走 `QUALITY_PRESETS.get(...)` 所以没这个问题。
    """
    raw_q = str(payload.get("quality_preset", "") or "")
    if raw_q in QUALITY_PRESETS:
        q = QUALITY_PRESETS[raw_q]
    elif raw_q and not raw_q.startswith("无"):
        q = raw_q
    else:
        q = ""
    pos = compose_prompt(
        tags=str(payload.get("tags", "")),
        intensity=str(payload.get("intensity", "hard")),
        quality_preset=q,
        extra_front=str(payload.get("extra_front", "")),
        extra_tail=str(payload.get("extra_tail", "")),
        caption_enabled=bool(payload.get("caption_enabled", True)),
        caption_seed=int(payload.get("caption_seed", 0) or 0),
        caption_text=str(payload.get("caption_text", "")),
        sort_tags=bool(payload.get("sort_tags", True)),
        outfit_preset=payload.get("outfit_preset") or None,
        pose_preset=payload.get("pose_preset") or None,
        mode=str(payload.get("mode", "NSFW（不限）")),
    )
    neg = compose_negative(
        base_enabled=bool(payload.get("negative_base", True)),
        extras=payload.get("negative_extras") or [],
        extra_text=str(payload.get("negative_extra_text", "")),
        mode=str(payload.get("mode", "NSFW（不限）")),
    )
    return {
        "positive": pos["prompt"],
        "negative": neg["prompt"],
        "info": pos["info"],
    }
