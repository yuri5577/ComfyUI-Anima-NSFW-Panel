# -*- coding: utf-8 -*-
"""中文翻译层（手工整理 + 本地中文资料 + 逐词词典）。

分层策略（``translate()``）：
  1. ``CURATED``   手工校对过的词条 —— 最高优先级，用于修正机翻的明显错误
  2. ``MERGED``    从本机中文资料合并来的实际译文
                   （ComfyUI-Danbooru-Anima-Prompt 的 weilin_tags.db + all_tags_cn.json）
  3. ``WORDS``     逐词词典 + 简单词形处理，用于组合词
  4. 都命中不了就保留原文（英文也是 Anima 认的写法，不影响出图）

所有查表都做了归一化（小写、非字母数字转下划线），因此
``see-through`` / ``see_through`` / ``See Through`` 是同一个键。
"""

from __future__ import annotations

import re
from typing import Dict, Optional

_NORM_RE = re.compile(r"[^a-z0-9]+")


def norm(text) -> str:
    return _NORM_RE.sub("_", str(text).lower()).strip("_")


# ---------------------------------------------------------------------------
# 1. 手工校对：修正机翻错误 / 补常见词
# ---------------------------------------------------------------------------
CURATED: Dict[str, str] = {
    # 作品名（机翻经常离谱）
    "vocaloid": "Vocaloid",
    "hololive": "Hololive",
    "nijisanji": "Nijisanji",
    "bang dream!": "BanG Dream!",
    "fate/stay night": "Fate/stay night",
    "fate/extra": "Fate/EXTRA",
    "fate/grand order": "Fate/Grand Order",
    "fate (series)": "Fate 系列",
    "little busters!": "Little Busters!",
    "clannad": "CLANNAD",
    "project moon": "Project Moon",
    "idolmaster": "偶像大师",
    "touhou": "东方 Project",
    "original": "原创角色",
    "blue archive": "蔚蓝档案",
    "azur lane": "碧蓝航线",
    "arknights": "明日方舟",
    "genshin impact": "原神",
    "honkai: star rail": "崩坏：星穹铁道",
    "honkai (series)": "崩坏系列",
    "umamusume": "赛马娘",
    "kantai collection": "舰队 Collection",
    "girls' frontline": "少女前线",
    "punishing: gray raven": "战双帕弥什",
    "reverse: 1999": "重返未来：1999",
    "wuthering waves": "鸣潮",
    "zenless zone zero": "绝区零",
    "neural cloud": "云图计划",
    "project sekai": "世界计划",
    "limbus company": "边狱公司",
    "nikke": "胜利女神：妮姬",
    "granblue fantasy": "碧蓝幻想",
    "princess connect!": "公主连结",
    "touken ranbu": "刀剑乱舞",
    "love live!": "LoveLive!",
    "love live! sunshine!!": "LoveLive! Sunshine!!",
    "the legend of zelda": "塞尔达传说",
    "xenoblade chronicles (series)": "异度神剑",
    "tales of (series)": "传说系列",
    "danganronpa (series)": "弹丸论破",
    "umineko no naku koro ni": "海猫鸣泣之时",
    "higurashi no naku koro ni": "寒蝉鸣泣之时",
    "jojo no kimyou na bouken": "JOJO 的奇妙冒险",
    "bishoujo senshi sailor moon": "美少女战士",
    "mahou shoujo madoka magica": "魔法少女小圆",
    "cardcaptor sakura": "魔卡少女樱",
    "lyrical nanoha": "魔法少女奈叶",
    "boku no hero academia": "我的英雄学院",
    "kimetsu no yaiba": "鬼灭之刃",
    "jujutsu kaisen": "咒术回战",
    "chainsaw man": "电锯人",
    "one piece": "海贼王",
    "dragon ball": "龙珠",
    "naruto": "火影忍者",
    "bleach": "死神",
    "neon genesis evangelion": "新世纪福音战士",
    "evangelion": "EVA",
    "code geass": "叛逆的鲁路修",
    "yu-gi-oh!": "游戏王",
    "kemono friends": "兽娘动物园",
    "girls und panzer": "少女与战车",
    "sono bisque doll wa koi wo suru": "更衣人偶坠入爱河",
    "yahari ore no seishun lovecome wa machigatteiru.": "我的青春恋爱物语果然有问题",
    "saenai heroine no sodatekata": "路人女主的养成方法",
    "go-toubun no hanayome": "五等分的新娘",
    "suzumiya haruhi no yuuutsu": "凉宫春日的忧郁",
    "k-on!": "轻音少女",
    "spy x family": "间谍过家家",
    "oshi no ko": "我推的孩子",
    "bocchi the rock!": "孤独摇滚！",
    "lycoris recoil": "莉可丽丝",
    "tensei shitara slime datta ken": "关于我转生变成史莱姆这档事",
    "re:zero": "Re：从零开始的异世界生活",
    "sword art online": "刀剑神域",
    "overlord": "不死者之王",
    "konosuba": "为美好的世界献上祝福",
    "steins;gate": "命运石之门",
    "guilty gear": "罪恶装备",
    "blazblue": "苍翼默示录",
    "hyperdimension neptunia": "次元游戏海王星",
    "atelier (series)": "炼金工房系列",
    "super mario (series)": "超级马里奥",
    "street fighter": "街头霸王",
    "tekken": "铁拳",
    "kingdom hearts": "王国之心",
    "devil may cry": "鬼泣",
    "resident evil": "生化危机",
    "dark souls (series)": "黑暗之魂",
    "elden ring": "艾尔登法环",
    "nier (series)": "尼尔系列",
    "nier: automata": "尼尔：机械纪元",
    "persona": "女神异闻录",
    "persona 5": "女神异闻录 5",
    "league of legends": "英雄联盟",
    "fire emblem": "火焰纹章",
    "final fantasy": "最终幻想",
    "dragon quest": "勇者斗恶龙",
    "ragnarok online": "仙境传说",
    "splatoon": "斯普拉遁",
    "metroid": "银河战士",
    "gundam": "高达",
    "precure": "光之美少女",
    "pokemon": "宝可梦",

    # 机翻明显不通顺的词
    "armpit cutout": "腋下镂空",
    "armpit": "腋下",
    "armpits": "腋下",
    "arm warmers": "手臂套",
    "arm belts": "臂带",
    "armored gloves": "护甲手套",
    "armored bodysuit": "护甲紧身衣",
    "armored skirt": "护甲裙",
    "assault rifle": "突击步枪",
    "bare arms": "裸臂",
    "bare thighs": "裸腿",
    "bare pectorals": "裸露胸肌",
    "bandaged thighs": "包扎的大腿",
    "armor high heels": "铠甲高跟鞋",
    "aura surrounding": "周身光环",
    "banner": "横幅",
    "bard": "吟游诗人",
    "bartender": "酒保",
    "baseball bat": "棒球棒",
    "bat ornament": "蝙蝠饰品",
    "book": "书",
    "holding book": "拿着书",
    "hair ornament": "发饰",
    "ornament": "饰品",
    "outwear": "外穿",
    "cutout": "镂空",
    "surrounding": "环绕",
    "adorned with intricate silver embroidery": "缀有繁复银线刺绣",
    "ancient greek clothes": "古希腊服饰",
    "aristocratic clothes": "贵族服饰",
    "aqua feather hair ornament": "水蓝羽毛发饰",
    "aqua-white outwear jacket": "水蓝白配色外穿夹克",
    "ntr": "NTR（被夺爱）",
    "hololive": "Hololive（虚拟主播企划）",
    "nijisanji": "Nijisanji（虚拟主播企划）",
    "fate/grand order": "Fate/Grand Order",
    "original": "原创角色",
    "kantai collection": "舰队 Collection",
    "touken ranbu": "刀剑乱舞",
    "love live!": "LoveLive!",
    "bang dream!": "BanG Dream!",
    "project sekai": "世界计划",
    "idolmaster": "偶像大师",
    "umamusume": "赛马娘",
    "arknights": "明日方舟",
    "azur lane": "碧蓝航线",
    "blue archive": "蔚蓝档案",
    "genshin impact": "原神",
    "honkai (series)": "崩坏系列",
    "honkai: star rail": "崩坏：星穹铁道",
    "girls' frontline": "少女前线",
    "granblue fantasy": "碧蓝幻想",
    "precure": "光之美少女",
    "fire emblem": "火焰纹章",
    "final fantasy": "最终幻想",
    "pokemon": "宝可梦",
    "tales of (series)": "传说系列",
    "danganronpa (series)": "弹丸论破",
    "fate (series)": "Fate 系列",
    "kancolle": "舰队 Collection",
    "vocaloid": "Vocaloid",
    "touhou": "东方 Project",
    "oshi no ko": "我推的孩子",
    "bocchi the rock!": "孤独摇滚！",
    "lycoris recoil": "莉可丽丝",
    "spy x family": "间谍过家家",
    "chainsaw man": "电锯人",
    "jujutsu kaisen": "咒术回战",
    "kimetsu no yaiba": "鬼灭之刃",
    "boku no hero academia": "我的英雄学院",
    "dragon ball": "龙珠",
    "one piece": "海贼王",
    "naruto": "火影忍者",
    "bleach": "死神",
    "gundam": "高达",
    "jojo no kimyou na bouken": "JOJO 的奇妙冒险",
    "neon genesis evangelion": "EVA",
    "project moon": "Project Moon",
    "limbus company": "边狱公司",
    "nikke": "胜利女神：妮姬",
    "wuthering waves": "鸣潮",
    "zenless zone zero": "绝区零",
    "reverse: 1999": "重返未来：1999",
    "punishing: gray raven": "战双帕弥什",
    "neural cloud": "云图计划",
    "princess connect!": "公主连结",
    "love live! sunshine!!": "LoveLive! Sunshine!!",
    "genshin impact": "原神",
}


# ---------------------------------------------------------------------------
# 2. 逐词词典（用于组合词）
# ---------------------------------------------------------------------------
WORDS: Dict[str, str] = {
    # 颜色
    "black": "黑色", "white": "白色", "red": "红色", "blue": "蓝色", "green": "绿色",
    "yellow": "黄色", "pink": "粉色", "purple": "紫色", "orange": "橙色",
    "brown": "棕色", "grey": "灰色", "gray": "灰色", "silver": "银色", "gold": "金色",
    "golden": "金色", "aqua": "水蓝", "cyan": "青色", "magenta": "品红",
    "blonde": "金", "dark": "深色", "light": "浅色", "pale": "苍白",
    "bright": "亮色", "vivid": "鲜艳", "pastel": "粉彩", "neon": "霓虹",
    "iridescent": "虹彩", "holographic": "全息", "two-tone": "双色",
    "multicolored": "多色", "gradient": "渐变", "translucent": "半透明",
    "transparent": "透明", "opaque": "不透明", "shiny": "亮面", "glossy": "光泽",
    "matte": "哑光", "metallic": "金属感", "pearl": "珍珠色", "crystal": "水晶",
    # 形状 / 尺寸
    "long": "长", "short": "短", "big": "大", "small": "小", "huge": "巨大",
    "tiny": "极小", "wide": "宽", "narrow": "窄", "thick": "粗", "thin": "细",
    "high": "高", "low": "低", "tight": "紧身", "loose": "宽松", "open": "敞开",
    "closed": "闭合", "full": "全长", "half": "半", "double": "双", "single": "单",
    "triple": "三", "two": "双", "three": "三", "cross": "十字", "crossed": "交叉",
    "layered": "分层", "pleated": "百褶", "frilled": "荷叶边", "ruffled": "褶皱",
    "trimmed": "镶边", "trim": "镶边", "lace": "蕾丝", "fishnet": "渔网",
    "striped": "条纹", "plaid": "格纹", "checkered": "格子", "polka": "圆点",
    "floral": "花卉", "patterned": "带花纹", "pattern": "花纹", "print": "印花",
    "decorated": "装饰", "embroidered": "刺绣", "embroidery": "刺绣",
    "sequin": "亮片", "sequins": "亮片", "bead": "珠子", "beads": "珠子",
    "chain": "链条", "spike": "尖刺", "spikes": "尖刺", "stud": "铆钉",
    "studs": "铆钉", "buckle": "带扣", "zipper": "拉链", "button": "扣子",
    "buttons": "扣子", "pocket": "口袋", "cuff": "袖口", "cuffs": "袖口",
    "hem": "下摆", "seam": "缝线", "stitch": "缝线", "stitches": "缝合线",
    "patch": "贴布", "badge": "徽章", "insignia": "徽章", "emblem": "纹章",
    "logo": "标志", "symbol": "符号", "sleeveless": "无袖", "strapless": "无肩带",
    "backless": "露背", "halterneck": "吊颈式", "turtleneck": "高领",
    "collared": "有领", "hooded": "连帽", "hood": "兜帽", "zippered": "带拉链",
    "fur": "毛皮", "fur-trimmed": "毛边", "fringed": "流苏", "fringe": "流苏",
    "tassel": "流苏", "tassels": "流苏", "knitted": "针织", "ribbed": "罗纹",
    "quilted": "绗缝", "padded": "加厚", "sheer": "半透明", "mesh": "网眼",
    "bandaged": "包扎", "torn": "破损", "ripped": "撕破", "wet": "湿透",
    "detached": "分离式", "removed": "脱下的", "unworn": "未穿的",
    "worn": "穿着的", "oversized": "超大号", "mini": "迷你", "micro": "超小",
    "high-waist": "高腰", "highleg": "高叉", "lowleg": "低腰",
    "off-shoulder": "露肩", "off": "离", "shoulder": "肩", "one-shoulder": "单肩",
    # 身体
    "hair": "头发", "eyes": "眼睛", "eye": "眼睛", "head": "头", "face": "脸",
    "mouth": "嘴", "lip": "唇", "lips": "唇", "tongue": "舌", "tooth": "牙",
    "fang": "尖牙", "ear": "耳", "ears": "耳朵", "nose": "鼻", "cheek": "脸颊",
    "forehead": "额头", "chin": "下巴", "neck": "脖子", "navel": "肚脐",
    "skin": "皮肤", "tattoo": "纹身", "tattoos": "纹身", "piercing": "穿孔",
    "makeup": "妆容", "scar": "疤痕", "scarred": "有疤痕", "bandage": "绷带",
    "bandages": "绷带", "arm": "手臂", "arms": "手臂", "leg": "腿", "legs": "腿",
    "hand": "手", "hands": "手", "finger": "手指", "fingers": "手指",
    "nail": "指甲", "nails": "指甲", "toe": "脚趾", "toes": "脚趾", "foot": "脚",
    "feet": "脚", "thigh": "大腿", "thighs": "大腿", "knee": "膝", "knees": "膝",
    "ankle": "脚踝", "wrist": "手腕", "waist": "腰", "hip": "胯", "hips": "胯",
    "chest": "胸", "breast": "胸", "breasts": "胸部", "pectorals": "胸肌",
    "stomach": "腹部", "back": "背部", "collarbone": "锁骨", "clavicle": "锁骨",
    # 服装
    "hair": "头发", "dress": "连衣裙", "skirt": "裙子", "shirt": "衬衫",
    "jacket": "夹克", "coat": "外套", "cape": "斗篷", "capelet": "短披肩",
    "cloak": "披风", "robe": "长袍", "gown": "礼服", "blouse": "女式衬衫",
    "sweater": "毛衣", "cardigan": "开衫", "hoodie": "连帽卫衣", "vest": "马甲",
    "tunic": "束腰外衣", "poncho": "斗篷式上衣", "shawl": "披肩", "stole": "披巾",
    "gloves": "手套", "glove": "手套", "mittens": "连指手套", "boots": "靴子",
    "boot": "靴", "shoes": "鞋", "sandal": "凉鞋", "sandals": "凉鞋",
    "sneakers": "运动鞋", "slippers": "拖鞋", "heels": "高跟鞋", "pumps": "高跟鞋",
    "hat": "帽子", "cap": "帽", "beret": "贝雷帽", "bonnet": "软帽",
    "headband": "发箍", "hairband": "发箍", "hairclip": "发夹", "hairpin": "发簪",
    "ribbon": "缎带", "ribbons": "缎带", "bow": "蝴蝶结", "bows": "蝴蝶结",
    "choker": "颈饰", "collar": "衣领", "necktie": "领带", "tie": "领带",
    "bowtie": "领结", "scarf": "围巾", "neckerchief": "领巾", "ascot": "领巾",
    "cravat": "领巾", "belt": "腰带", "sash": "腰带", "apron": "围裙",
    "uniform": "制服", "swimsuit": "泳装", "bikini": "比基尼", "leotard": "紧身衣",
    "bodysuit": "紧身衣", "bodystocking": "连体丝袜", "catsuit": "连身衣",
    "stockings": "长袜", "thighhighs": "过膝袜", "thighhigh": "过膝袜",
    "socks": "袜子", "sock": "袜子", "pantyhose": "连裤袜", "tights": "紧身袜",
    "garter": "吊袜带", "garters": "吊袜带", "strap": "绑带", "straps": "绑带",
    "belts": "腰带", "band": "束带", "bands": "束带", "necklace": "项链",
    "earring": "耳环", "earrings": "耳环", "bracelet": "手镯", "bracelets": "手镯",
    "ring": "戒指", "rings": "戒指", "brooch": "胸针", "pendant": "吊坠",
    "clothes": "衣物", "clothing": "服饰", "outfit": "套装", "wear": "服饰",
    "legwear": "袜类", "footwear": "鞋类", "underwear": "内衣", "lingerie": "内衣",
    "bra": "胸罩", "panties": "内裤", "thong": "丁字裤", "briefs": "内裤",
    "shorts": "短裤", "jeans": "牛仔裤", "pants": "长裤", "trousers": "长裤",
    "overalls": "背带裤", "leggings": "紧身裤", "sleeves": "袖子", "sleeve": "袖子",
    "neckline": "领口", "corset": "束腰", "bustier": "紧身胸衣",
    "chemise": "薄内衣", "negligee": "薄纱睡裙", "nightgown": "睡裙",
    "pajamas": "睡衣", "sleepwear": "睡衣", "armor": "盔甲", "armour": "盔甲",
    "breastplate": "胸甲", "pauldron": "肩甲", "pauldrons": "肩甲",
    "gauntlet": "臂甲", "gauntlets": "臂甲", "helmet": "头盔", "shield": "盾牌",
    "mask": "面具", "goggles": "护目镜", "glasses": "眼镜", "eyepatch": "眼罩",
    "monocle": "单片眼镜", "headphones": "耳机", "headset": "头戴设备",
    "visor": "护目镜", "crown": "皇冠", "tiara": "小皇冠", "veil": "面纱",
    "halo": "光环", "jewelry": "首饰", "charm": "挂饰", "amulet": "护身符",
    "cross": "十字架", "star": "星星", "heart": "心形", "moon": "月亮",
    "sun": "太阳", "snow": "雪", "ice": "冰", "fire": "火", "water": "水",
    "wind": "风", "thunder": "雷", "lightning": "闪电", "shadow": "影子",
    "darkness": "黑暗", "holy": "神圣", "magic": "魔法", "magical": "魔法",
    "energy": "能量", "power": "力量", "mechanical": "机械", "robot": "机器人",
    "android": "人造人", "cyborg": "改造人", "animal": "动物", "cat": "猫",
    "dog": "狗", "fox": "狐狸", "wolf": "狼", "rabbit": "兔子", "bunny": "兔子",
    "bear": "熊", "mouse": "老鼠", "bird": "鸟", "snake": "蛇", "dragon": "龙",
    "demon": "恶魔", "angel": "天使", "devil": "魔鬼", "ghost": "幽灵",
    "zombie": "僵尸", "vampire": "吸血鬼", "witch": "女巫", "wizard": "巫师",
    "knight": "骑士", "ninja": "忍者", "samurai": "武士", "maid": "女仆",
    "nurse": "护士", "police": "警察", "soldier": "士兵", "military": "军用",
    "tactical": "战术", "combat": "战斗", "sport": "运动", "sports": "运动",
    "gym": "健身", "school": "学校", "academy": "学院", "idol": "偶像",
    "stage": "舞台", "dance": "舞蹈", "ballet": "芭蕾", "wedding": "婚礼",
    "bridal": "新娘", "funeral": "葬礼", "festival": "祭典", "christmas": "圣诞",
    "halloween": "万圣节", "valentine": "情人节", "easter": "复活节",
    "summer": "夏季", "winter": "冬季", "spring": "春季", "autumn": "秋季",
    "korean": "韩式", "chinese": "中式", "japanese": "日式", "western": "西式",
    "ancient": "古代", "modern": "现代", "futuristic": "未来风",
    "victorian": "维多利亚风", "gothic": "哥特", "punk": "朋克", "cyber": "赛博",
    "steampunk": "蒸汽朋克", "fantasy": "奇幻", "elegant": "优雅",
    "casual": "休闲", "formal": "正式", "traditional": "传统", "simple": "简约",
    "ornate": "华丽", "fluffy": "蓬松", "puffy": "蓬松",
    # 道具 / 武器
    "sword": "剑", "katana": "武士刀", "dagger": "短剑", "spear": "长枪",
    "lance": "长枪", "bow": "弓", "arrow": "箭", "quiver": "箭袋",
    "staff": "法杖", "wand": "魔杖", "scepter": "权杖", "scythe": "镰刀",
    "gun": "枪", "pistol": "手枪", "rifle": "步枪", "revolver": "左轮手枪",
    "ammunition": "弹药", "pouch": "袋子", "bag": "包", "backpack": "背包",
    "satchel": "挎包", "handbag": "手提包", "suitcase": "手提箱",
    "umbrella": "伞", "parasol": "阳伞", "fan": "扇子", "handfan": "折扇",
    "book": "书", "clipboard": "写字板", "syringe": "注射器",
    "stethoscope": "听诊器", "lantern": "灯笼", "torch": "火把", "candle": "蜡烛",
    "broom": "扫帚", "flower": "花", "flowers": "花", "rose": "玫瑰",
    "leaf": "叶子", "feather": "羽毛", "wing": "翅膀", "wings": "翅膀",
    "horn": "角", "horns": "角", "tail": "尾巴", "antlers": "鹿角",
    "talisman": "符咒", "talismans": "符咒", "scroll": "卷轴", "scrolls": "卷轴",
    "barcode": "条形码", "text": "文字", "letter": "字母", "number": "数字",
    "banner": "横幅", "flag": "旗", "sign": "标牌", "poster": "海报",
    "pouch": "小袋", "holster": "枪套", "sheath": "刀鞘", "scabbard": "刀鞘",
    # 状态 / 动作
    "holding": "手持", "wearing": "穿着", "covered": "被覆盖", "exposed": "露出",
    "revealing": "暴露", "cutout": "镂空", "open": "敞开", "closed": "合上",
    "around": "围绕", "behind": "背后", "front": "正面", "side": "侧面",
    "under": "下方", "over": "上方", "inner": "内层", "outer": "外层",
    "top": "上衣", "bottom": "下装", "up": "上", "down": "下",
    "on": "在", "in": "在", "with": "带", "without": "无", "no": "无",
    "adorned": "缀有", "intricate": "繁复", "surrounding": "环绕",
    "removed": "脱下", "unworn": "未穿", "fallen": "滑落", "slipping": "滑落",
    "outwear": "外穿", "outerwear": "外套", "jacket": "夹克",
}


# ---------------------------------------------------------------------------
# 3. 合并本地中文资料（延迟加载，缺失也不影响）
# ---------------------------------------------------------------------------
def _load_merged() -> Dict[str, str]:
    import json
    import os
    import sqlite3

    out: Dict[str, str] = {}
    base = r"D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Danbooru-Anima-Prompt\py"

    p = os.path.join(base, "zh_cn", "all_tags_cn.json")
    if os.path.isfile(p):
        try:
            for k, v in json.load(open(p, encoding="utf-8")).items():
                if v and re.search(r"[\u4e00-\u9fff]", str(v)):
                    out[norm(k)] = str(v).strip()
        except Exception:
            pass

    p = os.path.join(base, "weilin_tags.db")
    if os.path.isfile(p):
        try:
            con = sqlite3.connect(p)
            for text, desc in con.execute("SELECT text, desc FROM tag_tags"):
                if text and desc and re.search(r"[\u4e00-\u9fff]", str(desc)):
                    out[norm(text)] = str(desc).strip()
            con.close()
        except Exception:
            pass

    return out


try:
    MERGED: Dict[str, str] = _load_merged()
except Exception:  # pragma: no cover
    MERGED = {}

_CURATED_N = {norm(k): v for k, v in CURATED.items()}


def translate(tag: str, default: Optional[str] = None) -> str:
    """把标签翻译成中文；翻不了就返回原文（或给出的 default）。"""
    raw = str(tag or "").strip()
    if not raw:
        return default or raw
    if re.search(r"[\u4e00-\u9fff]", raw):
        return raw                                   # 本来就是中文
    key = norm(raw)
    if key in _CURATED_N:
        return _CURATED_N[key]
    if key in MERGED:
        return MERGED[key]

    parts = [p for p in re.split(r"[\s\-_/]+", raw) if p]
    if not parts:
        return default or raw
    out, hit = [], 0
    for p in parts:
        pk = p.lower()
        if pk in WORDS:
            out.append(WORDS[pk])
            hit += 1
        else:
            out.append(p)
    if hit == 0:
        return default or raw
    return "".join(out)


def coverage(tags) -> Dict[str, int]:
    """统计一组标签的翻译覆盖情况（给测试/文档用）。"""
    full = partial = none = 0
    for t in tags:
        tr = translate(t)
        if re.search(r"[\u4e00-\u9fff]", tr):
            if re.search(r"[a-zA-Z]", tr):
                partial += 1
            else:
                full += 1
        else:
            none += 1
    return {"full": full, "partial": partial, "none": none, "total": len(list(tags))}
