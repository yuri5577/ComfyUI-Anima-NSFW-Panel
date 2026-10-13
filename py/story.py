# -*- coding: utf-8 -*-
"""剧情模式：一条故事线 = 若干「节拍」，每一拍给出标签 + 台词（英文给模型 / 中文给你看）。

设计要点
--------
1. **角色固定**：每个故事声明 `locks`（角色触发词 + 立绘标签 + 固定服装），
   每一拍的标签都会自动带上这些，所以主角的发色/瞳色/服装跨图一致。
   角色用 `char_lock:` 前缀锁住，配合 prompt_builder 的互斥组，一次只会画一个主角。
2. **图片连续性**：靠四件事——同一个 char_lock、同一套 style/quality、
   同一套镜头倾向（`camera`）、以及 `seed_mode` 的「递增」把种子绑成一条序列。
   面板会给出一键设置。
3. **分级**：NSFW 的尺度落在「氛围 + 暗示 + 局部裸露」，不写露骨器官与行为细节；
   想要更露骨，把 mode 切回 NSFW 并自己加标签即可。
4. 台词分 `en`（写进提示词，模型看得懂）和 `zh`（面板里给你读）。

每个故事 6 拍（`SCENES_PER_ARC`），是「可以一次画完」的长度。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

SCHEMA = 1
SCENES_PER_ARC = 6          # 每条故事线固定 6 拍

# 故事里可选的主角（都能在角色库里查到、且有立绘）
# key -> (英文名, 中文名, 作品, 立绘标签, 默认服装标签)
CAST: Dict[str, tuple] = {
    "asuna": (
        "asuna (sao)", "亚丝娜", "sword art online",
        ["1girl", "brown hair", "long hair", "braid", "brown eyes", "large breasts"],
        ["knights of the blood uniform", "white and red uniform", "thighhighs", "boots"],
    ),
    "yuuka": (
        "yuuka (blue archive)", "优香", "blue archive",
        ["1girl", "purple hair", "long hair", "two side up", "purple eyes", "large breasts"],
        ["blue archive school uniform", "white shirt", "black pleated skirt",
         "black thighhighs", "loafers"],
    ),
    "shiroko": (
        "shiroko (blue archive)", "白子", "blue archive",
        ["1girl", "grey hair", "wolf ears", "blue eyes", "halo",
         "mismatched pupils", "medium breasts"],
        ["blue archive school uniform", "sailor collar", "blue necktie",
         "black pleated skirt", "white thighhighs", "sneakers"],
    ),
    "raiden": (
        "raiden shogun", "雷电将军", "genshin impact",
        ["1girl", "purple hair", "very long hair", "braided ponytail", "purple eyes",
         "mole under eye", "large breasts"],
        ["kimono", "japanese clothes", "purple kimono", "sash", "hair ornament"],
    ),
    "marine": (
        "houshou marine", "宝钟玛琳", "hololive",
        ["1girl", "red hair", "long hair", "twintails", "heterochromia",
         "red eyes", "yellow eyes", "large breasts"],
        ["marine hat", "red coat", "white shirt", "skirt", "thighhigh boots", "eyepatch"],
    ),
    "megumin": (
        "megumin", "惠惠", "kono subarashii sekai ni shukufuku wo!",
        ["1girl", "brown hair", "short hair", "red eyes", "sidelocks",
         "small breasts", "cape"],
        ["red cape", "black dress", "witch hat", "bandaged arm", "thighhighs", "boots"],
    ),
    "darkness": (
        "darkness (konosuba)", "达克妮丝", "kono subarashii sekai ni shukufuku wo!",
        ["1girl", "blonde hair", "long hair", "blue eyes", "ponytail",
         "large breasts", "hair ornament"],
        ["plate armor", "breastplate", "gauntlets", "skirt", "thighhigh boots"],
    ),
    "takao": (
        "takao (azur lane)", "高雄", "azur lane",
        ["1girl", "black hair", "very long hair", "ponytail", "brown eyes",
         "large breasts", "hair flaps"],
        ["military uniform", "white shirt", "black skirt", "black thighhighs",
         "high heels", "peaked cap"],
    ),
}

# 通用：所有故事共用的画质与连续性标签
BASE_QUALITY = "best quality, absurdres, detailed skin, detailed background, cinematic lighting"

# ⚠️ 这里必须是**真实存在的 booru 标签**。
# 早期写过 "same character" —— 那不是标签，反而会污染提示词；
# 保证连续性的正确做法是：同一个 char_lock + 同一套立绘/服装标签 + 同一套镜头，
# 再配一句自然语言描述（见 CONTINUITY_CAPTION）。
CONTINUITY = "cinematic composition, consistent art style"
CONTINUITY_CAPTION = ("The same character with the same design and the same outfit, "
                      "framed in a matching style so the shots read as one continuous story.")

ARCS: List[Dict] = [
    # ================================================================ 1
    {
        "id": "office_overtime",
        "title": "加班夜",
        "zh": "加班夜：办公室只剩你们两个",
        "genre": "职场 / 偷情",
        "level": "suggestive",
        "summary": "深夜的办公室，只剩你和她在赶最后一份文件。灯灭了一半，"
                   "咖啡凉了，距离也一点点消失了。",
        "cast": ["asuna", "takao", "yuuka"],
        "setting": ["office", "night", "indoor", "window", "desk", "office chair",
                    "fluorescent lighting", "city lights"],
        "style": ["modern", "photorealistic lighting", "shallow depth of field"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "加班到深夜",
                "tags": ["1girl", "solo", "sitting", "office chair", "desk",
                         "paper stack", "coffee cup", "tired", "looking at viewer",
                         "unbuttoned collar", "loosened necktie", "night", "office"],
                "dialogue": "\"还差最后一份。……你先走吧，我留下来收尾。\"",
                "dialogue_en": "\"Just one more file. You can head home first — I'll wrap up.\"",
            },
            {
                "id": 2, "beat": "灯灭了一半",
                "tags": ["1girl", "solo", "standing", "stretching", "arms up",
                         "closed eyes", "dim lighting", "office", "night",
                         "window", "city lights", "silhouette"],
                "dialogue": "\"楼里好像只剩我们了。……你别站那么远。\"",
                "dialogue_en": "\"I think we're the only ones left in the building. Don't stand so far away.\"",
            },
            {
                "id": 3, "beat": "距离缩短",
                "tags": ["2people", "1girl", "1boy", "leaning forward", "close-up",
                         "eye contact", "blush", "office", "desk", "hand on desk",
                         "office chair", "kneeling"],
                "dialogue": "\"你身上……有咖啡的味道。\"",
                "dialogue_en": "\"You smell like coffee.\"",
            },
            {
                "id": 4, "beat": "第一下",
                "tags": ["2people", "1girl", "1boy", "kiss", "closed eyes", "blush",
                         "leaning forward", "hand on shoulder", "office", "desk",
                         "shirt tug", "unbuttoned shirt"],
                "dialogue": "\"……就一次。别让任何人知道。\"",
                "dialogue_en": "\"...Just once. Don't let anyone find out.\"",
            },
            {
                "id": 5, "beat": "桌上",
                "tags": ["2people", "1girl", "1boy", "on desk", "papers scattered",
                         "undressing", "open shirt", "visible bra", "blush",
                         "parted lips", "one leg up", "office", "night"],
                "dialogue": "\"文件……会乱掉的。\" \"那就让它乱。\"",
                "dialogue_en": "\"The files will get messed up.\" \"Let them.\"",
            },
            {
                "id": 6, "beat": "天快亮了",
                "tags": ["2people", "1girl", "1boy", "afterglow", "lying", "on desk",
                         "blanket", "dawn", "window", "warm lighting", "soft smile",
                         "hair spread out", "office"],
                "dialogue": "\"……天亮了。明天，还要装作什么都没发生吗？\"",
                "dialogue_en": "\"...It's dawn. Do we pretend nothing happened tomorrow?\"",
            },
        ],
    },
    # ================================================================ 2
    {
        "id": "onsen_ryokan",
        "title": "温泉旅馆",
        "zh": "温泉旅馆：一个人的露天汤",
        "genre": "和风 / 温泉",
        "level": "nude-suggestive",
        "summary": "雪夜的山中旅馆，她包下了露天温泉。雾气、木栅、雪声，"
                   "和一句「反正没人」。",
        "cast": ["raiden", "takao", "asuna"],
        "setting": ["onsen", "outdoor bath", "hot spring", "snow", "night", "steam",
                    "wooden fence", "stone", "lantern", "japanese architecture"],
        "style": ["japanese", "traditional", "warm lighting", "volumetric fog"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "进汤前",
                "tags": ["1girl", "solo", "yukata", "sitting", "wooden floor",
                         "towel", "steam", "blush", "looking at viewer",
                         "onsen", "night", "snow"],
                "dialogue": "\"这个时间是没人的。……你要一起吗？\"",
                "dialogue_en": "\"Nobody comes at this hour. ...Are you joining?\"",
            },
            {
                "id": 2, "beat": "解带",
                "tags": ["1girl", "solo", "undressing", "yukata", "slipping off shoulder",
                         "bare shoulders", "back", "from behind", "steam", "blush",
                         "onsen", "night", "dim lighting"],
                "dialogue": "\"别回头。……我说了别回头。\"",
                "dialogue_en": "\"Don't turn around. ...I said don't turn around.\"",
            },
            {
                "id": 3, "beat": "入汤",
                "tags": ["1girl", "solo", "onsen", "steam", "wet hair", "bare shoulders",
                         "water", "closed eyes", "relaxed", "blush", "towel on head",
                         "night", "snow"],
                "dialogue": "\"……好烫。你也下来。\"",
                "dialogue_en": "\"...It's hot. Get in.\"",
            },
            {
                "id": 4, "beat": "靠近",
                "tags": ["2people", "1girl", "1boy", "onsen", "steam", "close-up",
                         "eye contact", "wet skin", "blush", "hand on arm",
                         "water ripples", "night", "warm lighting"],
                "dialogue": "\"水下面，你手放哪儿呢。\"",
                "dialogue_en": "\"Where is your hand going, under the water?\"",
            },
            {
                "id": 5, "beat": "雪落下来",
                "tags": ["2people", "1girl", "1boy", "onsen", "kiss", "steam",
                         "snow", "wet hair", "bare shoulders", "blush", "closed eyes",
                         "close-up", "outdoor bath", "night"],
                "dialogue": "\"雪……掉在你肩膀上了。\"",
                "dialogue_en": "\"Snow... landed on your shoulder.\"",
            },
            {
                "id": 6, "beat": "汤冷之前",
                "tags": ["2people", "1girl", "1boy", "onsen", "afterglow", "leaning",
                         "towel", "wet hair", "dawn", "steam rising", "soft smile",
                         "bare shoulders", "outdoor bath"],
                "dialogue": "\"水快凉了。……再待一会儿吧。\"",
                "dialogue_en": "\"The water's cooling. ...Let's stay a little longer.\"",
            },
        ],
    },
    # ================================================================ 3
    {
        "id": "school_afterhours",
        "title": "放学后的教室",
        "zh": "放学后的教室：窗帘拉着",
        "genre": "校园",
        "level": "suggestive",
        "summary": "值日表上只有两个名字。夕阳、粉笔灰、空教室，"
                   "和一张不该坐上去的课桌。",
        "cast": ["shiroko", "yuuka", "megumin"],
        "setting": ["classroom", "school desk", "chalkboard", "curtain", "window",
                    "sunset", "afternoon", "school chair", "lockers"],
        "style": ["anime", "warm lighting", "dust in the air", "backlight"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "值日",
                "tags": ["1girl", "solo", "school uniform", "standing", "chalkboard",
                         "eraser", "chalk dust", "sunset", "classroom", "looking back",
                         "smile"],
                "dialogue": "\"今天只有我们两个值日。……你擦黑板，我扫地。\"",
                "dialogue_en": "\"Only the two of us on duty today. You take the board, I'll sweep.\"",
            },
            {
                "id": 2, "beat": "窗帘",
                "tags": ["1girl", "solo", "school uniform", "curtain", "pulling curtain",
                         "backlight", "shadow", "classroom", "sunset", "silhouette",
                         "standing"],
                "dialogue": "\"外面有人在看。……把窗帘拉上。\"",
                "dialogue_en": "\"Someone outside can see. ...Close the curtain.\"",
            },
            {
                "id": 3, "beat": "课桌上",
                "tags": ["1girl", "solo", "sitting on desk", "school desk",
                         "school uniform", "skirt lift", "bare thighs", "blush",
                         "classroom", "papers", "sunset", "looking at viewer"],
                "dialogue": "\"桌子……很凉。\"",
                "dialogue_en": "\"The desk... is cold.\"",
            },
            {
                "id": 4, "beat": "松开领结",
                "tags": ["1girl", "solo", "school uniform", "untying necktie",
                         "open shirt", "visible bra", "blush", "sitting on desk",
                         "classroom", "sunset", "close-up", "hands"],
                "dialogue": "\"领结打太紧了。……你帮我？\"",
                "dialogue_en": "\"My tie is too tight. ...Help me?\"",
            },
            {
                "id": 5, "beat": "铃响了没人来",
                "tags": ["2people", "1girl", "1boy", "kiss", "sitting on desk",
                         "hand on nape", "blush", "school uniform", "open shirt",
                         "classroom", "sunset", "dust in the air", "close-up"],
                "dialogue": "\"放学铃……早响过了。\"",
                "dialogue_en": "\"The closing bell... rang a long time ago.\"",
            },
            {
                "id": 6, "beat": "走廊的脚步声",
                "tags": ["2people", "1girl", "1boy", "hugging", "standing",
                         "school uniform", "half-undressed", "blush", "listening",
                         "classroom", "twilight", "door", "tension"],
                "dialogue": "\"嘘——有人。……别出声。\"",
                "dialogue_en": "\"Shh — someone's coming. ...Don't make a sound.\"",
            },
        ],
    },
    # ================================================================ 4
    {
        "id": "rainy_hotel",
        "title": "雨夜酒店",
        "zh": "雨夜酒店：只剩一间房",
        "genre": "旅行 / 一夜情",
        "level": "suggestive",
        "summary": "暴雨、满房、一张大床。她说「我睡沙发」，然后谁都没去睡。",
        "cast": ["takao", "marine", "asuna"],
        "setting": ["hotel room", "rain", "window", "bed", "lamp", "night",
                    "wet clothes", "suitcase", "city lights"],
        "style": ["modern", "moody lighting", "rain on glass", "bokeh"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "全身湿透",
                "tags": ["1girl", "solo", "wet clothes", "wet hair", "standing",
                         "hotel room", "rain", "window", "towel", "blush",
                         "looking at viewer", "water dripping"],
                "dialogue": "\"……都湿透了。你转过去。\"",
                "dialogue_en": "\"...I'm soaked through. Turn around.\"",
            },
            {
                "id": 2, "beat": "擦头发",
                "tags": ["1girl", "solo", "towel on head", "drying hair", "sitting on bed",
                         "tank top", "bare shoulders", "hotel room", "rain", "lamp",
                         "warm lighting", "blush"],
                "dialogue": "\"只有一条毛巾。……你等会儿。\"",
                "dialogue_en": "\"There's only one towel. ...Wait your turn.\"",
            },
            {
                "id": 3, "beat": "只有一张床",
                "tags": ["1girl", "1boy", "2people", "sitting on bed", "looking at each other",
                         "hotel room", "rain", "night", "lamp", "distance",
                         "bed sheet", "blush"],
                "dialogue": "\"我睡沙发。……你别笑。\"",
                "dialogue_en": "\"I'll take the sofa. ...Don't laugh.\"",
            },
            {
                "id": 4, "beat": "背对背",
                "tags": ["1girl", "1boy", "2people", "lying on bed", "back to back",
                         "bed sheet", "bare shoulders", "blush", "hotel room",
                         "rain", "window", "blue lighting", "night"],
                "dialogue": "\"……你呼吸声太大了。\"",
                "dialogue_en": "\"...You breathe too loudly.\"",
            },
            {
                "id": 5, "beat": "翻过来",
                "tags": ["1girl", "1boy", "2people", "lying on bed", "facing each other",
                         "close-up", "eye contact", "blush", "bed sheet", "bare shoulders",
                         "hand on cheek", "hotel room", "rain", "lamp"],
                "dialogue": "\"……雨好像小了。\" \"嗯。\"",
                "dialogue_en": "\"...The rain seems lighter.\" \"Mm.\"",
            },
            {
                "id": 6, "beat": "雨停时",
                "tags": ["1girl", "1boy", "2people", "afterglow", "lying on bed",
                         "tangled sheets", "bare shoulders", "dawn", "window",
                         "hotel room", "soft smile", "warm lighting"],
                "dialogue": "\"雨停了。……今天的事，就当是被雨困住的。\"",
                "dialogue_en": "\"The rain stopped. ...Let's blame today on the rain.\"",
            },
        ],
    },
    # ================================================================ 5
    {
        "id": "mage_guild_night",
        "title": "公会之夜",
        "zh": "公会之夜：任务之后",
        "genre": "奇幻冒险",
        "level": "suggestive",
        "summary": "讨伐结束，酒馆打烊，只剩两张床的旅店房间和一身没洗掉的伤。",
        "cast": ["megumin", "darkness", "asuna"],
        "setting": ["inn", "tavern", "wooden room", "candle", "bed", "night",
                    "fireplace", "window", "fantasy"],
        "style": ["fantasy", "candlelight", "warm lighting", "cozy"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "包扎",
                "tags": ["1girl", "solo", "bandage", "bare shoulders", "sitting on bed",
                         "candle", "inn", "night", "bandaged arm", "looking down",
                         "blush", "wound"],
                "dialogue": "\"这点小伤……喂，别看。\"",
                "dialogue_en": "\"It's just a scratch... hey, don't look.\"",
            },
            {
                "id": 2, "beat": "酒",
                "tags": ["1girl", "solo", "holding cup", "drinking", "flushed cheeks",
                         "sitting", "tavern", "candle", "night", "loosened collar",
                         "happy", "laughing"],
                "dialogue": "\"赢了就该喝一杯！……你怎么不喝？\"",
                "dialogue_en": "\"We won, so we drink! ...Why aren't you drinking?\"",
            },
            {
                "id": 3, "beat": "炉火前",
                "tags": ["1girl", "1boy", "2people", "sitting", "fireplace",
                         "candle", "warm lighting", "leaning on shoulder", "blanket",
                         "bare shoulders", "inn", "night", "blush"],
                "dialogue": "\"火……有点太暖了。\"",
                "dialogue_en": "\"The fire... is a little too warm.\"",
            },
            {
                "id": 4, "beat": "解甲",
                "tags": ["1girl", "solo", "removing armor", "breastplate", "undressing",
                         "visible bra", "blush", "bare shoulders", "inn", "candle",
                         "night", "from behind", "clothes fall"],
                "dialogue": "\"盔甲……卡住了。过来帮个忙。\"",
                "dialogue_en": "\"The armor... is stuck. Come help.\"",
            },
            {
                "id": 5, "beat": "床",
                "tags": ["1girl", "1boy", "2people", "on bed", "kiss", "blush",
                         "candle", "blanket", "bare shoulders", "close-up",
                         "hand on chest", "inn", "night", "warm lighting"],
                "dialogue": "\"隔壁……能听见的。\" \"那就小声点。\"",
                "dialogue_en": "\"The next room... can hear us.\" \"Then be quiet.\"",
            },
            {
                "id": 6, "beat": "天还没亮",
                "tags": ["1girl", "1boy", "2people", "afterglow", "lying", "bed",
                         "blanket", "candle out", "window", "dawn", "soft smile",
                         "hair spread out", "inn"],
                "dialogue": "\"下次讨伐……还一起吗？\"",
                "dialogue_en": "\"Next quest... together again?\"",
            },
        ],
    },
    # ================================================================ 6
    {
        "id": "stream_offline",
        "title": "下播之后",
        "zh": "下播之后：麦克风忘了关",
        "genre": "现代 / 主播",
        "level": "suggestive",
        "summary": "直播结束，她摘下耳机才发现麦克风还亮着 —— 而你已经进门了。",
        "cast": ["marine", "raiden", "yuuka"],
        "setting": ["streaming room", "desk", "microphone", "monitor", "headset",
                    "ring light", "night", "indoor", "poster", "cable"],
        "style": ["modern", "neon accent", "screen glow", "cozy"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "下播",
                "tags": ["1girl", "solo", "headset", "sitting", "desk", "monitor",
                         "streaming room", "night", "screen glow", "stretching",
                         "relieved", "hoodie"],
                "dialogue": "\"——下播啦。今天也谢谢大家。\"",
                "dialogue_en": "\"—And that's the stream. Thanks for today, everyone.\"",
            },
            {
                "id": 2, "beat": "麦克风",
                "tags": ["1girl", "solo", "microphone", "close-up", "surprised",
                         "blush", "leaning forward", "desk", "streaming room",
                         "night", "screen glow", "covering mouth"],
                "dialogue": "\"……等等。这个灯，还亮着？\"",
                "dialogue_en": "\"...Wait. This light is still on?\"",
            },
            {
                "id": 3, "beat": "你进门了",
                "tags": ["1girl", "1boy", "2people", "door", "standing", "surprised",
                         "hoodie", "bare legs", "streaming room", "night",
                         "looking at viewer", "blush"],
                "dialogue": "\"你什么时候进来的？！\"",
                "dialogue_en": "\"When did you come in?!\"",
            },
            {
                "id": 4, "beat": "耳机线",
                "tags": ["1girl", "1boy", "2people", "headset", "cable", "pulled",
                         "leaning", "close-up", "blush", "eye contact", "desk",
                         "streaming room", "night", "neon accent"],
                "dialogue": "\"线……缠住了。别动。\"",
                "dialogue_en": "\"The cable... is tangled. Don't move.\"",
            },
            {
                "id": 5, "beat": "还开着",
                "tags": ["1girl", "1boy", "2people", "kiss", "microphone", "desk",
                         "sitting on desk", "hoodie", "open hoodie", "visible bra",
                         "blush", "streaming room", "night", "screen glow", "close-up"],
                "dialogue": "\"……它还在录。\" \"那就让它录。\"",
                "dialogue_en": "\"...It's still recording.\" \"Then let it.\"",
            },
            {
                "id": 6, "beat": "关掉",
                "tags": ["1girl", "1boy", "2people", "afterglow", "lying", "bed",
                         "blanket", "monitor off", "dawn", "streaming room",
                         "soft smile", "hoodie off shoulder"],
                "dialogue": "\"……这下真的下播了。\"",
                "dialogue_en": "\"...Now I'm really offline.\"",
            },
        ],
    },
    # ================================================================ 7
    {
        "id": "beach_night",
        "title": "夜晚的海",
        "zh": "夜晚的海：只有浪声",
        "genre": "夏日 / 海边",
        "level": "suggestive",
        "summary": "夏天最后一个夜晚，沙滩上只剩篝火、海浪和一件没穿的防晒衫。",
        "cast": ["shiroko", "takao", "yuuka"],
        "setting": ["beach", "sea", "night", "bonfire", "sand", "moon",
                    "starry sky", "waves", "palm tree"],
        "style": ["summer", "moonlight", "warm firelight", "wide sky"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "篝火",
                "tags": ["1girl", "solo", "sitting on sand", "bonfire", "beach",
                         "night", "sea", "starry sky", "swimsuit", "bare shoulders",
                         "looking at viewer", "warm firelight"],
                "dialogue": "\"夏天……明天就结束了。\"",
                "dialogue_en": "\"Summer... ends tomorrow.\"",
            },
            {
                "id": 2, "beat": "脱掉防晒衫",
                "tags": ["1girl", "solo", "removing jacket", "swimsuit", "bikini",
                         "beach", "night", "bonfire", "blush", "bare shoulders",
                         "wind", "hair blowing", "side view"],
                "dialogue": "\"湿了，穿着难受。……你别看。\"",
                "dialogue_en": "\"It's wet and uncomfortable. ...Don't look.\"",
            },
            {
                "id": 3, "beat": "下水",
                "tags": ["1girl", "solo", "wading", "sea", "waves", "wet", "swimsuit",
                         "night", "moonlight", "back view", "hair blowing",
                         "reflection", "bare feet"],
                "dialogue": "\"水还是温的。过来。\"",
                "dialogue_en": "\"The water's still warm. Come here.\"",
            },
            {
                "id": 4, "beat": "浪",
                "tags": ["1girl", "1boy", "2people", "sea", "waves", "wet",
                         "close-up", "eye contact", "blush", "hand on waist",
                         "night", "moonlight", "swimsuit", "wet hair"],
                "dialogue": "\"浪要来了——抓住我。\"",
                "dialogue_en": "\"A wave's coming — hold on to me.\"",
            },
            {
                "id": 5, "beat": "沙滩上",
                "tags": ["1girl", "1boy", "2people", "lying on sand", "kiss", "blush",
                         "swimsuit", "wet skin", "bonfire", "beach", "night",
                         "starry sky", "close-up", "towel"],
                "dialogue": "\"沙会进头发里的。\" \"那就进。\"",
                "dialogue_en": "\"Sand will get in my hair.\" \"Then let it.\"",
            },
            {
                "id": 6, "beat": "日出前",
                "tags": ["1girl", "1boy", "2people", "afterglow", "lying", "towel",
                         "beach", "dawn", "sea", "bonfire embers", "soft smile",
                         "wet hair", "starry sky fading"],
                "dialogue": "\"……夏天，还能再来一次吗？\"",
                "dialogue_en": "\"...Can summer come again?\"",
            },
        ],
    },
    # ================================================================ 8
    {
        "id": "armor_training",
        "title": "训练场之后",
        "zh": "训练场之后：汗和护具",
        "genre": "奇幻 / 训练",
        "level": "suggestive",
        "summary": "对练结束，盔甲卸了一半，训练场只剩你们两个人和一桶凉水。",
        "cast": ["darkness", "raiden", "asuna"],
        "setting": ["training ground", "armory", "wooden fence", "dummy", "barrel",
                    "water bucket", "afternoon", "dusk", "straw"],
        "style": ["fantasy", "golden hour", "dust in the air", "warm lighting"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "对练",
                "tags": ["1girl", "1boy", "2people", "holding sword", "fighting",
                         "training ground", "armor", "dust", "afternoon",
                         "motion blur", "sweat", "determined"],
                "dialogue": "\"再来一次。这次我不会留手。\"",
                "dialogue_en": "\"Again. I won't hold back this time.\"",
            },
            {
                "id": 2, "beat": "卸甲",
                "tags": ["1girl", "solo", "removing armor", "breastplate off",
                         "underclothes", "bare shoulders", "sweat", "training ground",
                         "dusk", "blush", "sitting on barrel"],
                "dialogue": "\"盔甲里……全是汗。\"",
                "dialogue_en": "\"The inside of the armor... is all sweat.\"",
            },
            {
                "id": 3, "beat": "凉水",
                "tags": ["1girl", "solo", "pouring water", "water bucket", "wet",
                         "wet hair", "underclothes", "bare shoulders", "closed eyes",
                         "training ground", "dusk", "water dripping"],
                "dialogue": "\"……你要不要也冲一下？\"",
                "dialogue_en": "\"...Do you want some too?\"",
            },
            {
                "id": 4, "beat": "护具",
                "tags": ["1girl", "1boy", "2people", "untying straps", "arm guard",
                         "gauntlets", "bare shoulders", "close-up", "hands",
                         "training ground", "dusk", "blush", "sweat"],
                "dialogue": "\"这个扣……我自己解不开。\"",
                "dialogue_en": "\"This buckle... I can't undo it myself.\"",
            },
            {
                "id": 5, "beat": "稻草堆",
                "tags": ["1girl", "1boy", "2people", "lying", "straw", "kiss", "blush",
                         "underclothes", "bare shoulders", "training ground", "dusk",
                         "golden hour", "close-up", "barn"],
                "dialogue": "\"会有人经过的……\" \"这个点不会。\"",
                "dialogue_en": "\"Someone might walk by...\" \"Not at this hour.\"",
            },
            {
                "id": 6, "beat": "夜巡",
                "tags": ["1girl", "1boy", "2people", "afterglow", "lying", "straw",
                         "cape as blanket", "night", "training ground", "starlight",
                         "soft smile", "bare shoulders"],
                "dialogue": "\"……明天的训练，你准输。\"",
                "dialogue_en": "\"...Tomorrow's drill, you're losing.\"",
            },
        ],
    },

    # ================================================================ 9
    {
        "id": "childhood_promise",
        "title": "青梅竹马",
        "zh": "青梅竹马：十年前的那个约定",
        "genre": "日常 / 青春",
        "level": "suggestive",
        "summary": "搬家回来，隔壁还是那户人家。她翻出相册说「你记得吗」——"
                   "十年前的约定，她一直记着。",
        "cast": ["asuna", "yuuka", "shiroko"],
        "setting": ["bedroom", "living room", "photo album", "window", "afternoon",
                    "twilight", "tatami", "bookshelf"],
        "style": ["nostalgic", "warm lighting", "soft focus", "film grain"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "搬家回来",
                "tags": ["1girl", "casual", "standing", "doorway", "cardboard box",
                         "smile", "waving", "afternoon", "sunlight", "childhood friend",
                         "camera", "looking at viewer"],
                "solo": True,
                "dialogue": "「欢迎回来。……十年了，你长这么高了。」",
                "dialogue_en": "Welcome back. ...Ten years, and you got so tall.",
            },
            {
                "id": 2, "beat": "翻相册",
                "tags": ["1girl", "sitting", "photo album", "childhood photo",
                         "reminiscing", "laughing", "afternoon", "living room",
                         "pointing", "blush"],
                "solo": True,
                "dialogue": "「你看这张——小时候你哭得超难看。」",
                "dialogue_en": "Look at this one. You cried so ugly back then.",
            },
            {
                "id": 3, "beat": "那个约定",
                "tags": ["1girl", "sitting", "holding photo", "promise", "serious",
                         "looking down", "blush", "twilight", "living room",
                         "close-up", "nostalgic"],
                "solo": True,
                "dialogue": "「你说过，长大以后要娶我的。……记得吗？」",
                "dialogue_en": "You said you'd marry me when we grew up. ...Remember?",
            },
            {
                "id": 4, "beat": "河堤",
                "tags": ["1girl", "1boy", "2people", "riverbank", "sunset", "walking",
                         "sunflower field", "holding hands", "wind", "hair blowing",
                         "blush", "casual", "skirt"],
                "dialogue": "「这条路，我们小时候天天走。」",
                "dialogue_en": "We walked this road every day when we were kids.",
            },
            {
                "id": 5, "beat": "长大以后",
                "tags": ["1girl", "1boy", "2people", "kiss", "riverbank", "sunset",
                         "holding hands", "blush", "closed eyes", "close-up",
                         "casual", "wind"],
                "dialogue": "「那……现在算数了吗？」",
                "dialogue_en": "So... does it still count now?",
            },
            {
                "id": 6, "beat": "隔壁房间",
                "tags": ["1girl", "1boy", "2people", "bedroom", "night", "bed",
                         "lying", "tangled sheets", "afterglow", "bare shoulders",
                         "soft smile", "moonlight", "window", "tatami"],
                "dialogue": "「明天，我还要叫你名字。就像小时候那样。」",
                "dialogue_en": "Tomorrow I'll still call your name. Just like when we were kids.",
            },
        ],
    },
    # ================================================================ 10
    {
        "id": "hypno_pocketwatch",
        "title": "催眠怀表",
        "zh": "催眠怀表：她自己想知道答案",
        "genre": "心理 / 暗示",
        "level": "suggestive",
        "summary": "她在旧货店淘到一块怀表，说是能让人说真话。她坚持要试，"
                   "而且要你来做那个提问的人。",
        "cast": ["darkness", "takao", "marine"],
        "setting": ["bedroom", "dimly lit room", "candle", "mirror", "night",
                    "curtain", "bed", "pendulum", "pocket watch"],
        "style": ["moody lighting", "close-up focus", "bokeh", "film grain"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "淘到的表",
                "tags": ["1girl", "holding pocket watch", "pocket watch", "sitting",
                         "table", "curious", "smile", "bedroom", "night", "candle",
                         "looking at viewer"],
                "dialogue": "「店主说，这块表能让人说真话。」",
                "dialogue_en": "The shopkeeper said this watch makes people tell the truth.",
            },
            {
                "id": 2, "beat": "摆起来",
                "tags": ["1girl", "pendulum", "pocket watch", "close-up", "pink pupils",
                         "spiral eyes", "hypnosis", "dazed", "sitting", "bedroom",
                         "candle", "dim lighting"],
                "dialogue": "「你摇，我看着。……别停。」",
                "dialogue_en": "You swing it, I'll watch. ...Don't stop.",
            },
            {
                "id": 3, "beat": "第一个问题",
                "tags": ["1girl", "1boy", "2people", "sitting", "trance", "blank eyes",
                         "spiral eyes", "blush", "obedient", "bedroom", "candle",
                         "close-up", "unfocused"],
                "dialogue": "「……你问吧。我今天都会说实话。」",
                "dialogue_en": "...Ask me. I'll tell the truth today.",
            },
            {
                "id": 4, "beat": "说出口的答案",
                "tags": ["1girl", "1boy", "2people", "trance", "spiral eyes",
                         "leaning forward", "hand on cheek", "blush", "close-up",
                         "bedroom", "candle", "hypnotized"],
                "dialogue": "「……我喜欢你。这句话我憋了三年。」",
                "dialogue_en": "...I like you. I've held that in for three years.",
            },
            {
                "id": 5, "beat": "表停了",
                "tags": ["1girl", "1boy", "2people", "kiss", "pocket watch",
                         "holding pendulum", "dropped object", "blush", "bed",
                         "bedroom", "night", "candle", "close-up"],
                "dialogue": "「表……停了。不过我好像不需要它了。」",
                "dialogue_en": "The watch... stopped. But I don't think I need it anymore.",
            },
            {
                "id": 6, "beat": "醒着说的话",
                "tags": ["1girl", "1boy", "2people", "lying", "bed", "afterglow",
                         "bare shoulders", "dawn", "window", "curtain", "soft smile",
                         "hair spread out", "clear eyes"],
                "dialogue": "「现在我是清醒的。……再说一次：我喜欢你。」",
                "dialogue_en": "I'm awake now. ...I'll say it again: I like you.",
            },
        ],
    },
    # ================================================================ 11
    {
        "id": "time_stop_watch",
        "title": "时间停止",
        "zh": "时间停止：她掏出了那块表",
        "genre": "奇幻 / 时间",
        "level": "suggestive",
        "summary": "她说自己捡到一块能停住时间的表，然后当着你的面按了下去。"
                   "世界安静下来，只有你们两个还能动。",
        "cast": ["raiden", "shiroko", "megumin"],
        "setting": ["city street", "crossing", "clock tower", "frozen crowd",
                    "suspended motion", "dust suspended in air", "night",
                    "neon lights", "stopwatch"],
        "style": ["blue glow", "desaturated background", "cinematic",
                  "shallow depth of field"],
        "camera": "medium shot",
        "scenes": [
            {
                "id": 1, "beat": "她掏出一块表",
                "tags": ["1girl", "holding stopwatch", "stopwatch", "city street",
                         "night", "neon lights", "smile", "looking at viewer",
                         "clock tower", "close-up"],
                "solo": True,
                "dialogue": "「别问哪来的。你只要看着我按下去。」",
                "dialogue_en": "Don't ask where I got it. Just watch me press it.",
            },
            {
                "id": 2, "beat": "按下去",
                "tags": ["1girl", "holding stopwatch", "pressing button", "blue glow",
                         "time stop", "clock tower", "night", "city street",
                         "glowing", "sparkle", "close-up"],
                "solo": True,
                "dialogue": "「——三、二、一。」",
                "dialogue_en": "—Three, two, one.",
            },
            {
                "id": 3, "beat": "世界安静了",
                "tags": ["1girl", "1boy", "2people", "frozen in time", "frozen crowd",
                         "suspended motion", "dust suspended in air", "crossing",
                         "city street", "night", "blue glow", "desaturated background"],
                "solo": True,
                "dialogue": "「你看，雨停在半空。……现在只有我们两个能动了。」",
                "dialogue_en": "Look, the rain stopped mid-air. ...Now only the two of us can move.",
            },
            {
                "id": 4, "beat": "她拉着你走",
                "tags": ["1girl", "1boy", "2people", "walking", "holding hands",
                         "frozen crowd", "suspended motion", "city street", "night",
                         "blue glow", "dyed hair", "coat", "smile"],
                "dialogue": "「反正没人看得见。去哪都行。」",
                "dialogue_en": "Nobody can see us anyway. We can go anywhere.",
            },
            {
                "id": 5, "beat": "钟楼下面",
                "tags": ["1girl", "1boy", "2people", "kiss", "clock tower",
                         "frozen in time", "suspended motion", "night", "blue glow",
                         "close-up", "holding stopwatch", "dust suspended in air"],
                "dialogue": "「表上还有九分钟。……够不够？」",
                "dialogue_en": "There are nine minutes left on it. ...Is that enough?",
            },
            {
                "id": 6, "beat": "时间回来了",
                "tags": ["1girl", "1boy", "2people", "rain", "city street", "night",
                         "crowd", "clock tower", "neon lights", "close-up",
                         "holding umbrella", "soft smile", "blush"],
                "dialogue": "「时间回来了。……刚才那九分钟，我们都记得，对吧？」",
                "dialogue_en": "Time is back. ...We both remember those nine minutes, right?",
            },
        ],
    },
]

ARC_INDEX = {a["id"]: a for a in ARCS}


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def as_dict() -> Dict[str, object]:
    return {
        "schema": SCHEMA,
        "scenes_per_arc": SCENES_PER_ARC,
        "cast": {
            k: {"name": v[0], "zh": v[1], "copyright": v[2],
                "look": list(v[3]), "outfit": list(v[4])}
            for k, v in CAST.items()
        },
        "arcs": ARCS,
        "base_quality": BASE_QUALITY,
        "continuity": CONTINUITY,
    }


def resolve_cast(arc: Dict, cast_key: Optional[str] = None) -> Dict[str, object]:
    """挑主角：用户指定优先，否则用故事的第一个候选。"""
    keys = list(arc.get("cast") or [])
    key = cast_key if cast_key in keys else (keys[0] if keys else None)
    if not key or key not in CAST:
        return {}
    name, zh, copy, look, outfit = CAST[key]
    return {"key": key, "name": name, "zh": zh, "copyright": copy,
            "look": list(look), "outfit": list(outfit)}


# 场景里出现这些词就认为「这一拍有第二个人」
_PARTNER_HINTS = ("2people", "1boy", "2boys", "multiple boys", "kiss", "hugging",
                  "fingering", "sex", "missionary", "cowgirl position", "leaning forward",
                  "on desk", "couch", "partner", "pairing")

# 这些标签本身不写进提示词（只是我们内部的语义标记）
_INTERNAL = ("afterglow",)

# 场景里出现这些词才算「真的要有男性在场」；只写 2people 不够
_MALE_HINTS = ("1boy", "2boys", "multiple boys", "boy on top", "penis", "fellatio",
               "irrumatio", "paizuri", "handjob")

# 数量类标签：统一由锚点逻辑注入，场景里写的一律剔掉，避免互相打架
_COUNT_TAGS = ("1girl", "1boy", "2girls", "2boys", "solo", "2people", "multiple girls",
               "multiple boys", "1girl, 1boy")


def _wants_partner(tags: Sequence[str]) -> bool:
    low = {str(x).strip().lower() for x in tags}
    return any(h in low for h in _PARTNER_HINTS)


def build_scene(arc_id: str, scene_no: int, cast_key: Optional[str] = None,
                extra_tags: str = "", quality: str = BASE_QUALITY
                ) -> Dict[str, object]:
    """把某一拍展开成一份完整的生成参数（含连续性标签）。

    返回 ``{"tags": 逗号串, "caption": 英文台词, "dialogue_zh": 中文台词, ...}``
    """
    arc = ARC_INDEX.get(arc_id)
    if not arc:
        raise KeyError(f"没有这个剧情：{arc_id}")
    scenes = arc["scenes"]
    idx = max(1, min(int(scene_no), len(scenes))) - 1
    sc = scenes[idx]
    who = resolve_cast(arc, cast_key)

    locked = f"char_lock:{who['name']}" if who else ""
    # 台词要写进提示词（模型看得懂语气），但**必须去掉引号**：
    # 引号本身不是标签，而且台词里有逗号，会把它切成好几个碎标签。
    spoken = (sc.get("dialogue_en") or sc.get("dialogue") or "")
    spoken = spoken.replace('"', "").replace("\u201c", "").replace("\u201d", "").strip()

    parts: List[str] = []
    if locked:
        parts.append(locked)
    if who:
        parts.append(who.get("copyright", ""))
        parts.extend(who.get("look", []))
    # 注意：台词**不放**进标签串。它走 caption_text，最终拼在提示词末尾的
    # 自然语言段里（Anima 的语法就是这样：标签在前、自然语言在后）。
    scene_tags = [str(x) for x in (sc.get("tags") or [])]
    # ---- 人物数量锚点（最容易出问题的一步）----
    # ⚠️ 踩过两次坑：
    #   1) 官方「单人/多人」属于同一个互斥组，场景里的 `solo` 会把 `1boy` 顶掉，
    #      结果双人镜头没有男性锚点，模型自己编了个第二人；
    #   2) 反过来，场景里标了 `2people`（只是背景有路人）但画面里不该有男性时，
    #      注入 `1boy` 之后模型找不到男性，就把主角**复制**了一份 —— 实测画出了
    #      两个雷电将军。
    # 所以：先把场景里所有数量类标签剔掉，再注入**唯一**的锚点；
    # 场景用 `"solo": True` 显式声明「这一拍只有主角一个人」。
    explicit_solo = bool(sc.get("solo"))
    wants_partner = (_wants_partner(scene_tags)
                     and any(x.strip().lower() in _MALE_HINTS for x in scene_tags))
    if explicit_solo or not wants_partner:
        parts.append("1girl")
        parts.append("solo")
    else:
        parts.append("1girl")
        parts.append("1boy")
    parts.extend(x for x in scene_tags
                 if x.strip().lower() not in _INTERNAL
                 and x.strip().lower() not in _COUNT_TAGS)
    if who:
        parts.extend(who.get("outfit", []))
    parts.extend(arc.get("setting") or [])
    parts.extend(arc.get("style") or [])
    if arc.get("camera"):
        parts.append(arc["camera"])
    parts.extend([CONTINUITY, quality])
    if extra_tags.strip():
        parts.append(extra_tags.strip())

    # 保序去重（忽略大小写与下划线/空格差异），避免 "office" 出现两次这种
    seen, uniq = set(), []
    for p in parts:
        if not p:
            continue
        k = str(p).lower().replace("_", " ").strip()
        if k.startswith("char_lock:"):
            k = k
        if k in seen:
            continue
        seen.add(k)
        uniq.append(str(p))
    tags = ", ".join(uniq)
    return {
        "arc_id": arc_id,
        "arc_title": arc["title"],
        "scene_no": idx + 1,
        "scene_total": len(scenes),
        "beat": sc.get("beat", ""),
        "tags": tags,
        "caption": spoken,                 # 英文台词 -> 写进提示词的自然语言段
        "caption_text": spoken,
        "dialogue": sc.get("dialogue", ""),
        "dialogue_en": sc.get("dialogue_en", ""),
        "cast": who,
        "continuity_caption": CONTINUITY_CAPTION,
        "style_tags": list(arc.get("style") or []),
        "setting_tags": list(arc.get("setting") or []),
        "camera": arc.get("camera", ""),
        "level": arc.get("level", ""),
        # 面板用：把这一拍的种子绑成一条序列
        "seed_hint": "递增 +1",
    }


def counts() -> Dict[str, int]:
    return {
        "cast": len(CAST),
        "arcs": len(ARCS),
        "scenes": sum(len(a["scenes"]) for a in ARCS),
    }
