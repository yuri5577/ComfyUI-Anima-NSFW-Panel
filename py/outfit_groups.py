# -*- coding: utf-8 -*-
"""服装分组与自动分类（v1.9.9）。

## 为什么要有这个文件

原来 568 套服装挤在 14 个分组里，而且**分组很偏、内容也常错**：

* 「服装库·性感暴露」一组 160 套（占三成）
* 导入库自带的分组（d_dress / d_casual …）按内容看经常是错的 ——
  例如 `d_dress` 里的「黑色颈带·大腿带」其实是 garter straps + thigh strap

所以改成**按服装内容自动分类**：想看校服就点「校园制服」，想看内衣就点
「内衣/睡衣」。挑衣服的人关心的是"这是件什么衣服"，不是"当初从哪导入的"。

## 判据（踩过几轮坑才定下来）

1. **主判定只看前 3 个标签**。导入数据里第一个标签就是主项
   （`眼镜·项链` → `glasses, necklace, ...`），
   让配件也参与计分的话，「白色连裤袜·高跟鞋」会被算成"日常"。
2. **计分而非先命中先赢**。关键词越长越具体分越高，这样 `bikini` 能压过 `skirt`。
3. **词边界**。`bra` 不能命中 `braid`/`bracelet`（踩过）。
4. **配件拼盘单独一组**。整套里只有手套/袜子/首饰、没有任何主服装
   （dress/skirt/uniform/kimono/bikini/armor…）→ 归「配件组合」。
5. 游戏 COS 那 50 套按原分组直接映射，不参与关键词匹配。
"""

# 英文的「主服装」标志：有这些才说明这套是"一件衣服"而不是配件拼盘
MAIN_GARMENT_EN = (
    "dress", "skirt", "shirt", "uniform", "kimono", "yukata", "hanfu", "qipao",
    "swimsuit", "bikini", "bodysuit", "armor", "robe", "jacket", "coat",
    "sweater", "hoodie", "cardigan", "overalls", "tracksuit", "jersey",
    "leotard", "lingerie", "corset", "bustier", "nightgown", "pajamas",
    "tuxedo", "gown", "blazer", "apron", "veil", "sari", "dirndl", "tunic",
    "vest", "camisole", "maid", "nurse", "witch", "ninja", "miko", "shorts",
    "pants", "jeans",
)
MAIN_GARMENT_ZH = ("服", "装", "裙", "衣", "甲", "袍", "裤")

# 游戏 COS 的分组映射（这 50 套按原分组直接归位）
GAME_MAP = {
    "al_royal": "gc_al_royal", "al_eagle": "gc_al_eagle", "al_iron": "gc_al_iron",
    "al_sakura": "gc_al_sakura", "al_other": "gc_al_other", "al_base": "gc_al_base",
    "cl_base": "gc_cl", "cl_team": "gc_cl", "cos_general": "gc_general",
}

# (id, 中文名, 图标, 权重倍率, (关键词...))
# 权重倍率：露出类调成 0.6，避免 `bare shoulders` 这种附带标签压过主服装
RULE_GROUPS = (
    ("oc_nurse", "护士/医疗", "\U0001F489", 1.0, (
        "nurse", "scrubs", "stethoscope", "syringe", "bandage", "护士", "听诊器", "绷带")),
    ("oc_maid", "女仆/家政", "\U0001F9F9", 1.0, (
        "maid", "waitress", "waist apron", "女仆", "服务生", "咖啡店")),
    ("oc_police", "警察/安保", "\U0001F693", 1.0, (
        "police uniform", "police", "security guard", "警察", "警服", "警帽")),
    ("oc_school", "校园制服", "\U0001F392", 1.2, (
        "school uniform", "serafuku", "sailor collar", "gym uniform", "bloomers",
        "loose socks", "school swimsuit", "plaid skirt", "school bag",
        "校服", "水手服", "体操服", "学园", "学院", "图书委员", "死库水", "校")),
    ("oc_military", "军装/海军", "\U0001F396", 1.0, (
        "military uniform", "naval uniform", "army uniform", "sailor hat",
        "epaulettes", "armband", "greatcoat", "bicorne", "tricorne", "army",
        "军装", "海军", "大檐帽", "战术背心")),
    ("oc_idol", "偶像/舞台", "\U0001F3A4", 1.0, (
        "idol", "stage costume", "microphone", "concert", "spotlight",
        "偶像", "打歌", "舞台", "演唱会", "爵士")),
    ("oc_bunny", "兔女郎", "\U0001F430", 1.0, (
        "bunny girl", "playboy bunny", "rabbit ears", "兔女郎", "兔耳")),
    ("oc_swim", "泳装", "\U0001F3D6", 1.0, (
        "bikini", "one-piece swimsuit", "swimsuit", "swim briefs", "beach",
        "competition swimsuit", "swim cap", "比基尼", "泳装", "泳衣", "泳帽")),
    ("oc_lingerie", "内衣/睡衣", "\U0001FA72", 1.0, (
        "lingerie", "panties", "bra", "sports bra", "garter belt", "garter straps",
        "bustier", "corset", "chemise", "nightgown", "pajamas", "sleepwear",
        "negligee", "camisole", "内衣", "胸罩", "内裤", "吊袜", "束腰",
        "睡衣", "紧身胸衣")),
    ("oc_wedding", "婚纱/丧服", "\U0001F470", 1.0, (
        "wedding dress", "veil", "funeral", "婚纱", "婚礼", "葬礼", "头纱", "花嫁")),
    ("oc_formal", "晚礼服/正装", "\U0001F457", 1.0, (
        "evening gown", "cocktail dress", "tuxedo", "halterneck", "ball gown",
        "晚礼服", "鸡尾酒", "正装", "燕尾")),
    ("oc_kimono", "和服/和风", "\u26E9", 1.0, (
        "kimono", "yukata", "hakama", "furisode", "obi", "miko", "maiko",
        "nontraditional miko", "geta", "tabi", "sarashi", "japanese clothes",
        "和服", "浴衣", "巫女", "袴", "振袖", "舞妓", "日式")),
    ("oc_cn", "中华/汉服/旗袍", "\U0001F3EE", 1.0, (
        "china dress", "cheongsam", "hanfu", "qipao", "mandarin collar",
        "旗袍", "汉服", "中华")),
    ("oc_sport", "运动/竞技", "\u26BD", 1.0, (
        "tracksuit", "jersey", "bike shorts", "sweat", "tennis", "athletic",
        "ballet", "tutu", "gymnastics", "cheerleader", "pom poms",
        "运动", "球衣", "棒球", "篮球", "网球", "芭蕾", "体操", "啦啦", "舞蹈")),
    ("oc_fantasy", "奇幻/铠甲", "\u2694", 1.0, (
        "armor", "chainmail", "breastplate", "gauntlets", "bikini armor", "knight",
        "witch hat", "witch", "wizard", "elf", "demon girl", "angel", "dragon",
        "robe", "mage", "quiver", "ninja", "kunoichi",
        "铠甲", "盔甲", "骑士", "女巫", "魔法", "精灵", "恶魔", "天使",
        "女武神", "忍者", "武士", "长袍", "斗篷", "披风")),
    ("oc_scifi", "科幻/紧身衣", "\U0001F680", 1.0, (
        "bodysuit", "plugsuit", "latex", "cyber", "mecha", "spacesuit",
        "interface headset", "紧身衣", "驾驶服", "乳胶", "赛博", "科幻",
        "机械", "机甲")),
    ("oc_vocaloid", "虚拟歌手", "\U0001F3B5", 1.0, (
        "vocaloid", "hatsune miku", "初音", "雪未来", "赛车初音")),
    ("oc_goth", "哥特/洛丽塔", "\U0001F5A4", 1.0, (
        "gothic lolita", "gothic", "lolita", "victorian", "哥特", "洛丽塔",
        "维多利亚")),
    ("oc_costume", "拟装/角色扮演", "\U0001F383", 1.0, (
        "animal ears", "cat girl", "costume", "santa", "halloween", "pumpkin",
        "cosplay", "pirate", "圣诞", "万圣", "猫耳", "拟装", "海盗")),
    # 注：原来还有个「民族/传统」组（sari / dirndl / ao dai），但 568 套里
    # 没有任何一套命中它 —— 点进去空无一物，所以去掉了。要加回的话把关键词
    # 补进来重新分类即可。
    ("oc_reveal", "透视/露点系", "\U0001F525", 0.6, (
        "see-through", "revealing clothes", "crotchless", "pasties", "underboob",
        "sideboob", "no bra", "no panties", "topless", "clothing cutout",
        "breasts curtain", "pelvic curtain", "透视", "暴露", "开裆", "乳贴", "裸露")),
    ("oc_offshoulder", "露肩/露背", "\U0001F4AB", 0.6, (
        "bare shoulders", "off shoulder", "bare arms", "backless",
        "shoulder cutout", "露肩", "裸肩", "露背", "裸露手臂")),
    ("oc_midriff", "露脐/中空", "\u2728", 0.6, (
        "midriff", "crop top", "navel", "露脐", "中空", "露腰", "肚脐")),
    ("oc_top", "上衣/衬衫", "\U0001F454", 1.0, (
        "t-shirt", "shirt", "tank top", "blouse", "camisole", "turtleneck",
        "sweater", "衬衫", "上衣", "毛衣", "针织", "背心")),
    ("oc_outer", "外套/夹克", "\U0001F9E5", 1.0, (
        "jacket", "coat", "cardigan", "hoodie", "capelet", "trench coat",
        "overcoat", "duffel coat", "外套", "夹克", "大衣", "卫衣", "开衫",
        "披肩", "毛皮")),
    ("oc_pants", "裤装/休闲", "\U0001F456", 1.0, (
        "jeans", "pants", "shorts", "bike shorts", "overalls", "casual",
        "休闲", "牛仔裤", "长裤", "短裤", "背带")),
    ("oc_dress", "连衣裙/裙装", "\U0001F45A", 1.0, (
        "sundress", "one-piece dress", "pleated skirt", "miniskirt", "long skirt",
        "layered skirt", "frilled skirt", "dress", "skirt", "连衣裙", "长裙",
        "短裙", "百褶")),
    ("oc_office", "OL/职业西装", "\U0001F4BC", 1.0, (
        "office lady", "business suit", "blazer", "pencil skirt", "lab coat",
        "flight attendant", "职业", "西装", "白大褂", "空姐")),
)

# 游戏 COS 分组（顺序 = 面板里的显示顺序）
GAME_GROUPS = (
    ("gc_al_royal", "碧蓝·皇家", "\U0001F451"),
    ("gc_al_eagle", "碧蓝·白鹰", "\U0001F985"),
    ("gc_al_iron", "碧蓝·铁血", "\u2699\uFE0F"),
    ("gc_al_sakura", "碧蓝·重樱", "\U0001F338"),
    ("gc_al_other", "碧蓝·其它阵营", "\u26F5"),
    ("gc_al_base", "碧蓝·舰娘基础", "\u2693"),
    ("gc_cl", "封印者", "\U0001F694"),
    ("gc_general", "通用 COS 风", "\U0001F3AD"),
)

FALLBACK_GROUPS = (
    ("oc_accessory", "配件组合", "\U0001F9E4"),
    ("oc_other", "其它", "\U0001F9E9"),
)

# 面板用的分组清单（id / zh / en / icon / src）
def as_group_list():
    out = []
    for cid, zh, icon, _mul, _kws in RULE_GROUPS:
        out.append({"id": cid, "zh": zh, "en": cid, "icon": icon, "src": "auto"})
    for gid, zh, icon in GAME_GROUPS:
        out.append({"id": gid, "zh": zh, "en": gid, "icon": icon, "src": "game-cos"})
    for cid, zh, icon in FALLBACK_GROUPS:
        out.append({"id": cid, "zh": zh, "en": cid, "icon": icon, "src": "auto"})
    return out


import re as _re

_WORD = _re.compile(r"[a-z]")
_CJK = _re.compile(r"[\u4e00-\u9fff]")


def _hit(kw, hay_en, hay_zh):
    if _CJK.search(kw):
        return (len(kw) + 2) if kw in hay_zh else 0
    if _re.search(r"(?<![a-z])" + _re.escape(kw) + r"(?![a-z])", hay_en):
        return len(kw)
    return 0


def _score(hay_en, hay_zh):
    best, best_score = None, 0.0
    for cid, _zh, _icon, mul, kws in RULE_GROUPS:
        s = 0.0
        for kw in kws:
            s += _hit(kw, hay_en, hay_zh)
        s *= mul
        if s > best_score:
            best, best_score = cid, s
    return best, best_score


def has_main_garment(zh, tags):
    """这套里有没有「主服装」（而不是只有配件）"""
    low = " " + " ".join(tags).lower() + " "
    for kw in MAIN_GARMENT_EN:
        if _re.search(r"(?<![a-z])" + _re.escape(kw) + r"(?![a-z])", low):
            return True
    return any(ch in str(zh) for ch in MAIN_GARMENT_ZH)


def classify(src, gid, zh, tags, head_n=3):
    """给一套预设算分组 id。

    * 游戏 COS（src == "game-cos"）按原分组映射
    * 其余：只用前 head_n 个标签判定（导入数据里第一个就是主项），
      没命中再退回全部标签；真的没主题时看有没有主服装决定归「配件组合」还是「其它」
    """
    if src == "game-cos":
        return GAME_MAP.get(gid, "gc_general")

    head = list(tags)[:head_n]
    best, sc = _score("; " + " ".join(head).lower() + "; ",
                      "; " + str(zh) + "; " + " ".join(head) + ";")
    if best is None:
        best, sc = _score("; " + " ".join(tags).lower() + "; ",
                          "; " + str(zh) + "; " + " ".join(tags) + ";")
    if best is None:
        return "oc_other" if has_main_garment(zh, tags) else "oc_accessory"
    # 命中很弱（< 5 分，基本只是配件命中）且没有主服装 → 配件组合
    if sc < 5 and not has_main_garment(zh, tags):
        return "oc_accessory"
    return best
