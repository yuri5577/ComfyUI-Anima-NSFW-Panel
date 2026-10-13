# -*- coding: utf-8 -*-
"""Anima NSFW 标签库（英文标签 + 中文说明）。

数据模型
--------
::

    {
      "schema": 1,
      "categories": [{"id", "zh", "en", "color", "desc"}, ...],
      "tags": [{"t": "english tag", "zh": "中文", "c": "category id",
                "g": "约束组(可选)", "r": "rating", "lvl": 0-3}, ...],
      "quality_presets": {...},
      "negative": {...},
      "intensity": {...},
    }

* ``g`` 约束组：同一组内互斥（前端选一个会自动取消同组其它标签，后端也会强制）。
* ``r`` 分级：``soft`` / ``hard`` / ``extreme`` / ``meta``，用于强度预置与警示。
* ``lvl`` = 该标签开始出现的强度档位（1=soft 2=hard 3=extreme）。
* 标签必须是 Anima（booru 词表）认识的英文写法，小写、下划线已转空格。
"""

SCHEMA = 1

CATEGORIES = [
    {"id": "subject", "zh": "角色/人数", "en": "Subject", "color": "#38bdf8",
     "desc": "人数与性别组合，决定整张图的角色结构"},
    {"id": "act", "zh": "性爱姿势", "en": "Sex Act", "color": "#f472b6",
     "desc": "主性交体位（同组互斥，选一个）"},
    {"id": "foreplay", "zh": "前戏/服务", "en": "Foreplay", "color": "#fb923c",
     "desc": "口交、乳交、手交、足交等非插入行为，可多选"},
    {"id": "solo", "zh": "自慰/单人", "en": "Solo Play", "color": "#a78bfa",
     "desc": "单人自慰、玩具、展示"},
    {"id": "outfit", "zh": "服装", "en": "Outfit", "color": "#e879f9",
     "desc": "服装本体，outfit_base 组互斥；下方「服装预设」一键成套"},
    {"id": "body", "zh": "身体/状态", "en": "Body & State", "color": "#22c55e",
     "desc": "身体部位、生理状态、体液反应"},
    {"id": "face", "zh": "表情/神态", "en": "Expression", "color": "#facc15",
     "desc": "高潮脸、失神、表情细节"},
    {"id": "fluid", "zh": "体液/射精", "en": "Fluids", "color": "#e2e8f0",
     "desc": "精液量、位置、淫水等"},
    {"id": "prop", "zh": "道具/束缚", "en": "Props & Bondage", "color": "#94a3b8",
     "desc": "情趣道具、束缚、调教器具"},
    {"id": "scene", "zh": "场景/视角", "en": "Scene & Angle", "color": "#2dd4bf",
     "desc": "地点、构图、镜头角度"},
    {"id": "character", "zh": "角色名", "en": "Character", "color": "#818cf8",
     "desc": "作品里的具体角色。8000 个角色按热度排序，热门默认可见，其余可搜索或按作品筛；同组互斥，一次只画一个角色"},
    {"id": "copyright", "zh": "游戏/作品", "en": "Copyright", "color": "#c084fc",
     "desc": "作品名（版权 tag）。加了它模型才知道画的是哪个游戏/动画的角色，"
             "配角色名一起用效果最好"},
    {"id": "style", "zh": "画质/风格", "en": "Quality & Style", "color": "#f59e0b",
     "desc": "质量标签、光照、画面风格"},
    {"id": "preset_extra", "zh": "预设补充", "en": "Preset Extras", "color": "#7c8aa5",
     "desc": "服装预设里用到、面板默认不展示的标签（发色/饰品/角色名等），"
             "被预设选中时会出现在已选区"},
]

# ---------------------------------------------------------------------------
# 标签本体。写得紧凑，方便后续手工维护。
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 剧情补充标签：催眠 / 时间停止 / 青梅竹马
# （并进 TAGS 主表，所以有中文名、有分级、参与强度过滤与 SFW 拦截）
# ---------------------------------------------------------------------------
STORY_TAGS = [
    # (英文, 中文, 分类, 互斥组, 分级, 强度档)
    # ---- 催眠系 ----
    ("spiral eyes", "漩涡眼（催眠标志）", "face", None, "hard", 2),
    ("swirl eyes", "螺旋眼", "face", None, "hard", 2),
    ("hypnosis", "催眠", "face", None, "hard", 2),
    ("mind control", "精神控制", "face", None, "hard", 2),
    ("trance", "恍惚失神", "face", None, "hard", 2),
    ("blank eyes", "空洞的眼神", "face", None, "hard", 2),
    ("dazed", "迷迷糊糊", "face", None, "soft", 1),
    ("unfocused", "目光失焦", "face", None, "soft", 1),
    ("obedient", "顺从", "face", None, "hard", 2),
    ("hypnotized", "被催眠状态", "face", None, "hard", 2),
    ("pendulum", "摆锤（催眠道具）", "prop", None, "hard", 2),
    ("glowing eyes", "发光的眼睛", "face", None, "hard", 2),
    ("pink pupils", "粉色瞳孔", "face", None, "hard", 2),
    # ---- 时间停止系 ----
    ("time stop", "时间停止", "scene", None, "hard", 2),
    ("frozen in time", "凝固在时间里", "scene", None, "hard", 2),
    ("clock", "时钟", "prop", None, "soft", 1),
    ("pocket watch", "怀表", "prop", None, "soft", 1),
    ("stopwatch", "秒表", "prop", None, "soft", 1),
    ("clock tower", "钟楼", "scene", None, "soft", 1),
    ("suspended motion", "动作悬停", "scene", None, "hard", 2),
    ("dust suspended in air", "悬浮的尘埃", "scene", None, "soft", 1),
    ("blue glow", "蓝色辉光", "style", "light", "soft", 1),
    ("time manipulation", "时间操纵", "scene", None, "hard", 2),
    # ---- 青梅竹马 / 日常 ----
    ("childhood friend", "青梅竹马", "subject", None, "soft", 1),
    ("neighbors", "邻居", "scene", None, "soft", 1),
    ("promise", "约定", "scene", None, "soft", 1),
    ("photo album", "相册", "prop", None, "soft", 1),
    ("childhood photo", "童年照片", "prop", None, "soft", 1),
    ("bloomers", "运动短裤", "outfit", "outfit_base", "soft", 1),
    ("randoseru", "小学生书包", "prop", None, "soft", 1),
    ("sunflower field", "向日葵田", "scene", None, "soft", 1),
    ("riverbank", "河堤", "scene", None, "soft", 1),
    ("reminiscing", "回忆", "scene", None, "soft", 1),
    ("nostalgic", "怀旧", "style", "tone", "soft", 1),
]

TAGS = [
    # ---------------- 角色 / 人数 ----------------
    ("1girl", "一名女性", "subject", "count", "soft", 1),
    ("1boy", "一名男性", "subject", "count", "soft", 1),
    ("2girls", "两名女性", "subject", "count", "soft", 1),
    ("2boys", "两名男性", "subject", "count", "soft", 1),
    ("1girl, 1boy", "一女一男（异性）", "subject", "pairing", "soft", 1),
    ("1girl, 2boys", "一女两男", "subject", "pairing", "hard", 2),
    ("3girls", "三名女性", "subject", "count", "soft", 1),
    ("multiple girls", "多名女性", "subject", "count", "soft", 1),
    ("multiple boys", "多名男性", "subject", "count", "hard", 2),
    ("1futa", "一名扶她", "subject", "pairing", "hard", 2),
    ("1girl, 1futa", "一女一扶她", "subject", "pairing", "hard", 2),
    ("2futas", "两名扶她", "subject", "pairing", "hard", 2),
    ("1futa, 1boy", "一扶她一男", "subject", "pairing", "hard", 2),
    ("futanari", "扶她（双性）", "subject", "trait", "hard", 2),
    ("solo", "单人", "subject", "solo", "soft", 1),
    ("solo focus", "单人特写", "subject", "solo", "soft", 1),
    ("hetero", "异性恋", "subject", "orientation", "soft", 1),
    ("yuri", "百合（女女）", "subject", "orientation", "soft", 1),
    ("yaoi", "耽美（男男）", "subject", "orientation", "soft", 1),
    ("netorare", "被夺爱/NTR", "subject", "theme", "hard", 2),
    ("ntr", "NTR", "subject", "theme", "hard", 2),
    ("gender bender", "性别转换", "subject", "theme", "hard", 2),
    ("tomboy", "女汉子/假小子", "subject", "trait", "soft", 1),
    ("milf", "熟女", "subject", "age", "hard", 2),
    ("loli", "幼女（高风险）", "subject", "age", "extreme", 3),
    ("shota", "正太（高风险）", "subject", "age", "extreme", 3),
    ("mature female", "成熟女性", "subject", "age", "soft", 1),
    ("muscular male", "肌肉男", "subject", "trait", "soft", 1),
    ("muscular female", "肌肉女", "subject", "trait", "soft", 1),
    ("monster", "怪物", "subject", "partner", "hard", 2),
    ("orc", "兽人", "subject", "partner", "hard", 2),
    ("tentacles", "触手", "subject", "partner", "extreme", 3),
    ("machine", "机械", "subject", "partner", "hard", 2),
    ("ghost", "幽灵", "subject", "partner", "hard", 2),
    ("furry", "兽人/毛茸茸", "subject", "partner", "hard", 2),
    ("kemonomimi", "兽耳娘", "subject", "trait", "soft", 1),

    # ---------------- 性爱姿势 ----------------
    ("missionary", "传教士体位", "act", "position", "hard", 2),
    ("cowgirl position", "女上位（骑乘）", "act", "position", "hard", 2),
    ("reverse cowgirl position", "反向女上位", "act", "position", "hard", 2),
    ("girl on top", "女性在上", "act", "position", "hard", 2),
    ("boy on top", "男性在上", "act", "position", "hard", 2),
    ("doggystyle", "后入式", "act", "position", "hard", 2),
    ("sex from behind", "从背后插入", "act", "position", "hard", 2),
    ("standing sex", "站立性交", "act", "position", "hard", 2),
    ("suspended congress", "抱起来操（悬空）", "act", "position", "hard", 2),
    ("spooning", "侧卧位", "act", "position", "hard", 2),
    ("mating press", "交配压制（压腿）", "act", "position", "hard", 2),
    ("prone bone", "趴压式", "act", "position", "hard", 2),
    ("piledriver", "打桩机（倒立）", "act", "position", "extreme", 3),
    ("full nelson", "全纳尔逊", "act", "position", "extreme", 3),
    ("standing full nelson", "站立全纳尔逊", "act", "position", "extreme", 3),
    ("legs up", "双腿抬起", "act", "position", "hard", 2),
    ("leg lock", "双腿夹锁", "act", "position", "hard", 2),
    ("straddling", "跨坐", "act", "position", "hard", 2),
    ("grinding", "摩擦顶弄", "act", "motion", "hard", 2),
    ("bouncing", "上下弹动", "act", "motion", "hard", 2),
    ("deep penetration", "深度插入", "act", "depth", "hard", 2),
    ("rough sex", "粗暴性爱", "act", "tone", "hard", 2),
    ("gentle sex", "温柔性爱", "act", "tone", "soft", 1),
    ("passionate kiss", "深吻", "act", "tone", "soft", 1),
    ("sex", "性交", "act", "core", "hard", 2),
    ("vaginal", "阴道性交", "act", "core", "hard", 2),
    ("anal", "肛交", "act", "core", "extreme", 3),
    ("double penetration", "双重插入", "act", "core", "extreme", 3),
    ("gangbang", "轮奸", "act", "core", "extreme", 3),
    ("threesome", "三人行", "act", "core", "hard", 2),
    ("orgy", "群交", "act", "core", "extreme", 3),
    ("bukkake", "颜射", "act", "core", "hard", 2),
    ("rape", "强暴（高风险）", "act", "tone", "extreme", 3),
    ("netorase", "被旁观性爱", "act", "tone", "extreme", 3),
    ("public sex", "公开性爱", "act", "place", "extreme", 3),
    ("exhibitionism", "露出癖", "act", "tone", "hard", 2),
    ("masturbation", "自慰", "act", "solo", "hard", 2),

    # ---------------- 前戏 / 服务 ----------------
    ("fellatio", "口交（含入）", "foreplay", "oral", "hard", 2),
    ("oral", "口交", "foreplay", "oral", "hard", 2),
    ("deepthroat", "深喉", "foreplay", "oral", "extreme", 3),
    ("irrumatio", "被顶喉", "foreplay", "oral", "extreme", 3),
    ("cunnilingus", "舔阴", "foreplay", "oral", "hard", 2),
    ("licking penis", "舔阴茎", "foreplay", "oral", "hard", 2),
    ("licking pussy", "舔小穴", "foreplay", "oral", "hard", 2),
    ("licking nipple", "舔乳头", "foreplay", "oral", "hard", 2),
    ("sucking fingers", "吸手指", "foreplay", "oral", "soft", 1),
    ("kissing", "接吻", "foreplay", "oral", "soft", 1),
    ("french kiss", "舌吻", "foreplay", "oral", "soft", 1),
    ("69", "69 式互舔", "foreplay", "oral", "hard", 2),
    ("face sitting", "坐脸", "foreplay", "oral", "hard", 2),
    ("paizuri", "乳交", "foreplay", "nonpenetrative", "hard", 2),
    ("breast press", "乳房夹压", "foreplay", "nonpenetrative", "hard", 2),
    ("handjob", "手交", "foreplay", "nonpenetrative", "hard", 2),
    ("footjob", "足交", "foreplay", "nonpenetrative", "hard", 2),
    ("thigh sex", "腿交", "foreplay", "nonpenetrative", "hard", 2),
    ("armpit sex", "腋交", "foreplay", "nonpenetrative", "hard", 2),
    ("hairjob", "发交", "foreplay", "nonpenetrative", "hard", 2),
    ("glansjob", "龟头摩擦", "foreplay", "nonpenetrative", "hard", 2),
    ("sumata", "素股（摩擦不插入）", "foreplay", "nonpenetrative", "hard", 2),
    ("fellatio + paizuri", "口交+乳交", "foreplay", "combo", "hard", 2),
    ("handjob + paizuri", "手交+乳交", "foreplay", "combo", "hard", 2),
    ("footjob + handjob", "足交+手交", "foreplay", "combo", "hard", 2),
    ("cum on breasts", "射在胸部", "foreplay", "result", "hard", 2),
    ("cum on face", "射在脸上", "foreplay", "result", "hard", 2),
    ("cum on tongue", "射在舌头上", "foreplay", "result", "extreme", 3),
    ("cum in mouth", "射在嘴里", "foreplay", "result", "hard", 2),
    ("cum swap", "精液互换", "foreplay", "result", "extreme", 3),
    ("saliva", "唾液", "foreplay", "result", "hard", 2),
    ("saliva trail", "口水拉丝", "foreplay", "result", "hard", 2),
    ("spit", "吐口水", "foreplay", "result", "extreme", 3),
    ("spitroast", "前后夹击", "foreplay", "combo", "extreme", 3),
    ("double blowjob", "双人口交", "foreplay", "combo", "extreme", 3),

    # ---------------- 自慰 / 单人 ----------------
    ("masturbating", "自慰中", "solo", "self", "hard", 2),
    ("fingering", "手指插入", "solo", "self", "hard", 2),
    ("fingering herself", "手指插自己", "solo", "self", "hard", 2),
    ("touching self", "抚摸自己", "solo", "self", "hard", 2),
    ("hand between legs", "手在腿间", "solo", "self", "hard", 2),
    ("hand on own breast", "手放在自己胸上", "solo", "self", "hard", 2),
    ("grabbing own breast", "揉自己的胸", "solo", "self", "hard", 2),
    ("nipple stimulation", "刺激乳头", "solo", "self", "hard", 2),
    ("clit stimulation", "刺激阴蒂", "solo", "self", "hard", 2),
    ("spread pussy", "掰开小穴", "solo", "present", "extreme", 3),
    ("spread ass", "掰开屁股", "solo", "present", "extreme", 3),
    ("presenting", "展示（摆姿势）", "solo", "present", "hard", 2),
    ("presenting armpit", "展示腋下", "solo", "present", "hard", 2),
    ("spread legs", "张开双腿", "solo", "pose", "hard", 2),
    ("legs apart", "双腿分开", "solo", "pose", "hard", 2),
    ("arched back", "弓起的背", "solo", "pose", "hard", 2),
    ("on all fours", "四肢着地", "solo", "pose", "hard", 2),
    ("kneeling", "跪姿", "solo", "pose", "soft", 1),
    ("squatting", "蹲姿", "solo", "pose", "soft", 1),
    ("bent over", "弯腰前倾", "solo", "pose", "hard", 2),
    ("top-down bottom-up", "头下脚上", "solo", "pose", "hard", 2),
    ("sex toy", "性玩具", "solo", "toy", "hard", 2),
    ("vibrator", "振动棒", "solo", "toy", "hard", 2),
    ("dildo", "假阳具", "solo", "toy", "hard", 2),
    ("anal beads", "肛门拉珠", "solo", "toy", "extreme", 3),
    ("plug", "肛塞", "solo", "toy", "extreme", 3),
    ("onahole", "飞机杯", "solo", "toy", "hard", 2),
    ("sex machine", "炮机", "solo", "toy", "extreme", 3),
    ("toy insertion", "玩具插入", "solo", "toy", "extreme", 3),
    ("holding sex toy", "拿着性玩具", "solo", "toy", "hard", 2),
    ("condom", "避孕套", "solo", "toy", "hard", 2),
    ("used condom", "用过的避孕套", "solo", "toy", "extreme", 3),
    ("condom in mouth", "嘴里含避孕套", "solo", "toy", "extreme", 3),

    # ---------------- 服装本体 ----------------
    # outfit_base 组 = 一套主服装，互斥。
    # 以下标签全部核对过 Anima 的本地角色词表高频分布（7999 个角色），不是自造词。
    ("serafuku", "水手服（经典）", "outfit", "outfit_base", "soft", 1),
    ("school uniform", "校服（统称）", "outfit", "outfit_base", "soft", 1),
    ("winter uniform", "冬季校服", "outfit", "outfit_base", "soft", 1),
    ("gym uniform", "体操服", "outfit", "outfit_base", "soft", 1),
    ("bloomers", "运动短裤（布鲁玛）", "outfit", None, "soft", 1),
    ("sailor dress", "水手连衣裙", "outfit", "outfit_base", "soft", 1),
    ("shirt", "衬衫", "outfit", "outfit_base", "soft", 1),
    ("white shirt", "白衬衫", "outfit", "outfit_base", "soft", 1),
    ("collared shirt", "翻领衬衫", "outfit", "outfit_base", "soft", 1),
    ("sleeveless shirt", "无袖上衣", "outfit", "outfit_base", "soft", 1),
    ("blouse", "女式衬衫", "outfit", "outfit_base", "soft", 1),
    ("sweater", "毛衣", "outfit", "outfit_base", "soft", 1),
    ("cardigan", "开衫", "outfit", "outfit_base", "soft", 1),
    ("hoodie", "连帽卫衣", "outfit", "outfit_base", "soft", 1),
    ("hooded jacket", "连帽夹克", "outfit", "outfit_base", "soft", 1),
    ("jacket", "夹克", "outfit", "outfit_base", "soft", 1),
    ("blazer", "西装外套", "outfit", "outfit_base", "soft", 1),
    ("cropped jacket", "短款夹克", "outfit", "outfit_base", "soft", 1),
    ("fur-trimmed jacket", "毛领夹克", "outfit", "outfit_base", "soft", 1),
    ("coat", "大衣", "outfit", "outfit_base", "soft", 1),
    ("lab coat", "白大褂", "outfit", "outfit_base", "soft", 1),
    ("overalls", "背带裤", "outfit", "outfit_base", "soft", 1),
    ("business suit", "职业西装", "outfit", "outfit_base", "soft", 1),
    ("office lady", "OL 职业装", "outfit", "outfit_base", "soft", 1),
    ("military uniform", "军装", "outfit", "outfit_base", "soft", 1),
    ("naval uniform", "海军制服", "outfit", "outfit_base", "soft", 1),
    ("peaked cap", "大檐帽", "outfit", None, "soft", 1),
    ("nurse", "护士服", "outfit", "outfit_base", "soft", 1),
    ("maid", "女仆装", "outfit", "outfit_base", "soft", 1),
    ("maid headdress", "女仆头饰", "outfit", None, "soft", 1),
    ("waitress", "服务生制服", "outfit", "outfit_base", "soft", 1),
    ("apron", "围裙", "outfit", None, "soft", 1),
    ("white apron", "白围裙", "outfit", None, "soft", 1),
    ("miko", "巫女服", "outfit", "outfit_base", "soft", 1),
    ("nontraditional miko", "改良巫女服", "outfit", "outfit_base", "soft", 1),
    ("nun", "修女服", "outfit", "outfit_base", "soft", 1),
    ("kimono", "和服", "outfit", "outfit_base", "soft", 1),
    ("yukata", "浴衣", "outfit", "outfit_base", "soft", 1),
    ("hakama", "袴", "outfit", None, "soft", 1),
    ("china dress", "旗袍", "outfit", "outfit_base", "soft", 1),
    ("cheongsam", "长衫/旗袍", "outfit", "outfit_base", "soft", 1),
    ("hanfu", "汉服", "outfit", "outfit_base", "soft", 1),
    ("ao dai", "越南长衫", "outfit", "outfit_base", "soft", 1),
    ("sari", "纱丽", "outfit", "outfit_base", "soft", 1),
    ("dirndl", "巴伐利亚裙", "outfit", "outfit_base", "soft", 1),
    ("gothic lolita", "哥特萝莉装", "outfit", "outfit_base", "soft", 1),
    ("lolita fashion", "洛丽塔装", "outfit", "outfit_base", "soft", 1),
    ("victorian", "维多利亚风", "outfit", "outfit_base", "soft", 1),
    ("wedding dress", "婚纱", "outfit", "outfit_base", "soft", 1),
    ("evening gown", "晚礼服", "outfit", "outfit_base", "soft", 1),
    ("cocktail dress", "鸡尾酒裙", "outfit", "outfit_base", "soft", 1),
    ("white dress", "白色连衣裙", "outfit", "outfit_base", "soft", 1),
    ("black dress", "黑色连衣裙", "outfit", "outfit_base", "soft", 1),
    ("sundress", "吊带夏裙", "outfit", "outfit_base", "soft", 1),
    ("strapless dress", "抹胸连衣裙", "outfit", "outfit_base", "soft", 1),
    ("sleeveless dress", "无袖连衣裙", "outfit", "outfit_base", "soft", 1),
    ("one-piece swimsuit", "连体泳装", "outfit", "outfit_base", "hard", 2),
    ("school swimsuit", "死库水", "outfit", "outfit_base", "hard", 2),
    ("competition swimsuit", "竞技泳装", "outfit", "outfit_base", "hard", 2),
    ("bikini", "比基尼", "outfit", "outfit_base", "hard", 2),
    ("micro bikini", "超小比基尼", "outfit", "outfit_base", "hard", 2),
    ("side-tie bikini bottom", "系带比基尼", "outfit", None, "hard", 2),
    ("highleg leotard", "高叉体操服", "outfit", "outfit_base", "hard", 2),
    ("leotard", "紧身连体衣", "outfit", "outfit_base", "hard", 2),
    ("bodysuit", "全身紧身衣", "outfit", "outfit_base", "hard", 2),
    ("plugsuit", "驾驶服（EVA）", "outfit", "outfit_base", "hard", 2),
    ("latex", "乳胶衣", "outfit", "outfit_base", "hard", 2),
    ("leather", "皮革装", "outfit", "outfit_base", "hard", 2),
    ("tracksuit", "运动套装", "outfit", "outfit_base", "soft", 1),
    ("jersey", "球衣", "outfit", "outfit_base", "soft", 1),
    ("cheerleader", "拉拉队服", "outfit", "outfit_base", "soft", 1),
    ("idol", "偶像打歌服", "outfit", "outfit_base", "soft", 1),
    ("stage costume", "舞台服装", "outfit", "outfit_base", "soft", 1),
    ("magical girl", "魔法少女装", "outfit", "outfit_base", "soft", 1),
    ("witch hat", "女巫帽", "outfit", None, "soft", 1),
    ("armor", "盔甲", "outfit", "outfit_base", "soft", 1),
    ("plate armor", "板甲", "outfit", "outfit_base", "soft", 1),
    ("chainmail", "锁子甲", "outfit", "outfit_base", "soft", 1),
    ("bikini armor", "比基尼铠甲", "outfit", "outfit_base", "extreme", 3),
    ("knight", "骑士装", "outfit", "outfit_base", "soft", 1),
    ("ninja", "忍者装", "outfit", "outfit_base", "soft", 1),
    ("samurai", "武士装", "outfit", "outfit_base", "soft", 1),
    ("military", "军装风", "outfit", None, "soft", 1),
    ("cape", "斗篷", "outfit", None, "soft", 1),
    ("cloak", "披风", "outfit", None, "soft", 1),
    ("hood", "兜帽", "outfit", None, "soft", 1),
    ("hood up", "兜帽戴上", "outfit", "hood_state", "soft", 1),
    ("hood down", "兜帽放下", "outfit", "hood_state", "soft", 1),
    ("detached sleeves", "分离袖", "outfit", None, "soft", 1),
    ("sailor collar", "水手领", "outfit", None, "soft", 1),
    ("detached collar", "假领", "outfit", None, "soft", 1),
    ("skirt", "裙子", "outfit", None, "soft", 1),
    ("pleated skirt", "百褶裙", "outfit", None, "soft", 1),
    ("miniskirt", "超短裙", "outfit", None, "hard", 2),
    ("plaid skirt", "格子裙", "outfit", None, "soft", 1),
    ("high-waist skirt", "高腰裙", "outfit", None, "soft", 1),
    ("shorts", "短裤", "outfit", None, "soft", 1),
    ("short shorts", "超短裤", "outfit", None, "hard", 2),
    ("bike shorts", "骑行短裤", "outfit", None, "soft", 1),
    ("jeans", "牛仔裤", "outfit", None, "soft", 1),
    ("pantyhose", "连裤袜", "outfit", None, "hard", 2),
    ("thighhighs", "过膝袜", "outfit", None, "hard", 2),
    ("black thighhighs", "黑色过膝袜", "outfit", None, "hard", 2),
    ("white thighhighs", "白色过膝袜", "outfit", None, "hard", 2),
    ("stockings", "长筒袜", "outfit", None, "soft", 1),
    ("garter belt", "吊袜带", "outfit", None, "hard", 2),
    ("lingerie", "内衣", "outfit", "outfit_base", "hard", 2),
    ("lace panties", "蕾丝内裤", "outfit", None, "hard", 2),
    ("bra", "胸罩", "outfit", None, "hard", 2),
    ("sports bra", "运动内衣", "outfit", None, "hard", 2),
    ("corset", "束腰", "outfit", None, "hard", 2),
    ("high heels", "高跟鞋", "outfit", None, "soft", 1),
    ("boots", "靴子", "outfit", None, "soft", 1),
    ("thigh boots", "过膝长靴", "outfit", None, "hard", 2),
    ("sandals", "凉鞋", "outfit", None, "soft", 1),
    ("loafers", "乐福鞋", "outfit", None, "soft", 1),
    ("sneakers", "运动鞋", "outfit", None, "soft", 1),
    ("gloves", "手套", "outfit", None, "soft", 1),
    ("black gloves", "黑手套", "outfit", None, "soft", 1),
    ("white gloves", "白手套", "outfit", None, "soft", 1),
    ("elbow gloves", "长手套", "outfit", None, "soft", 1),
    ("fingerless gloves", "露指手套", "outfit", None, "soft", 1),
    ("bridal gauntlets", "新娘长手套", "outfit", None, "soft", 1),
    ("goggles", "护目镜", "outfit", None, "soft", 1),
    ("goggles on head", "护目镜架在头上", "outfit", None, "soft", 1),
    ("mask", "面罩", "outfit", None, "soft", 1),
    ("hair ribbon", "发带", "outfit", None, "soft", 1),
    ("hair bow", "蝴蝶结发饰", "outfit", None, "soft", 1),
    ("hairband", "发箍", "outfit", None, "soft", 1),
    ("hair ornament", "发饰", "outfit", None, "soft", 1),
    ("beret", "贝雷帽", "outfit", None, "soft", 1),
    ("baseball cap", "棒球帽", "outfit", None, "soft", 1),
    ("top hat", "礼帽", "outfit", None, "soft", 1),
    ("crown", "皇冠", "outfit", None, "soft", 1),
    ("tiara", "小皇冠", "outfit", None, "soft", 1),
    ("veil", "头纱", "outfit", None, "soft", 1),
    ("necktie", "领带", "outfit", None, "soft", 1),
    ("bowtie", "领结", "outfit", None, "soft", 1),
    ("scarf", "围巾", "outfit", None, "soft", 1),
    ("sash", "腰带/绶带", "outfit", None, "soft", 1),
    ("belt", "皮带", "outfit", None, "soft", 1),
    ("choker", "颈圈饰", "outfit", None, "soft", 1),
    ("necklace", "项链", "outfit", None, "soft", 1),
    ("earrings", "耳环", "outfit", None, "soft", 1),
    ("bracelet", "手镯", "outfit", None, "soft", 1),

    # ---------------- 身体 / 状态 ----------------
    # 着装状态：nude_state 组只放互相冲突的三种裸体程度
    ("nude", "全裸", "body", "nude_state", "hard", 2),
    ("completely nude", "完全赤裸", "body", None, "hard", 2),
    ("topless", "上半身赤裸", "body", "nude_state", "hard", 2),
    ("bottomless", "下半身赤裸", "body", "nude_state", "hard", 2),
    # 服装的「状态」（不是服装本身，因此不参与 outfit_base 互斥）
    ("no panties", "没穿内裤", "body", None, "hard", 2),
    ("no bra", "没穿胸罩", "body", None, "hard", 2),
    ("undressing", "正在脱衣", "body", None, "hard", 2),
    ("clothes pull", "拉衣服", "body", None, "hard", 2),
    ("skirt lift", "掀裙子", "body", None, "hard", 2),
    ("shirt lift", "掀上衣", "body", None, "hard", 2),
    ("strap slip", "肩带滑落", "body", None, "hard", 2),
    ("wardrobe malfunction", "衣服走光", "body", None, "hard", 2),
    ("torn clothes", "被撕破的衣服", "body", None, "extreme", 3),
    ("wet clothes", "湿身衣着", "body", None, "hard", 2),
    ("see-through", "透视", "body", None, "hard", 2),
    # 胸围：bust 组互斥
    ("large breasts", "大胸", "body", "bust", "soft", 1),
    ("huge breasts", "巨乳", "body", "bust", "hard", 2),
    ("flat chest", "贫乳", "body", "bust", "soft", 1),
    ("cleavage", "乳沟", "body", None, "soft", 1),
    ("nipples", "乳头", "body", None, "hard", 2),
    ("puffy nipples", "凸起的乳头", "body", None, "hard", 2),
    ("thick thighs", "粗大腿", "body", None, "soft", 1),
    ("wide hips", "宽胯", "body", None, "soft", 1),
    ("slim waist", "细腰", "body", None, "soft", 1),
    ("pubic hair", "阴毛", "body", "pubic", "hard", 2),
    ("shaved pussy", "剃毛小穴", "body", "pubic", "hard", 2),
    ("pussy", "小穴", "body", None, "hard", 2),
    ("pussy juice", "淫水", "body", None, "hard", 2),
    ("clitoris", "阴蒂", "body", None, "hard", 2),
    ("anus", "肛门", "body", None, "extreme", 3),
    ("gaping", "扩张/张开的洞", "body", None, "extreme", 3),
    ("penis", "阴茎", "body", None, "hard", 2),
    ("large penis", "粗大阴茎", "body", "penis_size", "hard", 2),
    ("erection", "勃起", "body", None, "hard", 2),
    ("bulge", "鼓起", "body", None, "hard", 2),
    ("testicles", "睾丸", "body", None, "hard", 2),
    ("veins", "血管", "body", None, "hard", 2),
    ("blush", "脸红", "body", None, "soft", 1),
    ("sweat", "汗水", "body", None, "hard", 2),
    ("sweat drop", "汗珠", "body", None, "hard", 2),
    ("trembling", "颤抖", "body", None, "hard", 2),
    ("shivering", "发抖", "body", None, "hard", 2),
    ("trembling thighs", "大腿颤抖", "body", None, "hard", 2),
    ("arched spine", "弓背", "body", None, "hard", 2),
    ("toes curling", "脚趾蜷缩", "body", None, "hard", 2),
    ("bound wrists", "手腕被绑", "body", None, "extreme", 3),
    ("pregnant", "怀孕", "body", None, "extreme", 3),
    ("pubic tattoo", "私处纹身", "body", None, "hard", 2),
    ("tanlines", "晒痕", "body", None, "soft", 1),
    ("lotion", "润滑油", "body", None, "hard", 2),
    ("oil", "油光身体", "body", None, "hard", 2),

    # ---------------- 表情 / 神态 ----------------
    ("ahegao", "阿黑颜", "face", None, "hard", 2),
    ("rolling eyes", "翻白眼", "face", None, "hard", 2),
    ("empty eyes", "失神空洞的眼神", "face", None, "hard", 2),
    ("heart-shaped pupils", "心形瞳孔", "face", None, "hard", 2),
    ("tongue out", "伸出舌头", "face", None, "hard", 2),
    ("open mouth", "张嘴", "face", None, "soft", 1),
    ("parted lips", "微张的唇", "face", None, "soft", 1),
    ("biting lip", "咬唇", "face", None, "soft", 1),
    ("licking lips", "舔嘴唇", "face", None, "hard", 2),
    ("drooling", "流口水", "face", None, "extreme", 3),
    ("tears", "眼泪", "face", None, "hard", 2),
    ("crying", "哭泣", "face", None, "hard", 2),
    ("teary eyes", "泪眼汪汪", "face", None, "hard", 2),
    ("half-closed eyes", "半闭眼", "face", "eyelids", "hard", 2),
    ("heavy-lidded eyes", "迷离的眼神", "face", "eyelids", "hard", 2),
    ("looking at viewer", "看向观众", "face", "gaze_dir", "soft", 1),
    ("looking back", "回眸", "face", "gaze_turn", "soft", 1),
    ("looking up", "向上看", "face", "gaze_v", "soft", 1),
    ("looking down", "向下看", "face", "gaze_v", "soft", 1),
    ("eye contact", "对视", "face", None, "soft", 1),
    ("naughty face", "淫荡的表情", "face", None, "hard", 2),
    ("smug", "得意", "face", None, "soft", 1),
    ("shy", "害羞", "face", None, "soft", 1),
    ("embarrassed", "难为情", "face", None, "soft", 1),
    ("pleasure", "愉悦", "face", None, "hard", 2),
    ("ecstasy", "极乐", "face", None, "extreme", 3),
    ("painful pleasure", "痛苦又愉悦", "face", None, "extreme", 3),
    ("mind break", "精神崩坏", "face", None, "extreme", 3),
    ("orgasm", "高潮", "face", None, "extreme", 3),
    ("afterglow", "余韵", "face", None, "hard", 2),
    ("expressionless", "无表情", "face", None, "hard", 2),
    ("bored", "无聊/不情愿", "face", None, "hard", 2),
    ("sleeping", "睡着（睡奸向）", "face", None, "extreme", 3),
    ("angry", "生气", "face", None, "soft", 1),
    ("grin", "咧嘴笑", "face", None, "soft", 1),
    ("moaning", "呻吟", "face", None, "hard", 2),
    ("breath", "喘息", "face", None, "hard", 2),

    # ---------------- 体液 / 射精 ----------------
    # 注意：射精位置类标签不设互斥组，允许同时叠多个位置
    ("cum", "精液", "fluid", None, "hard", 2),
    ("excessive cum", "大量精液", "fluid", "cum_amount", "extreme", 3),
    ("cum in pussy", "内射", "fluid", None, "hard", 2),
    ("creampie", "中出", "fluid", None, "hard", 2),
    ("cum overflow", "精液溢出", "fluid", None, "extreme", 3),
    ("cum in ass", "肛门内射", "fluid", None, "extreme", 3),
    ("cum on body", "射在身上", "fluid", None, "hard", 2),
    ("cum on stomach", "射在腹部", "fluid", None, "hard", 2),
    ("cum on back", "射在背上", "fluid", None, "hard", 2),
    ("cum on hair", "射在头发上", "fluid", None, "hard", 2),
    ("cum on hands", "射在手上", "fluid", None, "hard", 2),
    ("cum on feet", "射在脚上", "fluid", None, "hard", 2),
    ("cum on clothes", "射在衣服上", "fluid", None, "hard", 2),
    ("cum string", "精液拉丝", "fluid", None, "extreme", 3),
    ("cum bubble", "精液气泡", "fluid", None, "extreme", 3),
    ("cum pool", "精液水洼", "fluid", None, "extreme", 3),
    ("bukkake", "颜射（多人）", "fluid", None, "hard", 2),
    ("facial", "脸上射精", "fluid", None, "hard", 2),
    ("precum", "前列腺液", "fluid", None, "hard", 2),
    ("squirting", "潮吹", "fluid", None, "extreme", 3),
    ("female ejaculation", "女性射精", "fluid", None, "extreme", 3),
    ("wet pussy", "湿润的小穴", "fluid", None, "hard", 2),
    ("pussy juice trail", "淫水拉丝", "fluid", None, "hard", 2),
    ("milking", "挤奶", "fluid", None, "extreme", 3),
    ("lactation", "泌乳", "fluid", None, "extreme", 3),
    ("breast milk", "母乳", "fluid", None, "extreme", 3),
    ("urine", "尿液（高风险）", "fluid", None, "extreme", 3),
    ("drool", "口水", "fluid", None, "hard", 2),

    # ---------------- 道具 / 束缚 ----------------
    # bondage 组：主束缚方式互斥（选了绳缚就不用再选项圈当主方式）
    ("bondage", "束缚", "prop", None, "extreme", 3),
    ("shibari", "日式绳缚", "prop", "bondage_kind", "extreme", 3),
    ("rope", "绳索", "prop", None, "extreme", 3),
    ("collar", "项圈", "prop", None, "extreme", 3),
    ("leash", "牵引绳", "prop", None, "extreme", 3),
    ("handcuffs", "手铐", "prop", "bondage_kind", "extreme", 3),
    ("blindfold", "眼罩", "prop", None, "extreme", 3),
    ("gag", "口塞", "prop", "gag_kind", "extreme", 3),
    ("ball gag", "球形口塞", "prop", "gag_kind", "extreme", 3),
    ("chastity belt", "贞操带", "prop", None, "extreme", 3),
    ("spreader bar", "扩张杆", "prop", None, "extreme", 3),
    ("cuffs", "皮铐", "prop", "bondage_kind", "extreme", 3),
    ("bound", "被绑住", "prop", None, "extreme", 3),
    ("restrained", "被限制行动", "prop", None, "extreme", 3),
    ("suspension", "吊缚", "prop", None, "extreme", 3),
    ("whip", "鞭子", "prop", "bdsm_tool", "extreme", 3),
    ("paddle", "拍打板", "prop", "bdsm_tool", "extreme", 3),
    ("crop", "马鞭", "prop", "bdsm_tool", "extreme", 3),
    ("wax play", "滴蜡", "prop", None, "extreme", 3),
    ("nipple clamp", "乳夹", "prop", None, "extreme", 3),
    ("spanking", "打屁股", "prop", None, "hard", 2),
    ("red buttocks", "被打红的屁股", "prop", None, "extreme", 3),
    ("whip marks", "鞭痕", "prop", None, "extreme", 3),
    ("pet play", "宠物游戏", "prop", None, "extreme", 3),
    ("dog collar", "狗项圈", "prop", None, "extreme", 3),
    ("cat lingerie", "猫耳内衣", "prop", None, "hard", 2),
    ("latex", "乳胶衣", "prop", None, "hard", 2),
    ("leather", "皮革装", "prop", None, "hard", 2),
    ("stockings", "长筒袜", "prop", None, "soft", 1),
    ("fishnet", "渔网袜", "prop", None, "hard", 2),
    ("high heels", "高跟鞋", "prop", None, "soft", 1),
    ("crotchless panties", "开裆内裤", "prop", None, "extreme", 3),
    ("pasties", "乳贴", "prop", None, "hard", 2),
    ("condom on penis", "戴着避孕套", "prop", "toy_kind", "hard", 2),
    ("used condom", "用过的避孕套", "prop", None, "extreme", 3),
    ("dildo in mouth", "嘴里含假阳具", "prop", None, "extreme", 3),
    ("double dildo", "双头假阳具", "prop", "toy_kind", "extreme", 3),
    ("strap-on", "穿戴式假阳具", "prop", "toy_kind", "extreme", 3),
    ("fleshlight", "飞机杯", "prop", "toy_kind", "hard", 2),
    ("onahole", "名器", "prop", "toy_kind", "hard", 2),
    ("tentacle sex", "触手性交", "prop", "creature_kind", "extreme", 3),
    ("oviposition", "产卵", "prop", "creature_kind", "extreme", 3),
    ("egg insertion", "塞蛋", "prop", "creature_kind", "extreme", 3),

    # ---------------- 场景 / 视角 ----------------
    # place：主场景互斥
    ("on bed", "在床上", "scene", "place", "soft", 1),
    ("bedroom", "卧室", "scene", None, "soft", 1),
    ("messy bed", "凌乱的床", "scene", None, "hard", 2),
    ("love hotel", "情人旅馆", "scene", "place", "hard", 2),
    ("bathroom", "浴室", "scene", "place", "hard", 2),
    ("shower", "淋浴间", "scene", "place", "hard", 2),
    ("bathtub", "浴缸", "scene", None, "hard", 2),
    ("onsen", "温泉", "scene", "place", "hard", 2),
    ("public restroom", "公共厕所", "scene", "place", "extreme", 3),
    ("classroom", "教室", "scene", "place", "hard", 2),
    ("school desk", "课桌", "scene", None, "hard", 2),
    ("office", "办公室", "scene", "place", "hard", 2),
    ("desk", "办公桌", "scene", None, "hard", 2),
    ("car", "车内", "scene", "place", "hard", 2),
    ("backseat", "后座", "scene", None, "hard", 2),
    ("elevator", "电梯", "scene", "place", "extreme", 3),
    ("against wall", "靠墙", "scene", None, "hard", 2),
    ("against glass", "贴着玻璃", "scene", None, "extreme", 3),
    ("mirror", "镜子", "scene", None, "hard", 2),
    ("outdoors", "户外", "scene", "place", "hard", 2),
    # 光照：不设互斥（可以又逆光又霓虹）
    ("night", "夜晚", "scene", None, "soft", 1),
    ("dim lighting", "昏暗灯光", "scene", None, "hard", 2),
    ("candlelight", "烛光", "scene", None, "hard", 2),
    ("neon lights", "霓虹灯", "scene", None, "hard", 2),
    ("steam", "水汽/蒸汽", "scene", None, "hard", 2),
    # 景别：framing 组互斥
    ("close-up", "特写", "scene", "framing", "hard", 2),
    ("extreme close-up", "极端特写", "scene", "framing", "hard", 2),
    ("full body", "全身", "scene", "framing", "soft", 1),
    ("upper body", "上半身", "scene", "framing", "soft", 1),
    ("cowboy shot", "七分身（牛仔镜头）", "scene", "framing", "soft", 1),
    ("portrait", "肖像", "scene", "framing", "soft", 1),
    # 视角：camera 组互斥
    ("pov", "第一人称视角", "scene", "camera", "hard", 2),
    ("point of view", "视点镜头", "scene", "camera", "hard", 2),
    ("from below", "仰视", "scene", "camera", "hard", 2),
    ("from above", "俯视", "scene", "camera", "hard", 2),
    ("from behind", "从背后看", "scene", "camera", "hard", 2),
    ("from side", "侧面", "scene", "camera", "hard", 2),
    ("dutch angle", "荷兰角（倾斜构图）", "scene", "camera", "hard", 2),
    ("top-down view", "正上方视角", "scene", "camera", "hard", 2),
    ("worm's-eye view", "虫视视角", "scene", "camera", "hard", 2),
    ("bird's-eye view", "鸟瞰视角", "scene", "camera", "hard", 2),
    ("foreshortening", "透视缩短", "scene", None, "hard", 2),
    # 焦点区域互斥
    ("crotch focus", "胯部焦点", "scene", "focus_area", "extreme", 3),
    ("ass focus", "臀部焦点", "scene", "focus_area", "hard", 2),
    ("breast focus", "胸部焦点", "scene", "focus_area", "hard", 2),
    ("feet focus", "足部焦点", "scene", "focus_area", "hard", 2),
    # 漫画效果符号
    ("motion lines", "速度线/动作线", "scene", None, "hard", 2),
    ("heart", "爱心符号", "scene", None, "hard", 2),
    ("spoken heart", "爱心语音符号", "scene", None, "hard", 2),
    # 元标签（打码方式互斥）
    ("censored", "打码", "scene", "censor", "hard", 2),
    ("mosaic censoring", "马赛克打码", "scene", "censor", "hard", 2),
    ("bar censor", "黑条打码", "scene", "censor", "hard", 2),
    ("uncensored", "无码", "scene", "censor", "hard", 2),
    ("explicit", "露骨", "scene", None, "hard", 2),

    # ---------------- 画质 / 风格 ----------------
    ("masterpiece", "杰作", "style", "quality", "soft", 1),
    ("best quality", "最佳质量", "style", "quality", "soft", 1),
    ("high quality", "高质量", "style", "quality", "soft", 1),
    ("highres", "高分辨率", "style", "quality", "soft", 1),
    ("absurdres", "极高分辨率", "style", "quality", "soft", 1),
    ("score_9", "评分 9", "style", "quality", "soft", 1),
    ("score_8_up", "评分 8+", "style", "quality", "soft", 1),
    ("score_7", "评分 7", "style", "quality", "soft", 1),
    ("detailed anatomy", "细致的人体结构", "style", "detail", "soft", 1),
    ("detailed skin", "细腻的皮肤", "style", "detail", "soft", 1),
    ("detailed background", "细致的背景", "style", "detail", "soft", 1),
    ("anime illustration", "动漫插画", "style", "medium", "soft", 1),
    ("anime coloring", "动漫上色", "style", "medium", "soft", 1),
    ("soft lighting", "柔和光照", "style", "light", "soft", 1),
    ("rim light", "轮廓光", "style", "light", "soft", 1),
    ("backlighting", "逆光", "style", "light", "soft", 1),
    ("dramatic lighting", "戏剧性光照", "style", "light", "soft", 1),
    ("cinematic lighting", "电影感光照", "style", "light", "soft", 1),
    ("volumetric lighting", "体积光", "style", "light", "soft", 1),
    ("glowing", "发光", "style", "light", "soft", 1),
    ("wet", "湿润质感", "style", "detail", "soft", 1),
    ("oil skin", "油亮肌肤", "style", "detail", "soft", 1),
    ("realistic", "写实", "style", "medium", "soft", 1),
    ("semi-realistic", "半写实", "style", "medium", "soft", 1),
    ("monochrome", "单色", "style", "medium", "soft", 1),
    ("sketch", "素描风", "style", "medium", "soft", 1),
    ("watercolor", "水彩风", "style", "medium", "soft", 1),
    ("flat color", "平涂上色", "style", "medium", "soft", 1),
    ("artist name", "画师风格占位", "style", "artist", "soft", 1),
]

# 剧情补充标签并进主表
TAGS += STORY_TAGS

# ---------------------------------------------------------------------------
# 质量预置
# ---------------------------------------------------------------------------

QUALITY_PRESETS = {
    "turbo（Turbo LoRA 12 步）": "masterpiece, best quality, absurdres, newest, year 2025",
    "base（原版 28~32 步）": "masterpiece, best quality, highres, absurdres, newest, year 2025, detailed",
    "pony（score_ 系）": "score_9, score_8_up, score_7_up, masterpiece, best quality, absurdres",
    "极简（只留质量词）": "best quality, absurdres",
    "无（自己写）": "",
}

# ---------------------------------------------------------------------------
# 负面提示词基线与分段
# ---------------------------------------------------------------------------

NEGATIVE_BASE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, "
    "bad anatomy, bad proportions, bad hands, extra fingers, missing fingers, "
    "fused fingers, extra limbs, extra arms, extra legs, malformed limbs, "
    "deformed, disfigured, mutated, duplicate, cropped, out of frame, "
    "watermark, signature, username, logo, unrelated text, text"
)

NEGATIVE_EXTRA = {
    "手部修复": "bad hands, extra fingers, missing fingers, fused fingers, "
                "extra digits, fewer digits, malformed hands, mutated hands, "
                "poorly drawn hands, disconnected limbs",
    "面部修复": "crossed eyes, asymmetrical eyes, distorted face, duplicate face, "
                "mutated face, disfigured face, poorly drawn face, ugly face",
    "人体结构": "bad anatomy, bad proportions, long neck, extra limbs, fused body, "
                "conjoined, missing limbs, unnatural pose, twisted body",
    "NSFW 安全": "censored, mosaic censoring, bar censor, watermark, text, "
                 "child, underage, loli, shota, toddler, infant",
    # 「画面干净」顺带负责压掉乱码文字：放大模型的会把背景的纹理
    # 幻化成假文字（实测出现过 TWENT / ADDRESS 之类的乱码标题），
    # 所以这里把 text / watermark / signature 一类全列上。
    "画面干净": "jpeg artifacts, grain, noise, overexposed, underexposed, "
                "flat lighting, washed out, blurry lineart, messy lineart, "
                "text, watermark, signature, username, logo, artist name, "
                "copyright name, web address, dated, english text, chinese text, "
                "speech bubble, caption, letterboxed, ui, interface",
    "防伪影": "greyscale, monochrome, sketch, unfinished, signature, artist name, "
              "copyright name, dated, web address",
}

# 强度档位 -> 中文说明（前端展示用）
INTENSITY = {
    "soft": {"zh": "轻柔 / 氛围", "desc": "以暗示、身体与表情为主，插入行为关闭"},
    "hard": {"zh": "露骨 / 强度", "desc": "含明确性交、体液与露骨身体描写（默认）"},
    "extreme": {"zh": "极限 / 高风险", "desc": "含极端、调教、触手等高风险内容"},
}


# ---------------------------------------------------------------------------
# 服装预设里用到的辅助标签（发色/瞳色/道具/角色名等）
# ---------------------------------------------------------------------------
# 归类说明：
#   * 归到已有分类（body/face/scene/prop）的标签会正常出现在面板里，排序也正确；
#   * 归到 "preset_extra" 的标签（主要是角色名与版权名）打 hidden 标记，
#     面板默认不展示，但仍参与去重 / 互斥 / 已选展示。

PRESET_EXTRA_SUPPLEMENT = [
    # 外观（会出现在「身体/状态」分类）
    ("aqua hair", "水蓝色头发", "body", None, "soft", 1),
    ("pink hair", "粉色头发", "body", None, "soft", 1),
    ("blue hair", "蓝色头发", "body", None, "soft", 1),
    ("purple hair", "紫色头发", "body", None, "soft", 1),
    ("blonde hair", "金发", "body", None, "soft", 1),
    ("silver hair", "银发", "body", None, "soft", 1),
    ("blue eyes", "蓝眼睛", "body", None, "soft", 1),
    ("green eyes", "绿眼睛", "body", None, "soft", 1),
    ("twintails", "双马尾", "body", None, "soft", 1),
    ("long hair", "长发", "body", None, "soft", 1),
    ("short hair", "短发", "body", None, "soft", 1),
    ("ponytail", "马尾", "body", None, "soft", 1),
    ("braid", "麻花辫", "body", None, "soft", 1),
    ("twin braids", "双麻花辫", "body", None, "soft", 1),
    ("single braid", "单侧麻花辫", "body", None, "soft", 1),
    ("bob cut", "波波头", "body", None, "soft", 1),
    ("two side up", "两侧束发", "body", None, "soft", 1),
    ("hair bun", "丸子头", "body", None, "soft", 1),
    ("pointy ears", "尖耳", "body", None, "soft", 1),
    ("horns", "角", "body", None, "soft", 1),
    ("halo", "光环", "body", None, "soft", 1),
    ("feathered wings", "羽翼", "body", None, "soft", 1),
    ("black wings", "黑色翅膀", "body", None, "soft", 1),
    ("demon wings", "恶魔之翼", "body", None, "soft", 1),
    ("demon tail", "恶魔尾巴", "body", None, "soft", 1),
    ("bare shoulders", "裸肩", "body", None, "soft", 1),
    ("bare legs", "光腿", "body", None, "soft", 1),
    ("midriff", "露出腹部", "body", None, "hard", 2),
    ("navel", "肚脐", "body", None, "soft", 1),
    ("covered nipples", "乳头被遮挡", "body", None, "hard", 2),
    ("wet", "湿身", "body", None, "hard", 2),
    ("smile", "微笑", "face", None, "soft", 1),
    ("dancing", "跳舞", "face", None, "soft", 1),
    ("blush", "脸红", "body", None, "soft", 1),

    # 道具 / 手中物品
    ("holding book", "拿着书", "prop", None, "soft", 1),
    ("holding weapon", "拿着武器", "prop", None, "soft", 1),
    ("holding sword", "拿着剑", "prop", None, "soft", 1),
    ("holding staff", "拿着法杖", "prop", None, "soft", 1),
    ("holding wand", "拿着魔杖", "prop", None, "soft", 1),
    ("holding bow", "拿着弓", "prop", None, "soft", 1),
    ("holding microphone", "拿着麦克风", "prop", None, "soft", 1),
    ("holding bouquet", "拿着捧花", "prop", None, "soft", 1),
    ("holding tray", "端着托盘", "prop", None, "soft", 1),
    ("holding clipboard", "拿着写字板", "prop", None, "soft", 1),
    ("sword", "剑", "prop", None, "soft", 1),
    ("katana", "武士刀", "prop", None, "soft", 1),
    ("spear", "长枪", "prop", None, "soft", 1),
    ("kunai", "苦无", "prop", None, "soft", 1),
    ("quiver", "箭袋", "prop", None, "soft", 1),
    ("wand", "魔杖", "prop", None, "soft", 1),
    ("syringe", "注射器", "prop", None, "hard", 2),
    ("microphone stand", "麦克风架", "prop", None, "soft", 1),
    ("pom poms", "啦啦球", "prop", None, "soft", 1),
    ("parasol", "阳伞", "prop", None, "soft", 1),
    ("straw hat", "草帽", "prop", None, "soft", 1),
    ("bag", "包", "prop", None, "soft", 1),
    ("cross", "十字架", "prop", None, "soft", 1),
    ("rosary", "念珠", "prop", None, "soft", 1),
    ("pumpkin", "南瓜", "prop", None, "soft", 1),
    ("jewelry", "首饰", "prop", None, "soft", 1),
    ("pearl necklace", "珍珠项链", "prop", None, "soft", 1),
    ("broom", "扫帚", "prop", None, "soft", 1),
    ("flower", "花", "prop", None, "soft", 1),
    ("hair flower", "发间花饰", "prop", None, "soft", 1),
    ("hair tubes", "发管", "prop", None, "soft", 1),
    ("glasses", "眼镜", "prop", None, "soft", 1),
    ("earrings", "耳环", "prop", None, "soft", 1),

    # 服装细项补充
    ("frills", "荷叶边", "outfit", None, "soft", 1),
    ("ribbon", "缎带", "outfit", None, "soft", 1),
    ("red ribbon", "红缎带", "outfit", None, "soft", 1),
    ("red bow", "红蝴蝶结", "outfit", None, "soft", 1),
    ("neckerchief", "领巾", "outfit", None, "soft", 1),
    ("pencil skirt", "铅笔裙", "outfit", None, "soft", 1),
    ("long skirt", "长裙", "outfit", None, "soft", 1),
    ("black skirt", "黑色裙子", "outfit", None, "soft", 1),
    ("red skirt", "红色裙子", "outfit", None, "soft", 1),
    ("leather skirt", "皮裙", "outfit", None, "hard", 2),
    ("loose socks", "泡泡袜", "outfit", None, "soft", 1),
    ("white socks", "白袜", "outfit", None, "soft", 1),
    ("kneehighs", "及膝袜", "outfit", None, "soft", 1),
    ("black pantyhose", "黑色连裤袜", "outfit", None, "hard", 2),
    ("white pantyhose", "白色连裤袜", "outfit", None, "hard", 2),
    ("black bra", "黑色胸罩", "outfit", None, "hard", 2),
    ("black panties", "黑色内裤", "outfit", None, "hard", 2),
    ("panties", "内裤", "outfit", None, "hard", 2),
    ("white bikini", "白色比基尼", "outfit", None, "hard", 2),
    ("black bikini", "黑色比基尼", "outfit", None, "hard", 2),
    ("highleg", "高叉", "outfit", None, "hard", 2),
    ("name tag", "名牌", "outfit", None, "soft", 1),
    ("short sleeves", "短袖", "outfit", None, "soft", 1),
    ("crop top", "露脐短上衣", "outfit", None, "hard", 2),
    ("puffy sleeves", "泡泡袖", "outfit", None, "soft", 1),
    ("wide sleeves", "宽袖", "outfit", None, "soft", 1),
    ("side slit", "侧开叉", "outfit", None, "hard", 2),
    ("backless", "露背", "outfit", None, "hard", 2),
    ("skin tight", "紧身", "outfit", None, "soft", 1),
    ("shiny", "亮面光泽", "outfit", None, "soft", 1),
    ("zipper", "拉链", "outfit", None, "soft", 1),
    ("fur trim", "毛边", "outfit", None, "soft", 1),
    ("epaulettes", "肩章", "outfit", None, "soft", 1),
    ("lace", "蕾丝", "outfit", None, "soft", 1),
    ("breastplate", "胸甲", "outfit", None, "soft", 1),
    ("gauntlets", "臂甲", "outfit", None, "soft", 1),
    ("arm guards", "护臂", "outfit", None, "soft", 1),
    ("helmet", "头盔", "outfit", None, "soft", 1),
    ("latex boots", "乳胶长靴", "outfit", None, "hard", 2),
    ("latex gloves", "乳胶手套", "outfit", None, "hard", 2),
    ("leather gloves", "皮手套", "outfit", None, "hard", 2),
    ("tunic", "束腰外衣", "outfit", None, "soft", 1),
    ("robe", "长袍", "outfit", None, "soft", 1),
    ("habit", "修女头巾长袍", "outfit", None, "soft", 1),
    ("tutu", "芭蕾舞裙", "outfit", None, "soft", 1),
    ("ballet slippers", "芭蕾舞鞋", "outfit", None, "soft", 1),
    ("swim cap", "泳帽", "outfit", None, "soft", 1),
    ("santa costume", "圣诞装", "outfit", "outfit_base", "soft", 1),
    ("santa hat", "圣诞帽", "outfit", None, "soft", 1),
    ("red bodysuit", "红色紧身衣", "outfit", "outfit_base", "hard", 2),
    ("white bodysuit", "白色紧身衣", "outfit", "outfit_base", "hard", 2),
    ("racing suit", "赛车服", "outfit", "outfit_base", "soft", 1),
    ("police uniform", "警察制服", "outfit", "outfit_base", "soft", 1),
    ("flight attendant", "空乘制服", "outfit", "outfit_base", "soft", 1),
    ("sarashi", "裹胸布", "outfit", None, "hard", 2),
    ("obi", "和服腰带", "outfit", None, "soft", 1),
    ("geta", "木屐", "outfit", None, "soft", 1),
    ("tabi", "足袋", "outfit", None, "soft", 1),
    ("hakama skirt", "袴裙", "outfit", None, "soft", 1),
    ("furisode", "振袖", "outfit", "outfit_base", "soft", 1),
    ("maiko", "舞妓", "outfit", "outfit_base", "soft", 1),
    ("japanese clothes", "日式服饰", "outfit", None, "soft", 1),

    # 场景补充
    ("beach", "海边", "scene", "place", "soft", 1),
    ("water", "水中", "scene", None, "soft", 1),
    ("shrine", "神社", "scene", "place", "soft", 1),
    ("locker room", "更衣室", "scene", "place", "hard", 2),
    ("festival", "祭典", "scene", None, "soft", 1),
    ("night", "夜晚", "scene", None, "soft", 1),
    ("snow", "雪", "scene", None, "soft", 1),
    ("autumnal", "秋意", "scene", None, "soft", 1),
    ("sunlight", "阳光", "scene", None, "soft", 1),
    ("spotlight", "聚光灯", "scene", None, "soft", 1),
    ("sparkle", "闪光", "scene", None, "soft", 1),
    ("halloween", "万圣节", "scene", None, "soft", 1),
    ("standing", "站立", "scene", None, "soft", 1),
    ("sitting", "坐着", "scene", None, "soft", 1),
    ("hands in pockets", "手插口袋", "scene", None, "soft", 1),
    ("hands on hips", "双手叉腰", "scene", None, "soft", 1),

    # ---- 服装库里常见、之前被兜底成 hidden 的标签，提升为正常标签 ----
    ("argyle", "菱形格纹", "outfit", None, "soft", 1),
    ("anklet", "脚链", "outfit", None, "soft", 1),
    ("arm belt", "臂带", "outfit", None, "soft", 1),
    ("arm garter", "大臂吊带", "outfit", None, "hard", 2),
    ("arm strap", "手臂绑带", "outfit", None, "soft", 1),
    ("arm tattoo", "手臂纹身", "body", None, "hard", 2),
    ("animal hood", "动物造型兜帽", "outfit", None, "soft", 1),
    ("animal collar", "动物项圈", "outfit", None, "hard", 2),
    ("animal ear headphones", "兽耳耳机", "outfit", None, "soft", 1),
    ("areola slip", "乳晕走光", "body", None, "extreme", 3),
    ("back bow", "背后蝴蝶结", "outfit", None, "soft", 1),
    ("bandeau", "抹胸", "outfit", "outfit_base", "hard", 2),
    ("barcode tattoo", "条形码纹身", "body", None, "hard", 2),
    ("bell", "铃铛", "prop", None, "soft", 1),
    ("belt buckle", "皮带扣", "outfit", None, "soft", 1),
    ("bodystocking", "连体丝袜", "outfit", None, "hard", 2),
    ("bracelet", "手镯", "prop", None, "soft", 1),
    ("bridal veil", "新娘头纱", "outfit", None, "soft", 1),
    ("brooch", "胸针", "prop", None, "soft", 1),
    ("bustier", "紧身胸衣", "outfit", "outfit_base", "hard", 2),
    ("capelet", "短披肩", "outfit", None, "soft", 1),
    ("collar chain", "项圈链条", "prop", None, "extreme", 3),
    ("cravat", "领巾", "outfit", None, "soft", 1),
    ("double-breasted", "双排扣", "outfit", None, "soft", 1),
    ("ear piercing", "耳洞", "body", None, "soft", 1),
    ("eyepatch", "眼罩", "outfit", None, "hard", 2),
    ("facial tattoo", "面部纹身", "body", None, "hard", 2),
    ("fanny pack", "腰包", "prop", None, "soft", 1),
    ("fishnet top", "渔网上衣", "outfit", "outfit_base", "hard", 2),
    ("floral print", "花卉印花", "outfit", None, "soft", 1),
    ("fringe trim", "流苏边", "outfit", None, "soft", 1),
    ("hairclip", "发夹", "outfit", None, "soft", 1),
    ("handfan", "折扇", "prop", None, "soft", 1),
    ("head chain", "头链", "prop", None, "soft", 1),
    ("heart tattoo", "心形纹身", "body", None, "hard", 2),
    ("high collar", "高领", "outfit", None, "soft", 1),
    ("hip vent", "胯部开衩", "outfit", None, "hard", 2),
    ("hoop earrings", "圈状耳环", "prop", None, "soft", 1),
    ("jacket on shoulders", "外套披肩上", "outfit", None, "soft", 1),
    ("knee boots", "及膝长靴", "outfit", None, "soft", 1),
    ("knee pads", "护膝", "outfit", None, "soft", 1),
    ("lace choker", "蕾丝颈饰", "outfit", None, "soft", 1),
    ("lace trim", "蕾丝花边", "outfit", None, "soft", 1),
    ("layered skirt", "层叠裙", "outfit", None, "soft", 1),
    ("leg ribbon", "腿部缎带", "outfit", None, "soft", 1),
    ("loincloth", "腰布", "outfit", "outfit_base", "hard", 2),
    ("loose clothes", "宽松衣物", "outfit", None, "soft", 1),
    ("lowleg", "低腰", "outfit", None, "hard", 2),
    ("mandarin collar", "立领", "outfit", None, "soft", 1),
    ("mary janes", "玛丽珍鞋", "outfit", None, "soft", 1),
    ("mismatched legwear", "不对称袜", "outfit", None, "soft", 1),
    ("nightgown", "睡裙", "outfit", "outfit_base", "hard", 2),
    ("off shoulder", "露肩", "outfit", None, "hard", 2),
    ("one shoulder", "单肩", "outfit", None, "hard", 2),
    ("open clothes", "敞开的衣服", "outfit", None, "hard", 2),
    ("oversized clothes", "超大号衣物", "outfit", None, "soft", 1),
    ("pasties", "乳贴", "outfit", None, "hard", 2),
    ("pendant", "吊坠", "prop", None, "soft", 1),
    ("plaid", "格纹", "outfit", None, "soft", 1),
    ("pleated microskirt", "百褶超短裙", "outfit", None, "hard", 2),
    ("plunging neckline", "深 V 领口", "outfit", None, "hard", 2),
    ("pocket", "口袋", "outfit", None, "soft", 1),
    ("puff sleeves", "泡泡袖", "outfit", None, "soft", 1),
    ("ribbon trim", "缎带镶边", "outfit", None, "soft", 1),
    ("scrunchie", "大肠发圈", "outfit", None, "soft", 1),
    ("sheer thighhighs", "半透明过膝袜", "outfit", None, "hard", 2),
    ("shirt tucked in", "衬衫扎进裙里", "outfit", None, "soft", 1),
    ("shoulder bag", "单肩包", "prop", None, "soft", 1),
    ("shoulder cutout", "肩部镂空", "outfit", None, "hard", 2),
    ("side cutout", "侧面镂空", "outfit", None, "hard", 2),
    ("single thighhigh", "单腿过膝袜", "outfit", None, "hard", 2),
    ("skindentation", "衣物勒痕", "body", None, "hard", 2),
    ("sleepwear", "睡衣", "outfit", "outfit_base", "hard", 2),
    ("spaghetti strap", "细吊带", "outfit", None, "hard", 2),
    ("spiked choker", "铆钉项圈", "outfit", None, "extreme", 3),
    ("stethoscope", "听诊器", "prop", None, "soft", 1),
    ("stitches", "缝合线", "body", None, "extreme", 3),
    ("strapless", "无肩带", "outfit", None, "hard", 2),
    ("striped clothes", "条纹衣物", "outfit", None, "soft", 1),
    ("stud earrings", "耳钉", "prop", None, "soft", 1),
    ("sunglasses", "太阳镜", "outfit", None, "soft", 1),
    ("sunglasses on head", "太阳镜架头上", "outfit", None, "soft", 1),
    ("tassel", "流苏", "outfit", None, "soft", 1),
    ("taut dress", "紧身裙", "outfit", "outfit_base", "hard", 2),
    ("thigh strap", "大腿绑带", "outfit", None, "hard", 2),
    ("torn pantyhose", "破洞连裤袜", "outfit", None, "hard", 2),
    ("turtleneck", "高领毛衣", "outfit", "outfit_base", "soft", 1),
    ("tuxedo", "燕尾服", "outfit", "outfit_base", "soft", 1),
    ("two-tone hair", "双色头发", "body", None, "soft", 1),
    ("underboob", "乳下露出", "body", None, "extreme", 3),
    ("underbust", "胸下缘", "body", None, "hard", 2),
    ("waist apron", "围腰", "outfit", None, "soft", 1),
    ("waist bow", "腰间蝴蝶结", "outfit", None, "soft", 1),
    ("watch", "手表", "prop", None, "soft", 1),
    ("wrist cuffs", "腕套", "outfit", None, "soft", 1),
    ("zettai ryouiki", "绝对领域", "body", None, "hard", 2),
]


# ---------------------------------------------------------------------------
# 作品名（版权 tag）
# ---------------------------------------------------------------------------
# 来源：本机 Anima 角色库里 7999 个角色的 trigger 第二段（826 个不同作品），
# 取出现频次最高的那批。加版权 tag 能显著提高角色还原度（角色名 + 作品名一起给）。
# 分组仅用于面板筛选，不参与互斥（同一作品当然只该选一个，但跨作品混搭是用户自由）。

# ---------------------------------------------------------------------------
# 轻小说（38 部）
# ---------------------------------------------------------------------------
# 每一条都经过 Animadex 缩略图探测确认「该作品有角色图」，也就是库里有它。
# 用独立的 light_novel_base 互斥组：轻小说和游戏是两类作品，
# 让它们能同时选（比如「原神角色 + 刀剑神域角色」这种跨作品同人）。
LIGHT_NOVELS = [
    # (作品名, 中文, 近似角色数)
    ('toaru majutsu no index', '魔法禁书目录 / 某科学的超电磁炮', 23),
    ('sword art online', '刀剑神域', 21),
    ('monogatari (series)', '物语系列', 14),
    ('kagerou project', '阳炎计划', 13),
    ('high school dxd', '恶魔高校 DxD', 11),
    ('kono subarashii sekai ni shukufuku wo!', '为美好的世界献上祝福！', 10),
    ('to love-ru', '出包王女', 10),
    ('zero no tsukaima', '零之使魔', 8),
    ('date a live', '约会大作战', 7),
    ('ore no imouto ga konna ni kawaii wake ga nai', '我的妹妹不可能那么可爱', 6),
    ('durarara!!', '无头骑士异闻录', 6),
    ('toradora!', '龙与虎', 5),
    ('mushoku tensei', '无职转生', 5),
    ('hyouka', '冰菓', 5),
    ('chuunibyou demo koi ga shitai!', '中二病也要谈恋爱', 5),
    ('infinite stratos', '无限斯特拉托斯', 5),
    ('overlord (maruyama)', 'Overlord', 4),
    ('dungeon ni deai wo motomeru no wa machigatteiru darou ka', '在地下城寻求邂逅是否搞错了什么', 4),
    ('goblin slayer!', '哥布林杀手', 4),
    ('boku wa tomodachi ga sukunai', '我的朋友很少', 4),
    ('tate no yuusha no nariagari', '盾之勇者成名录', 3),
    ('tensei shitara slime datta ken', '关于我转生变成史莱姆这档事', 3),
    ('shakugan no shana', '灼眼的夏娜', 3),
    ('spice and wolf', '狼与香辛料', 2),
    ('no game no life', '游戏人生', 2),
    ('haiyore! nyaruko-san', '袭来！美少女邪神', 2),
    ('baka to test to shoukanjuu', '笨蛋、测验、召唤兽', 1),
    ('mahouka koukou no rettousei', '魔法科高中的劣等生', 1),
    ('gate - jieitai ka no chi nite kaku tatakaeri', 'GATE 自卫队', 1),
    ('log horizon', '记录的地平线', 1),
    ('youjo senki', '谭雅战记', 1),
    ('accel world', '加速世界', 1),
    ('kino no tabi', '奇诺之旅', 1),
    ('strike the blood', '噬血狂袭', 1),
    ('youkoso jitsuryoku shijou shugi no kyoushitsu e', '欢迎来到实力至上主义教室', 1),
    ('rakudai kishi no cavalry', '落第骑士英雄谭', 1),
    ('shinmai maou no testament', '新妹魔王的契约者', 1),
    ('highschool of the dead', '学园默示录', 1),
]


def light_novel_tags():
    """展开成标签条目，挂到 light_novel_base 互斥组。"""
    out, seen = [], set()
    for name, zh, _n in LIGHT_NOVELS:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((name, zh, "copyright", "light_novel_base", "soft", 1))
    return out


LIGHT_NOVEL_TAGS = light_novel_tags()

COPYRIGHT_GROUPS = [
    {"id": "game", "zh": "游戏", "en": "Games", "icon": "🎮"},
    {"id": "gacha", "zh": "手游/抽卡", "en": "Gacha", "icon": "📱"},
    {"id": "anime", "zh": "动画/漫画", "en": "Anime & Manga", "icon": "📺"},
    {"id": "light_novel", "zh": "轻小说", "en": "Light Novels", "icon": "📖"},
    {"id": "idol", "zh": "偶像/音乐", "en": "Idol & Music", "icon": "🎤"},
    {"id": "other", "zh": "其它", "en": "Others", "icon": "🌐"},
]

# (作品名, 中文, 分组, 近似角色数)
COPYRIGHTS = [
    # ---- 手游 / 抽卡 ----
    ("blue archive", "蔚蓝档案", "gacha", 203),
    ("azur lane", "碧蓝航线", "gacha", 167),
    ("kantai collection", "舰队 Collection", "gacha", 401),
    ("girls' frontline", "少女前线", "gacha", 93),
    ("fate/grand order", "Fate/Grand Order", "gacha", 102),
    ("arknights", "明日方舟", "gacha", 201),
    ("genshin impact", "原神", "gacha", 136),
    ("honkai (series)", "崩坏系列", "gacha", 99),
    ("honkai: star rail", "崩坏：星穹铁道", "gacha", 60),
    ("umamusume", "赛马娘", "gacha", 121),
    ("princess connect!", "公主连结", "gacha", 31),
    ("granblue fantasy", "碧蓝幻想", "gacha", 75),
    ("project sekai", "世界计划", "gacha", 40),
    ("nikke", "胜利女神：妮姬", "gacha", 30),
    ("punishing: gray raven", "战双帕弥什", "gacha", 20),
    ("touken ranbu", "刀剑乱舞", "gacha", 51),
    ("love live!", "LoveLive!", "gacha", 57),
    ("bang dream!", "BanG Dream!", "gacha", 34),
    ("idolmaster", "偶像大师", "gacha", 211),
    ("project moon", "Project Moon", "gacha", 28),
    ("limbus company", "边狱公司", "gacha", 20),
    ("reverse: 1999", "重返未来：1999", "gacha", 18),
    ("wuthering waves", "鸣潮", "gacha", 25),
    ("zenless zone zero", "绝区零", "gacha", 22),
    ("neural cloud", "云图计划", "gacha", 18),

    # ---- 游戏 ----
    ("fate (series)", "Fate 系列", "game", 336),
    ("pokemon", "宝可梦", "game", 553),
    ("fire emblem", "火焰纹章", "game", 147),
    ("final fantasy", "最终幻想", "game", 94),
    ("dragon quest", "勇者斗恶龙", "game", 29),
    ("the legend of zelda", "塞尔达传说", "game", 29),
    ("xenoblade chronicles (series)", "异度神剑", "game", 27),
    ("persona", "女神异闻录", "game", 42),
    ("persona 5", "女神异闻录 5", "game", 25),
    ("league of legends", "英雄联盟", "game", 58),
    ("nier (series)", "尼尔系列", "game", 20),
    ("nier: automata", "尼尔：机械纪元", "game", 30),
    ("tales of (series)", "传说系列", "game", 45),
    ("street fighter", "街头霸王", "game", 25),
    ("tekken", "铁拳", "game", 15),
    ("kingdom hearts", "王国之心", "game", 20),
    ("devil may cry", "鬼泣", "game", 12),
    ("resident evil", "生化危机", "game", 20),
    ("dark souls (series)", "黑暗之魂", "game", 12),
    ("elden ring", "艾尔登法环", "game", 15),
    ("gensou suikoden", "幻想水浒传", "game", 10),
    ("ragnarok online", "仙境传说", "game", 35),
    ("guilty gear", "罪恶装备", "game", 20),
    ("blazblue", "苍翼默示录", "game", 18),
    ("hyperdimension neptunia", "次元游戏海王星", "game", 25),
    ("atelier (series)", "炼金工房系列", "game", 20),
    ("splatoon", "斯普拉遁", "game", 20),
    ("super mario (series)", "超级马里奥", "game", 15),
    ("metroid", "银河战士", "game", 10),

    # ---- 动画 / 漫画 ----
    ("touhou", "东方 Project", "anime", 203),
    ("original", "原创角色", "other", 108),
    ("vocaloid", "Vocaloid", "idol", 61),
    ("hololive", "Hololive", "idol", 260),
    ("nijisanji", "Nijisanji", "idol", 107),
    ("precure", "光之美少女", "anime", 108),
    ("bishoujo senshi sailor moon", "美少女战士", "anime", 30),
    ("cardcaptor sakura", "魔卡少女樱", "anime", 24),
    ("lyrical nanoha", "魔法少女奈叶", "anime", 41),
    ("mahou shoujo madoka magica", "魔法少女小圆", "anime", 35),
    ("boku no hero academia", "我的英雄学院", "anime", 32),
    ("kimetsu no yaiba", "鬼灭之刃", "anime", 30),
    ("jujutsu kaisen", "咒术回战", "anime", 30),
    ("chainsaw man", "电锯人", "anime", 25),
    ("one piece", "海贼王", "anime", 35),
    ("dragon ball", "龙珠", "anime", 35),
    ("naruto", "火影忍者", "anime", 30),
    ("bleach", "死神", "anime", 25),
    ("jojo no kimyou na bouken", "JOJO 的奇妙冒险", "anime", 68),
    ("gundam", "高达", "anime", 68),
    ("evangelion", "新世纪福音战士", "anime", 25),
    ("neon genesis evangelion", "EVA", "anime", 40),
    ("code geass", "叛逆的鲁路修", "anime", 25),
    ("danganronpa (series)", "弹丸论破", "anime", 56),
    ("umineko no naku koro ni", "海猫鸣泣之时", "anime", 33),
    ("higurashi no naku koro ni", "寒蝉鸣泣之时", "anime", 25),
    ("yu-gi-oh!", "游戏王", "anime", 38),
    ("kemono friends", "兽娘动物园", "anime", 71),
    ("girls und panzer", "少女与战车", "anime", 74),
    ("love live! sunshine!!", "LoveLive! Sunshine!!", "idol", 25),
    ("sono bisque doll wa koi wo suru", "更衣人偶坠入爱河", "anime", 20),
    ("yahari ore no seishun lovecome wa machigatteiru.", "我的青春恋爱物语果然有问题",
     "anime", 15),
    ("saenai heroine no sodatekata", "路人女主的养成方法", "anime", 15),
    ("go-toubun no hanayome", "五等分的新娘", "anime", 15),
    ("suzumiya haruhi no yuuutsu", "凉宫春日的忧郁", "anime", 15),
    ("k-on!", "轻音少女", "anime", 20),
    ("spy x family", "间谍过家家", "anime", 20),
    ("oshi no ko", "我推的孩子", "anime", 20),
    ("bocchi the rock!", "孤独摇滚！", "anime", 20),
    ("lycoris recoil", "莉可丽丝", "anime", 15),
    ("re:zero", "Re：从零开始的异世界生活", "anime", 20),
    ("overlord", "不死者之王", "anime", 20),
    ("konosuba", "为美好的世界献上祝福", "anime", 20),
    ("fate/stay night", "Fate/stay night", "anime", 30),
    ("fate/extra", "Fate/EXTRA", "anime", 15),
    ("little busters!", "Little Busters!", "other", 12),
    ("clannad", "CLANNAD", "other", 12),
    ("steins;gate", "命运石之门", "anime", 15),
]


def copyright_tags():
    """展开成标签条目；顺带去重，并统一挂到 copyright_base 互斥组。

    ⚠️ 所有作品名共用一个互斥组：一次只画一个作品的角色，
    多选只会互相覆盖（也避免「原神 + 蔚蓝档案」这种必然崩坏的组合）。
    """
    out, seen = [], set()
    for name, zh, group, _n in COPYRIGHTS:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((name, zh, "copyright", "copyright_base", "soft", 1))
    return out


COPYRIGHT_TAGS = copyright_tags()


# ---------------------------------------------------------------------------
# 服装预设：一键把一整套服装标签写进选择
# ---------------------------------------------------------------------------
# 每条: (中文名, 英文副标题, 分组, 标签串, 分级, 强度档, 备注)
#   * 标签全部是 booru 通用词（已对本地 7999 角色的 Anima 词表做过频次核对）
#   * 备注里以「锁定」开头的，会额外写入 char_lock 互斥组 —— 那是角色本身，
#     一次只能锁一个；不锁角色的预设只写服装。
#   * 数值仅供面板展示，实际提示词顺序由 prompt_builder 统一排序。

OUTFIT_GROUPS = [
    {"id": "school", "zh": "校园", "en": "School", "icon": "🎒"},
    {"id": "job", "zh": "职业", "en": "Occupational", "icon": "💼"},
    {"id": "jp", "zh": "传统/和风", "en": "Traditional", "icon": "⛩️"},
    {"id": "swim", "zh": "泳装/内衣", "en": "Swim & Lingerie", "icon": "🩱"},
    {"id": "fantasy", "zh": "奇幻/战斗", "en": "Fantasy & Combat", "icon": "⚔️"},
    {"id": "stage", "zh": "偶像/舞台", "en": "Idol & Stage", "icon": "🎤"},
    {"id": "daily", "zh": "日常/礼服", "en": "Casual & Formal", "icon": "👗"},
    {"id": "game", "zh": "游戏/角色锁定", "en": "Game & Character", "icon": "🎮"},
]

OUTFIT_PRESETS = [
    # ---------------- 校园 ----------------
    ("经典水手服", "serafuku", "school",
     "serafuku, pleated skirt, sailor collar, neckerchief, thighhighs, loafers", "soft", 1, ""),
    ("深色水手服", "dark serafuku", "school",
     "serafuku, black skirt, sailor collar, black thighhighs, loafers, pleated skirt", "soft", 1, ""),
    ("夏季薄款校服", "summer uniform", "school",
     "school uniform, short sleeves, pleated skirt, necktie, white socks, loafers", "soft", 1, ""),
    ("冬季校服", "winter uniform", "school",
     "winter uniform, blazer, plaid skirt, necktie, black thighhighs, loafers", "soft", 1, ""),
    ("西装外套校服", "blazer uniform", "school",
     "school uniform, blazer, plaid skirt, ribbon, kneehighs, loafers", "soft", 1, ""),
    ("体操服 + 布鲁玛", "gym uniform", "school",
     "gym uniform, bloomers, white shirt, sneakers, short sleeves", "soft", 1, ""),
    ("死库水", "school swimsuit", "school",
     "school swimsuit, one-piece swimsuit, name tag, wet, water", "hard", 2, ""),
    ("体育课更衣", "changing", "school",
     "gym uniform, undressing, shirt lift, panties, blush, locker room", "hard", 2, ""),
    ("学园祭女仆咖啡", "school festival maid", "school",
     "maid, maid headdress, white apron, black dress, thighhighs, ribbon", "soft", 1, ""),
    ("图书委员", "library committee", "school",
     "school uniform, cardigan, pleated skirt, holding book, glasses", "soft", 1, ""),

    # ---------------- 职业 ----------------
    ("护士服", "nurse", "job",
     "nurse, nurse cap, white dress, white pantyhose, syringe", "soft", 1, ""),
    ("护士服（破）", "torn nurse", "job",
     "nurse, nurse cap, torn clothes, see-through, white thighhighs, blush", "hard", 2, ""),
    ("女仆装", "maid", "job",
     "maid, maid headdress, white apron, black dress, frills, thighhighs", "soft", 1, ""),
    ("兔女郎", "bunny girl", "job",
     "bunny girl, leotard, rabbit ears, black pantyhose, high heels, bowtie", "hard", 2, ""),
    ("OL 职业装", "office lady", "job",
     "office lady, business suit, pencil skirt, white shirt, necktie, pantyhose, high heels",
     "soft", 1, ""),
    ("白大褂研究员", "lab coat", "job",
     "lab coat, glasses, white shirt, necktie, pencil skirt, holding clipboard", "soft", 1, ""),
    ("空姐制服", "flight attendant", "job",
     "flight attendant, business suit, neckerchief, pencil skirt, pantyhose, peaked cap", "soft", 1, ""),
    ("警察制服", "police", "job",
     "police, police uniform, peaked cap, necktie, handcuffs, belt", "soft", 1, ""),
    ("军装", "military uniform", "job",
     "military uniform, peaked cap, necktie, epaulettes, thigh boots, gloves", "soft", 1, ""),
    ("咖啡店服务生", "cafe waitress", "job",
     "waitress, apron, white shirt, black skirt, ribbon, holding tray", "soft", 1, ""),
    ("教师（职业装）", "teacher", "job",
     "office lady, blazer, pencil skirt, glasses, necktie, holding book", "soft", 1, ""),

    # ---------------- 传统 / 和风 ----------------
    ("和服（振袖）", "furisode", "jp",
     "kimono, furisode, obi, flower, hair ornament, sandals", "soft", 1, ""),
    ("夏日浴衣", "yukata", "jp",
     "yukata, obi, geta, hair flower, festival, night", "soft", 1, ""),
    ("巫女服", "miko", "jp",
     "miko, hakama, nontraditional miko, red ribbon, hair tubes, shrine", "soft", 1, ""),
    ("改良巫女服", "modern miko", "jp",
     "nontraditional miko, hakama, white shirt, red ribbon, thighhighs", "soft", 1, ""),
    ("旗袍", "china dress", "jp",
     "china dress, side slit, hair ornament, high heels, thighhighs", "soft", 1, ""),
    ("汉服", "hanfu", "jp",
     "hanfu, wide sleeves, sash, hair ornament, long hair, ribbon", "soft", 1, ""),
    ("忍者装", "kunoichi", "jp",
     "ninja, mask, arm guards, sash, thighhighs, kunai, holding weapon", "soft", 1, ""),
    ("武士", "samurai", "jp",
     "samurai, hakama, katana, sash, armor, holding sword", "soft", 1, ""),
    ("修女服", "nun", "jp",
     "nun, habit, rosary, cross, veil, black dress", "soft", 1, ""),
    ("舞妓", "maiko", "jp",
     "kimono, maiko, obi, hair ornament, hair flower, tabi, sandals", "soft", 1, ""),

    # ---------------- 泳装 / 内衣 ----------------
    ("白色比基尼", "white bikini", "swim",
     "bikini, white bikini, side-tie bikini bottom, navel, wet, beach", "hard", 2, ""),
    ("黑色比基尼", "black bikini", "swim",
     "bikini, black bikini, navel, bare shoulders, beach, sunlight", "hard", 2, ""),
    ("竞技泳装", "competition swimsuit", "swim",
     "competition swimsuit, one-piece swimsuit, swim cap, goggles, wet", "hard", 2, ""),
    ("高叉连体泳装", "highleg swimsuit", "swim",
     "one-piece swimsuit, highleg, navel, wet, bare shoulders", "hard", 2, ""),
    ("蕾丝内衣", "lace lingerie", "swim",
     "lingerie, lace panties, bra, garter belt, thighhighs, on bed", "hard", 2, ""),
    ("黑丝内衣", "black lingerie", "swim",
     "lingerie, black bra, black panties, black thighhighs, garter belt", "hard", 2, ""),
    ("运动内衣", "sports bra", "swim",
     "sports bra, bike shorts, midriff, navel, sneakers, sweat", "hard", 2, ""),
    ("开裆内裤", "crotchless panties", "swim",
     "crotchless panties, pussy, no bra, blush, spread legs", "extreme", 3, ""),
    ("性感束腰", "corset", "swim",
     "corset, lingerie, thighhighs, garter belt, high heels, choker", "hard", 2, ""),
    ("乳贴", "pasties", "swim",
     "pasties, topless, no bra, blush, covered nipples", "hard", 2, ""),

    # ---------------- 奇幻 / 战斗 ----------------
    ("全身紧身战斗服", "bodysuit", "fantasy",
     "bodysuit, skin tight, zipper, gloves, boots, standing", "hard", 2, ""),
    ("驾驶服", "plugsuit", "fantasy",
     "plugsuit, bodysuit, interface headset, gloves, boots, standing", "hard", 2, ""),
    ("骑士铠甲", "knight armor", "fantasy",
     "armor, plate armor, gauntlets, cape, sword, holding weapon", "soft", 1, ""),
    ("女武神", "valkyrie", "fantasy",
     "armor, breastplate, feathered wings, spear, helmet, cape", "soft", 1, ""),
    ("比基尼铠甲", "bikini armor", "fantasy",
     "bikini armor, breastplate, gauntlets, thigh boots, cape, navel", "extreme", 3, ""),
    ("魔法少女", "magical girl", "fantasy",
     "magical girl, frills, ribbon, thighhighs, wand, holding wand", "soft", 1, ""),
    ("女巫", "witch", "fantasy",
     "witch hat, cape, robe, holding staff, thighhighs, black dress", "soft", 1, ""),
    ("乳胶衣", "latex", "fantasy",
     "latex, bodysuit, latex gloves, latex boots, shiny, skin tight", "hard", 2, ""),
    ("皮革束装", "leather", "fantasy",
     "leather, corset, leather skirt, leather gloves, thigh boots, choker", "hard", 2, ""),
    ("精灵游侠", "elf ranger", "fantasy",
     "elf, pointy ears, tunic, cape, hood, quiver, holding bow, thighhighs", "soft", 1, ""),
    ("恶魔", "demon", "fantasy",
     "demon girl, demon tail, demon wings, horns, black wings, leotard", "soft", 1, ""),
    ("天使", "angel", "fantasy",
     "angel, feathered wings, halo, white dress, bare shoulders, sandals", "soft", 1, ""),

    # ---------------- 偶像 / 舞台 ----------------
    ("偶像打歌服", "idol stage", "stage",
     "idol, stage costume, frills, ribbon, thighhighs, boots, holding microphone", "soft", 1, ""),
    ("拉拉队服", "cheerleader", "stage",
     "cheerleader, pleated skirt, crop top, pom poms, midriff, sneakers", "soft", 1, ""),
    ("芭蕾舞服", "ballet", "stage",
     "ballet, tutu, leotard, pantyhose, ballet slippers, hair bun", "soft", 1, ""),
    ("体操竞技服", "gymnastics", "stage",
     "leotard, highleg leotard, gymnastics, bare legs, hair ribbon", "hard", 2, ""),
    ("演唱会舞台装", "concert costume", "stage",
     "stage costume, idol, spotlight, microphone stand, sparkle, thighhighs", "soft", 1, ""),
    ("爵士舞装", "jazz dance", "stage",
     "leotard, fishnet, high heels, gloves, stage costume, dancing", "hard", 2, ""),

    # ---------------- 日常 / 礼服 ----------------
    ("日常休闲（T恤短裤）", "casual", "daily",
     "t-shirt, shorts, sneakers, ponytail, hands in pockets, smile", "soft", 1, ""),
    ("针织衫 + 长裙", "sweater skirt", "daily",
     "sweater, long skirt, boots, scarf, autumnal, sitting", "soft", 1, ""),
    ("连帽卫衣", "hoodie", "daily",
     "hoodie, hood up, shorts, sneakers, hands in pockets", "soft", 1, ""),
    ("牛仔裤休闲", "jeans", "daily",
     "shirt, jeans, belt, sneakers, standing, hands on hips", "soft", 1, ""),
    ("白色婚纱", "wedding dress", "daily",
     "wedding dress, veil, bridal gauntlets, white thighhighs, bouquet, holding bouquet",
     "soft", 1, ""),
    ("晚礼服", "evening gown", "daily",
     "evening gown, backless, bare shoulders, high heels, jewelry, necklace", "soft", 1, ""),
    ("黑色鸡尾酒裙", "cocktail dress", "daily",
     "cocktail dress, black dress, high heels, pearl necklace, earrings", "soft", 1, ""),
    ("圣诞装", "santa", "daily",
     "santa costume, santa hat, fur trim, red skirt, black thighhighs, boots", "soft", 1, ""),
    ("万圣节魔女", "halloween witch", "daily",
     "witch hat, halloween, pumpkin, cape, black dress, thighhighs", "soft", 1, ""),
    ("哥特萝莉", "gothic lolita", "daily",
     "gothic lolita, frills, black dress, lace, ribbon, thighhighs, parasol", "soft", 1, ""),
    ("JK 制服 + 泡泡袜", "jk loose socks", "daily",
     "school uniform, serafuku, pleated skirt, loose socks, loafers, bag", "soft", 1, ""),
    ("私服连衣裙", "sundress", "daily",
     "sundress, straw hat, sandals, bare shoulders, sunlight, standing", "soft", 1, ""),

    # ---------------- 游戏 / 角色锁定 ----------------
    ("初音未来（默认）", "hatsune miku", "game",
     "hatsune miku, vocaloid, twintails, aqua hair, detached sleeves, necktie, thighhighs",
     "soft", 1, "锁定"),
    ("初音未来 Append", "miku append", "game",
     "hatsune miku (append), vocaloid append, twintails, thighhighs, elbow gloves, "
     "necktie, bridal gauntlets", "soft", 1, "锁定"),
    ("樱初音", "sakura miku", "game",
     "sakura miku, vocaloid, twintails, pink hair, detached sleeves, necktie", "soft", 1, "锁定"),
    ("博丽灵梦", "hakurei reimu", "game",
     "hakurei reimu, touhou, hair tubes, red bow, detached sleeves, sarashi, hakama skirt",
     "soft", 1, "锁定"),
    ("雾雨魔理沙", "kirisame marisa", "game",
     "kirisame marisa, touhou, witch hat, blonde hair, single braid, apron, puffy sleeves",
     "soft", 1, "锁定"),
    ("十六夜咲夜", "izayoi sakuya", "game",
     "izayoi sakuya, touhou, maid, maid headdress, braid, silver hair, thighhighs",
     "soft", 1, "锁定"),
    ("明日香（驾驶服）", "asuka plugsuit", "game",
     "souryuu asuka langley, neon genesis evangelion, plugsuit, red bodysuit, "
     "interface headset, two side up", "hard", 2, "锁定"),
    ("绫波丽（驾驶服）", "rei plugsuit", "game",
     "ayanami rei, neon genesis evangelion, plugsuit, white bodysuit, interface headset, "
     "short hair", "hard", 2, "锁定"),
    ("喜多川海梦（制服）", "marin kitagawa", "game",
     "kitagawa marin, sono bisque doll wa koi wo suru, school uniform, blonde hair, "
     "pink hair, earrings, long hair", "soft", 1, "锁定"),
    ("雪之下雪乃（总武高）", "yukinoshita yukino", "game",
     "yukinoshita yukino, yahari ore no seishun lovecome wa machigatteiru., "
     "sobu high school uniform, blazer, plaid skirt, red ribbon, hair ribbon", "soft", 1, "锁定"),
    ("雪未来", "yuki miku", "game",
     "yuki miku, vocaloid, twintails, blue hair, white dress, snow, blue eyes", "soft", 1, "锁定"),
    ("赛车初音", "racing miku", "game",
     "racing miku, vocaloid, twintails, black gloves, racing suit, boots", "soft", 1, "锁定"),
    ("加藤惠（制服）", "katou megumi", "game",
     "katou megumi, saenai heroine no sodatekata, school uniform, short hair, "
     "pleated skirt, loafers, bob cut", "soft", 1, "锁定"),
    ("间桐樱（制服）", "matou sakura", "game",
     "matou sakura, fate (series), school uniform, red ribbon, purple hair, hair ribbon",
     "soft", 1, "锁定"),
    ("远坂凛（制服）", "tohsaka rin", "game",
     "tohsaka rin, fate (series), school uniform, black thighhighs, twin braids, "
     "red ribbon", "soft", 1, "锁定"),
    ("尼禄（花嫁）", "nero bride", "game",
     "nero claudius (fate), fate (series), wedding dress, veil, blonde hair, "
     "green eyes, saber (fate)", "soft", 1, "锁定"),
    ("舰队 Collection 水手服", "kancolle serafuku", "game",
     "kantai collection, serafuku, pleated skirt, neckerchief, thighhighs, "
     "hair ribbon", "soft", 1, "锁定"),
]


# ---------------------------------------------------------------------------
# 剧情模式（一条故事线 = 若干拍，主角固定）
# ---------------------------------------------------------------------------
try:
    from . import story as _story
except Exception:  # pragma: no cover
    _story = None


def story_counts():
    return _story.counts() if _story else {}


# ---------------------------------------------------------------------------
# SFW 模式（一个节点两用）
# ---------------------------------------------------------------------------
try:
    from . import sfw as _sfw
except Exception:  # pragma: no cover
    _sfw = None


def _sfw_modes():
    return getattr(_sfw, "MODES", ()) if _sfw else ()


def _sfw_hidden_cats():
    return getattr(_sfw, "HIDDEN_CATEGORIES_IN_SFW", ()) if _sfw else ()


def _sfw_quality():
    return getattr(_sfw, "SFW_QUALITY", "") if _sfw else ""


def _sfw_counts():
    return _sfw.counts() if _sfw else {}


def _sfw_block_keys():
    """SFW 要拦下的标签 keys（给前端做网格过滤）。"""
    try:
        return {str(k).strip().lower().replace("_", " ") for k in _sfw.BLOCK}
    except Exception:  # pragma: no cover
        return set()


# ---------------------------------------------------------------------------
# 中文翻译层：把没有中文名的标签补上中文
# ---------------------------------------------------------------------------
try:
    from .translations import translate as _translate
except Exception:  # pragma: no cover
    def _translate(tag, default=None):
        return default or tag


def zh_of(tag: str, given: str = "") -> str:
    """优先用手工中文；看起来是"英文占位"时才去翻译。"""
    g = str(given or "").strip()
    if g and g.lower() != str(tag).strip().lower():
        return g
    return _translate(tag, default=g or str(tag))


# ---------------------------------------------------------------------------
# 角色库：约 8000 个角色（web/characters.json）
# ---------------------------------------------------------------------------
try:
    from . import character_store as _chars
except Exception:  # pragma: no cover
    _chars = None


def character_tags():
    """生成角色标签条目：(英文名, 中文名, 分类, 互斥组, 分级, 强度档)。

    所有角色共用一个 ``character_base`` 互斥组 —— 一张图只可能是一个角色。
    """
    if _chars is None:
        return []
    out = []
    for en, zh, _copy, _posts, visible in _chars.tag_entries():
        out.append((en, zh, "character", "character_base", "soft", 1, not visible))
    return out


CHARACTER_TAGS_FULL = character_tags()      # 7 元组，含 hidden
CHARACTER_TAGS = [x[:6] for x in CHARACTER_TAGS_FULL]
CHARACTER_TAGS_HIDDEN = [x[6] for x in CHARACTER_TAGS_FULL]


# ---------------------------------------------------------------------------
# SFW 模式补进来的安全词（hidden —— 默认不占网格，选中或开「显示隐藏标签」可见）
# ---------------------------------------------------------------------------
SFW_TAGS = [
    ("rating:safe", "全年龄标记（rating:safe）", "style", "quality", "soft", 1),
    ("safe", "安全级", "style", "quality", "soft", 1),
    ("general", "一般向（general）", "style", "quality", "soft", 1),
    ("nsfw", "少儿不宜（负面用）", "style", "quality", "soft", 1),
]


def _split_multi(value):
    """把 "1girl, 1boy" 这类包含多个标签的条目展开。"""
    return [part.strip() for part in str(value).split(",") if part.strip()]


def outfit_presets_as_list():
    """把手工预设 + 导入的服装库预设展开成前端用的字典列表。"""
    out = []
    for idx, item in enumerate(_ALL_PRESETS):
        name, en, group, tags, rating, lvl, note = item[:7]
        out.append({
            "id": f"of{idx:03d}",
            "zh": name,
            "en": en,
            "g": group,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "r": rating,
            "lvl": int(lvl),
            "lock": note.startswith("锁定"),
            "note": note,
            "src": "import" if note.startswith("来源:") else "curated",
            "preview": OUTFIT_PREVIEWS.get(name, ""),
        })
    return out


def pose_presets_as_list():
    """姿势参考预设（来自 Anima 姿势选择器，带预览图）。"""
    out = []
    for idx, item in enumerate(POSE_PRESETS_IMPORT):
        name, en, group, tags, rating, lvl, note = item[:7]
        out.append({
            "id": f"po{idx:03d}",
            "zh": name,
            "en": en,
            "g": group,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "r": rating,
            "lvl": int(lvl),
            "src": "pose-lib",
            "preview": POSE_PREVIEWS.get(name, ""),
        })
    return out


def locked_character_tags():
    """所有「锁定角色」预设的第一个标签 = 角色触发词集合。

    用于让角色之间互斥：无论角色名来自预设第一个标签还是用户手打，
    只要在集合里就只能留一个。
    """
    chars = set()
    for item in OUTFIT_PRESETS:
        _name, _en, _g, tags, _r, _lvl, note = item
        if note.startswith("锁定"):
            first = tags.split(",")[0].strip().lower()
            if first:
                chars.add(first)
    return chars


# ---------------------------------------------------------------------------
# 来自 Comfyui-Anima-Tools 的「服装 tag 选择器」与「姿势选择器」
# ---------------------------------------------------------------------------
try:
    from .preset_import import (
        IMPORT_EXTRA_TAGS,
        IMPORT_GROUPS,
        OUTFIT_PRESETS_IMPORT,
        POSE_GROUPS,
        POSE_PRESETS_IMPORT,
    )
except Exception:  # pragma: no cover - 缺文件时不影响手工预设
    IMPORT_GROUPS, OUTFIT_PRESETS_IMPORT = [], []
    POSE_GROUPS, POSE_PRESETS_IMPORT = [], []
    IMPORT_EXTRA_TAGS = []

ALL_OUTFIT_GROUPS = list(OUTFIT_GROUPS) + [dict(g) for g in IMPORT_GROUPS]
ALL_POSE_GROUPS = [dict(g) for g in POSE_GROUPS]
_ALL_PRESETS = list(OUTFIT_PRESETS) + list(OUTFIT_PRESETS_IMPORT)

# 预设 -> 预览图（只有导入的预设带图；手工精选那 88 套没有图）
OUTFIT_PREVIEWS = {item[0]: item[7] for item in OUTFIT_PRESETS_IMPORT if len(item) > 7 and item[7]}
POSE_PREVIEWS = {item[0]: item[7] for item in POSE_PRESETS_IMPORT if len(item) > 7 and item[7]}


def _collect_preset_extras():
    """预设里用到、但正文标签表没定义的标签 → 自动补进「预设补充」分类。

    正常情况这里应该只剩角色名 / 版权名之类，以及服装库里那些非常细的单品词
    （它们不该出现在标签网格里）。这些会打 hidden 标记：面板默认不展示，
    但仍参与互斥、去重与已选展示。
    """
    known = {t[0].lower() for t in TAGS}
    known |= {t[0].lower() for t in PRESET_EXTRA_SUPPLEMENT}
    known |= {t[0].lower() for t in IMPORT_EXTRA_TAGS}
    extras, seen = [], set()
    for item in list(_ALL_PRESETS) + list(POSE_PRESETS_IMPORT):
        _name, _en, _g, tags, _r, lvl, _note = item[:7]
        for raw in tags.split(","):
            t = raw.strip()
            key = t.lower()
            if not t or key in known or key in seen:
                continue
            seen.add(key)
            extras.append((t, t, "preset_extra", None, "soft", min(int(lvl), 2)))
    return extras


PRESET_EXTRA_TAGS = _collect_preset_extras()
LOCKED_CHARACTERS = locked_character_tags()


def as_dict():
    """导出成前端 / API 使用的字典。"""
    tags = []
    for item in TAGS:
        t, zh, cat, group, rating, lvl = item
        entry = {"t": t, "zh": zh, "c": cat, "r": rating, "lvl": int(lvl)}
        if group:
            entry["g"] = group
        if "," in t:
            entry["multi"] = _split_multi(t)
        tags.append(entry)

    # 角色名：逐个角色一条，热门可见，其余 hidden
    for (t, zh, cat, group, rating, lvl), hid in zip(CHARACTER_TAGS, CHARACTER_TAGS_HIDDEN):
        entry = {"t": t, "zh": zh_of(t, zh), "c": cat, "r": rating, "lvl": int(lvl),
                 "g": group}
        if hid:
            entry["hidden"] = True
        tags.append(entry)

    # 轻小说：正常展示，归「游戏/作品」分类，但用自己的互斥组
    for t, zh, cat, group, rating, lvl in LIGHT_NOVEL_TAGS:
        entry = {"t": t, "zh": zh, "c": cat, "r": rating, "lvl": int(lvl)}
        if group:
            entry["g"] = group
        tags.append(entry)

    # 作品名（版权 tag）：正常展示，归「游戏/作品」分类
    for t, zh, cat, group, rating, lvl in COPYRIGHT_TAGS:
        entry = {"t": t, "zh": zh, "c": cat, "r": rating, "lvl": int(lvl)}
        if group:
            entry["g"] = group
        tags.append(entry)

    # SFW 安全词（hidden，默认不占网格）
    for t, zh, cat, group, rating, lvl in SFW_TAGS:
        tags.append({"t": t, "zh": zh, "c": cat, "r": rating, "lvl": int(lvl),
                     "g": group, "hidden": True})

    # 补充标签（发色/道具/场景细项等，正常展示）
    for t, zh, cat, group, rating, lvl in PRESET_EXTRA_SUPPLEMENT:
        entry = {"t": t, "zh": zh_of(t, zh), "c": cat, "r": rating, "lvl": int(lvl)}
        if group:
            entry["g"] = group
        tags.append(entry)

    # 服装库里那些很细的单品词（1788 条）：补进「预设补充」，打 hidden
    for t, zh, cat, group, rating, lvl in IMPORT_EXTRA_TAGS:
        entry = {"t": t, "zh": zh_of(t, zh), "c": cat, "r": rating, "lvl": int(lvl),
                 "hidden": True}
        if group:
            entry["g"] = group
        tags.append(entry)

    # 预设里用到但连服装库也没登记的零星标签
    for t, zh, cat, group, rating, lvl in PRESET_EXTRA_TAGS:
        entry = {"t": t, "zh": zh_of(t, zh), "c": cat, "r": rating, "lvl": int(lvl),
                 "hidden": True}
        if group:
            entry["g"] = group
        tags.append(entry)

    # 去重（按英文标签），并按"信息量"决定谁覆盖谁。
    # ⚠️ 自动兜底标签不能盖掉精心登记过的：
    #   * 例如 "touhou" 既在版权表里（正常展示），又出现在某个服装库套装的标签里
    #     （兜底 hidden），不能让它退化成 hidden
    #   * 例如 "hatsune miku" 既在角色表里（互斥组 character_base），
    #     又在兜底表里（hidden），必须保留角色表那条，否则角色互斥失效
    _PRIORITY = {"character": 6, "copyright": 5, "outfit": 4, "body": 4, "prop": 4,
                 "scene": 4, "face": 4, "subject": 4, "act": 4, "foreplay": 4,
                 "solo": 4, "fluid": 4, "style": 4, "preset_extra": 1}

    def _rank(entry):
        cat = entry.get("c") or ""
        return _PRIORITY.get(cat, 3) - (1 if entry.get("hidden") else 0)

    dedup = {}
    order = []
    for entry in tags:
        key = entry["t"].lower()
        if key not in dedup:
            order.append(key)
            dedup[key] = entry
            continue
        if _rank(entry) > _rank(dedup[key]):
            dedup[key] = entry

    return {
        "schema": SCHEMA,
        "categories": CATEGORIES,
        "tags": [dedup[k] for k in order],
        "outfit_groups": ALL_OUTFIT_GROUPS,
        "outfit_presets": outfit_presets_as_list(),
        "outfit_preset_count": {
            "all": len(_ALL_PRESETS),
            "curated": len(OUTFIT_PRESETS),
            "imported": len(OUTFIT_PRESETS_IMPORT),
        },
        "pose_groups": ALL_POSE_GROUPS,
        "pose_presets": pose_presets_as_list(),
        "pose_preset_count": len(POSE_PRESETS_IMPORT),
        "quality_presets": QUALITY_PRESETS,
        "negative_base": NEGATIVE_BASE,
        "negative_extra": NEGATIVE_EXTRA,
        "intensity": INTENSITY,
        "locked_characters": sorted(LOCKED_CHARACTERS),
        "copyright_groups": COPYRIGHT_GROUPS,
        "copyright_count": len(COPYRIGHT_TAGS),
        "light_novel_count": len(LIGHT_NOVEL_TAGS),
        "light_novel_titles": [n for n, _z, _c in LIGHT_NOVELS],
        "character_count": len(CHARACTER_TAGS),
        "story": story_counts(),
        "sfw": {
            "modes": list(_sfw_modes()),
            "hidden_categories": list(_sfw_hidden_cats()),
            "block_count": _sfw_counts().get("block", 0),
            "quality": _sfw_quality(),
            # 前端要按这份名单在 SFW 模式下把标签从网格里藏掉
            "block_keys": sorted(_sfw_block_keys()),
        },
        "character_meta": (_chars.meta() if _chars else {}),
    }


# 方便后端做校验（含预设补充标签与自动兜底标签）
# 手工登记过的标签集合：自动兜底的 hidden 标签不能盖掉它们
_NAMED = {t[0].lower() for t in TAGS}
_NAMED |= {t[0].lower() for t in COPYRIGHT_TAGS}
_NAMED |= {t[0].lower() for t in LIGHT_NOVEL_TAGS}
_NAMED |= {t[0].lower() for t in PRESET_EXTRA_SUPPLEMENT}

# 角色名必须进索引：否则「一张图一个角色」的互斥不会生效。
# ⚠️ 这里的合并顺序必须与 as_dict() 的优先级去重结果一致，
#    否则会出现"界面显示 c=character，索引里却是 preset_extra"的错位，
#    导致互斥组失效。
_TAG_INDEX_SOURCE = (list(TAGS) + list(COPYRIGHT_TAGS) + list(LIGHT_NOVEL_TAGS)
                     + list(PRESET_EXTRA_SUPPLEMENT)
                     + list(CHARACTER_TAGS) + list(SFW_TAGS)
                     + [t for t in PRESET_EXTRA_TAGS if t[0].lower() not in _NAMED])

_PRIORITY_MAP = {"character": 6, "copyright": 5, "outfit": 4, "body": 4, "prop": 4,
                 "scene": 4, "face": 4, "subject": 4, "act": 4, "foreplay": 4,
                 "solo": 4, "fluid": 4, "style": 4, "preset_extra": 1}


def _src_rank(item):
    cat = item[2] or ""
    return _PRIORITY_MAP.get(cat, 3)


TAG_INDEX = {}
for _item in _TAG_INDEX_SOURCE:
    _t, _zh, _cat, _group, _rating, _lvl = _item
    _key = _t.lower()
    _prev = TAG_INDEX.get(_key)
    if _prev is None or _src_rank(_item) > _src_rank(
            (_key, "", _prev["c"], _prev["g"], _prev["r"], _prev["lvl"])):
        TAG_INDEX[_key] = {"zh": _zh, "c": _cat, "g": _group,
                           "r": _rating, "lvl": int(_lvl)}
