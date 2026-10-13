# Changelog

## v1.9.3 — 2026-10-13

### 低版本前端兼容：又补了三处防线

你问「有没有更低版本的 ComfyUI 可以测」——我去查了。结论和依据都写进
`workflows/低版本兼容说明.md`。

**能拿到的最老前端**：PyPI 上 `comfyui-frontend-package` 最早是 **1.12.8**
（更早的 1.3.x 前端是内置在 ComfyUI 里的，不在 PyPI）。我把 1.12.8 下载下来，
在它的真实源码里核对了我依赖的每个 API。

补的三处：

1. **`addDOMWidget` 老前端只吃 3 个参数**（`name, type, element`），
   第 4 个 config 被忽略 —— 所以 `getHeight/getMinHeight/getMaxHeight` 都不会生效。
   现在 `addDOMWidget` 缺失或抛异常时**自动退回画布绘制预览**，
   不会把 `setupBuilder` 打断（打断的话连「打开面板」按钮都没有）。
2. **`widget.options` 可能不存在** —— 老前端（1.12.x）的 `addWidget` 不一定带
   `options` 字段，原来直接写 `refresh.options.serialize = false` 会抛 `TypeError`。
   现在 5 处访问全部有 `x.options = x.options || {}` 前置。
3. **`graph.links[id]` 的字段名**：老前端用 `target`，新的用 `target_id`；
   `graph.getNodeById` 在老前端上也可能是 undefined。
   种子推送那段现在两种字段名都认、并退回 `graph._nodes_by_id`。

### 新增第三个测试模式 `--oldfe`

模拟老前端的 DOM widget 契约：`addDOMWidget` 只收 3 个参数、按钮 widget
**没有 `options` 字段**、link 用 `target`、`graph.getNodeById` 返回 null。

```bash
node tools/animansfw_panel_smoke.mjs            # 现代前端
node tools/animansfw_panel_smoke.mjs --legacy   # 剥掉 addDOMWidget 等
node tools/animansfw_panel_smoke.mjs --oldfe    # 老前端契约（1.12.x）
```

三种模式都必须全绿 —— 这正是抓出上面第 2 条的地方。

### 补充：排查顺序

真遇到「打不开面板」，先按这个顺序查，**大多数情况跟前端版本无关**：

1. Ctrl+F5 硬刷新（浏览器缓存最常见）
2. F12 看有没有 `[AnimaNSFW]` 报错
3. 服务端日志里本包有没有 `IMPORT FAILED`
4. `curl /anima_nsfw/tags` 有没有 JSON（没有 = 后端/端口问题）
5. `curl /extensions/ComfyUI-Anima-NSFW-Panel/anima_nsfw_panel.js` 有没有 JS
6. 都正常才怀疑前端版本 → 按说明里的降级步骤验证

## v1.9.2 — 2026-10-13

### 新增：剧情工作流（修复 + 放大 + 保存）

`workflows/` 里多了三个文件，配套剧情模式使用：

| 文件 | 用途 |
|---|---|
| `Anima剧情工作流-修复放大保存.json` | UI 格式，拖进 ComfyUI 即用 |
| `Anima剧情工作流-修复放大保存.API.json` | API 格式，脚本调用 |
| `Anima剧情工作流-说明.md` | 逐环节说明 + 调参建议 + 常见问题 |

27 个节点 / 51 条连线，实测一张 **36~42 秒**：

```
基础采样 1024²（12 步 / CFG 1 / Turbo LoRA）
→ 潜空间放大 1.5× → 二次采样 1536²（denoise 0.45）
→ 修脸   FaceDetailer + face_yolov8m   + SAM
→ 修手   FaceDetailer + hand_yolov8s   + SAM   ← 治手脚崩坏
→ 修人体 FaceDetailer + person_yolov8m-seg + SAM ← 治结构崩坏
→ 4× anime 放大（1152 → 4608）→ 缩到 2534²
→ SaveImage 到 output/AnimaStory/
→ ImageGridComposite2x2 四格拼图
```

三个修复步骤的参数是**按问题类型分别调的**，不是复制粘贴：
- 修脸：`denoise 0.45` / `guide_size 512`
- 修手：`denoise 0.5` / `bbox_threshold 0.4`（手模糊也要能检出）/ `guide_size 384`
- 修人体：`denoise` **只有 0.35**（低 denoise 才能纠正结构而不重画角色）/
  `guide_size 768` / `max_size 1536`

### 修复：剧情套用后画面全黑（严重）

**两个原因叠在一起**：

1. `normalize_token()` 会把下划线换成空格，而内部标记 `char_lock:` 恰好含下划线 ——
   于是 `char_lock:asuna (sao)` 被规范化成 `char lock:asuna (sao)`。
   后果一串：
   - `strip_char_lock()` 认不出前缀，**这串垃圾文本直接进了提示词**
   - 角色互斥组也失效
   - 实测结果就是**整张全黑**（亮度 0.0000）
2. 同一个标签因为「锁定预设版本」和「用户版本」前缀不同，绕过了去重，
   前缀一剥就出现重复标签（实测重复了 `knights of the blood uniform`）

两处都修了：`normalize_token()` 现在会保护 `char_lock:` 前缀；
`dedupe()` 拿**去掉前缀**的部分做键，并且 strip + 折叠连续空格。
全库体检（11 线 × 6 拍 × 全部主角 = 198 组）现在零重复、零坏前缀。

### 修复：台词被当成字幕画在图上

套用剧情时会把英文台词写进 `caption_text`，而 `caption_text` 会拼进**正面提示词** ——
模型把它当成「要渲染的文字」，于是在图底部画出一行乱码字幕
（`..Ten years, and you got se-tol60h,`），右上角还多一个假 logo。

现在套用剧情**不再写 `caption_text`**，台词只在面板里给你读（点分镜卡片的
「复制台词」）。同时给提示词面板加了**第三路输出 `story_info`**，
把台词等元数据作为结构化 JSON 带出去 —— 想用的话接这根线，
但**不要接回提示词**。

### 修复：「画面干净」负面段补上反文字词

4× 放大模型会把物体纹理幻化成伪文字。`画面干净` 段原来只有
`jpeg artifacts / grain / noise ...`，现在补了
`text, watermark, signature, username, logo, artist name, copyright name,
web address, dated, english text, chinese text, speech bubble, caption,
letterboxed, ui, interface`。

### 实测数据

| 项目 | 结果 |
|---|---|
| 工作流端到端 | 成功，36~42s |
| 输出尺寸 | 2534×2534（`scale_by 0.55`）/ 可调 1613² ~ 4608² |
| 文件大小 | 约 3.8 MB（4608² 时约 13 MB） |
| 亮度 | 0.28 ~ 0.45（正常，非全黑） |
| 4× 模型实际倍率 | 1152 → 4608（确认是 4×） |

## v1.9.1 — 2026-10-12

### 新增 3 条故事线（共 11 条 / 66 拍）

按你的题材要求写的：

| 故事线 | 题材 | 梗概 | 可主角 |
|---|---|---|---|
| **青梅竹马** | 日常 / 青春 | 搬家回来，隔壁还是那户人家。她翻出相册说「你记得吗」——十年前的约定她一直记着 | 亚丝娜 / 优香 / 白子 |
| **催眠怀表** | 心理 / 暗示 | 她在旧货店淘到一块「能让人说真话」的怀表，坚持要试，而且要你来做提问的人 | 达克妮丝 / 高雄 / 宝钟玛琳 |
| **时间停止** | 奇幻 / 时间 | 她说捡到一块能停住时间的表，当着你的面按了下去。世界安静下来，只有你们两个还能动 | 雷电将军 / 白子 / 惠惠 |

**基调说明**：三条都写成「双方知情、以试探与告白为核心」——
- 催眠那条，最后一拍明确是她**醒来之后**再说一次真心话（怀表只是借口）
- 时间停止那条，最后一拍时间恢复，她选择**清醒地把话说完**
这样既保留题材张力，又不会写成单方面的支配。

### 修复：双人/单人锚点又踩了一次坑

上一版加了「有第二个人就注入 `1boy, 1girl`」，但判断条件太宽 ——
**时间停止第 3 拍**只是背景有冻结的路人（场景标了 `2people`），画面里根本不该有男性。
注入 `1boy` 后模型找不到男性，就把主角**复制了一份** —— 实测画出了两个雷电将军。

这次改成三个判据叠加：

1. 场景出现 `2people` **并且**出现真正的男性标识（`1boy` / `2boys` /
   `boy on top` / `penis` 等）→ 注入 `1girl, 1boy`
2. 场景显式声明 `"solo": true` → 强制 `1girl, solo`（给时间停止 #1~#3、
   青梅竹马 #1~#3 都补上了，这些拍背景有路人但只该画主角一个）
3. 其余 → `1girl, solo`

同时**先把场景里所有数量类标签剔掉**（`1girl` / `1boy` / `2people` / `solo` /
`2girls` …）再注入唯一锚点，避免官方互斥组互相顶掉。

现在 66 拍全部体检通过：每拍恰好 `1girl + solo` 或 `1girl + 1boy`，没有残留 `2people`。

### 新增 34 个剧情标签

催眠 / 时间停止 / 青梅竹马这几个题材需要的标签，原来库里没有，都是新加的
（并进正式 `TAGS` 主表，所以有中文名、有分级、参与强度过滤，SFW 模式下也会被拦）：

```
spiral eyes 漩涡眼    swirl eyes 螺旋眼      hypnosis 催眠
mind control 精神控制  trance 恍惚失神        blank eyes 空洞的眼神
pink pupils 粉色瞳孔   glowing eyes 发光眼    pendulum 摆锤
time stop 时间停止    frozen in time 凝固     suspended motion 动作悬停
dust suspended in air 悬浮尘埃               clock 时钟 / pocket watch 怀表
stopwatch 秒表        clock tower 钟楼       time manipulation 时间操纵
childhood friend 青梅竹马  promise 约定      photo album 相册
childhood photo 童年照片  bloomers 运动短裤   randoseru 小学生书包
sunflower field 向日葵田  riverbank 河堤     reminiscing 回忆 / nostalgic 怀旧
```

标签库 11067 → **11097** 条（+34，去重后 30 条生效）。

### 其它

- `CONTINUITY` 去掉了 `film grain`（新故事线的 style 里本来就有，避免重复标签）
- 离线冒烟测试的 fixture 扩到 **11 条故事线 / 198 拍**展开结果
- 验证脚本新增「剧情全库体检」：遍历 11 线 × 6 拍 × 全部主角，
  确认**没有重复标签、没有引号、每拍都带 char_lock、每拍都有台词**

## v1.9.0 — 2026-10-12

### 新增：📖 剧情模式（故事线 + 主角固定 + 跨图连续）

面板顶部多了 **📖 剧情**。进去以后分三层选：**故事线 → 主角 → 具体一拍**，
点「🎬 套用这一拍」就把这一拍的内容写进节点，然后自动回到标签视图。

**收录 8 条故事线 / 48 拍**，每条 6 拍：

| 故事线 | 题材 | 可主角 |
|---|---|---|
| 加班夜 | 职场 / 偷情 | 亚丝娜 / 高雄 / 优香 |
| 温泉旅馆 | 和风 / 温泉 | 雷电将军 / 高雄 / 亚丝娜 |
| 放学后的教室 | 校园 | 白子 / 优香 / 惠惠 |
| 雨夜酒店 | 旅行 / 一夜情 | 高雄 / 宝钟玛琳 / 亚丝娜 |
| 公会之夜 | 奇幻冒险 | 惠惠 / 达克妮丝 / 亚丝娜 |
| 下播之后 | 现代 / 主播 | 宝钟玛琳 / 雷电将军 / 优香 |
| 夜晚的海 | 夏日 / 海边 | 白子 / 高雄 / 优香 |
| 训练场之后 | 奇幻 / 训练 | 达克妮丝 / 雷电将军 / 亚丝娜 |

每一拍都有**中文台词**（面板里读）+ **英文台词**（写进提示词，模型看得懂语气）
+ **场景标签**。台词是我写的，`py/story.py` 里可以直接改。

### 连续性是怎么保证的

这是这个功能的核心，靠四件事叠加：

1. **同一个 `char_lock` 主角** —— 每一拍都带上 `char_lock:<角色名>`，
   配合互斥组保证一次只画一个主角，且角色触发词写法完全一致
2. **同一套立绘标签** —— 每个主角在 `CAST` 里写死了发色 / 瞳色 / 体型等
   （比如雷电将军 = `purple hair, very long hair, braided ponytail, purple eyes,
   mole under eye`），每一拍都自动带上
3. **固定服装** —— 每个主角一套固定 outfit，并且以**「锁定角色」预设**
   （`... [L]`）写进 `outfit_preset`，所以跨图不会换衣服
4. **同一套镜头与风格 + 种子成序列** —— 每条故事线固定 `setting` / `style` / `camera`，
   套用时把**种子模式自动切成「递增 +1」**，这样连点 6 次生成就是一条连续的序列

### 面板细节

- 主角按钮带**立绘缩略图**，一眼看出是谁
- 分镜卡片显示：第几拍 / 本拍标题 / 中文台词 / 英文台词 / 场景标签数 / 主角立绘
- 「复制台词」一键拿中文台词
- 故事栏下面有实时说明：这一卷的题材、尺度、梗概
- 卡片底部解释连续性是怎么保证的（用了哪些标签）

### 修复：双人镜头画成「双胞胎」

官方「单人 / 多人」标签属于**同一个互斥组**，场景标签里同时有 `2people` 和
`solo` 时，`solo` 赢了 —— 结果男主角锚点 `1boy` 被顶掉，模型不知道该画谁，
就自己编了一个第二人。实测第 5 拍（雪落下来，本该是她和你）画出了一个双胞胎。

现在 `build_scene()` 会**显式补人物数量锚点**，并且放在场景标签之前：

- 这一拍有第二个人（`2people` / `kiss` / `leaning forward` 等信号）
  → 注入 `1boy, 1girl`
- 否则 → 注入 `1girl, solo`

全库 48 拍里 28 拍是双人、20 拍是单人，每拍都只留一个正确的数量锚点。
另外 `2people` / `afterglow` 这类只是我们内部的语义标记，不再写进提示词。

### 修复：套用剧情后标签被覆盖回去

`applyStoryScene` 写入 `tags` 之后，面板内部的 `selected` / `order` 还是旧的，
于是「应用/关闭」时 `commit()` 用 `joinTags(order)` 把旧标签写了回去 —— 套用等于白做。
现在套用后会调用新增的 `syncSelectionFromNode()` 重建面板选中态。
**这个 bug 是离线冒烟测试抓到的**（`套用后 tags 没变化`）。

### 其它

- 新增 `py/story.py`；`GET /anima_nsfw/story` 给剧情库，
  `GET /anima_nsfw/story/scene?arc=&scene=&cast=` 展开某一拍
- `/anima_nsfw/tags` 新增 `story` 统计
- 离线冒烟测试新增 8 项剧情断言（含「换主角生效」），并给桩加了
  `story_fixture.json`（144 个镜头展开结果）

## v1.8.0 — 2026-10-12

### 先回答你的问题：之前的种子是「固定」的

- **描述种子**（决定自然语言描述用哪套句式）：节点上的 `caption_seed`，示例工作流里写死
  `1234` —— 同一组标签永远生成同一段描述
- **出图种子**：在 KSampler 上，示例工作流里写死 `20260214` / `20260215`
- 但 ComfyUI 的 UI 上 KSampler 的 seed 旁边有个 `control_after_generate` 控件，
  默认是 `randomize` —— 所以在界面里连点生成**是会换图的**，
  而通过 API 提交时那个控件不起作用，种子就是死的。两边不一致。

### 新增：种子随机 / 固定选项

提示词面板的 `optional` 里加了两个输入：

| 输入 | 说明 |
|---|---|
| `seed_mode` | `固定（每次同图）` / `每次随机` / `递增 +1` / `递减 -1` |
| `seed` | 种子数值 |

面板左侧也多了一行 **🎲 种子**：模式下拉 + 数值框 + 「🎲 抽一个」按钮，
和节点控件双向同步，下面还有一行说明（比如「将写入 2 个采样器」）。

**关键点：种子会真的写进下游 KSampler。** 面板沿本节点的输出连线往下找到所有
采样器（`KSampler` / `KSamplerAdvanced` / `RandomNoise`，深度最多 6 层），然后：

| 模式 | 写入采样器的行为 |
|---|---|
| 固定（每次同图） | `seed = 你填的值`，并把自动控制设为 `fixed` |
| 每次随机 | **立刻抽一个新 seed 写进去**，并把自动控制设为 `randomize`（连点生成会一直换图） |
| 递增 +1 / 递减 -1 | 把自动控制设为 `increment` / `decrement`，每生成一次自动加减 |

这样**不改工作流结构**（不用重新连线、不用加额外节点），也解决了
「API 提交时种子是死的」那个不一致。按「应用」时会弹提示告诉你写了几个采样器。

种子是 15 位随机数（`crypto.getRandomValues` 优先，退回 `Math.random`）——
不用满 64 位，因为 JS 的 Number 超过 2^53 会失真。

### 其它

- 仅描述节点（`AnimaNsfwCaptionOnly`）的 `seed` 补了说明：同 seed + 同标签 = 同描述
- 离线冒烟测试新增 4 项：**真的会建两个假 KSampler 并接上输出连线**，
  验证「固定模式写入正确值」「随机模式每次抽新值」「自动控制设为 randomize」
  「节点控件同步」

## v1.7.0 — 2026-10-12

### 新增：角色立绘缩略图

角色卡片现在是 **3:4 立绘 + 名字 + 作品/热度**，不再是纯文字。

- 图片来自 Animadex 官方 thumbs：`blobs.animadex.net/Outputs/thumbs/<角色名, 作品名>.webp`
- **覆盖率**：抽样 60 个角色实测命中 **56 个（93%）**；404 时自动退回「无图」占位，
  不会留破图
- 跟着面板上的 **🖼 缩略图 开/关** 一起走 —— 关掉后不出图，完全离线可用
- 图片是 `loading="lazy"`，滚到视野内才请求

### 新增：角色网格分页（懒加载）

之前一次最多建 150 张卡片，角色一多就得靠搜索。现在：

- 每个作品先渲染 **60 张**，往下滚自动加载下一批
- 用 `IntersectionObserver`（`rootMargin: 300px`）预取，滚动手感是连续的
- 老前端没有 `IntersectionObserver` 时，自动换成「加载更多」按钮
- 切换作品 / 分类 / 搜索词会回到第一批

### 新增：轻小说分类（38 部）

`COPYRIGHT_GROUPS` 多了 **📖 轻小说**，`COPYRIGHTS` 里也多了 38 部作品名。

选品方式：先用已知轻小说作品名去本地 8000 角色库里匹配，再用**该作品最热的两个真实角色名**
去 Animadex 探测有没有图 —— 有图才收录。这样得到的版权 tag 一定和角色库的写法一致。

```
23 角色  toaru majutsu no index        魔法禁书目录 / 某科学的超电磁炮
21 角色  sword art online              刀剑神域
14 角色  monogatari (series)           物语系列
13 角色  kagerou project               阳炎计划
11 角色  high school dxd               恶魔高校 DxD
10 角色  kono subarashii sekai ni shukufuku wo!  为美好的世界献上祝福！
10 角色  to love-ru                    出包王女
 8 角色  zero no tsukaima              零之使魔
 7 角色  date a live                   约会大作战
 6 角色  ore no imouto ...             我的妹妹不可能那么可爱
 6 角色  durarara!!                    无头骑士异闻录
 ... （共 38 部：龙与虎 / 无职转生 / 冰菓 / 中二病 / 无限斯特拉托斯 /
      Overlord / 地错 / 哥布林杀手 / 我的朋友很少 / 盾之勇者 / 转生史莱姆 /
      灼眼的夏娜 / 狼与香辛料 / 游戏人生 / 邪神酱 / 笨蛋测验召唤兽 /
      魔法科高中 / GATE / 记录的地平线 / 谭雅战记 / 加速世界 / 奇诺之旅 /
      噬血狂袭 / 实力至上主义教室 / 落第骑士 / 新妹魔王 / 学园默示录 等）
```

**互斥组用的是独立的 `light_novel_base`**：轻小说和游戏/抽卡是两类作品，
让它们能同时选（比如「原神角色 + 刀剑神域角色」这种跨作品构图），
而同为轻小说的两部作品之间仍然互斥。

顺便清理了 `COPYRIGHTS` 里两条重复（`sword art online`、
`tensei shitara slime datta ken`），它们已由轻小说表接管。

### 修复：`charWork` 变量名不统一

新的分页渲染器里我误用了 `charWorkFilter`，而实际变量叫 `charWork` ——
点「🧑‍🎤 角色」会直接抛 `ReferenceError`。离线冒烟测试抓到的，已统一。

### 其它

- `/anima_nsfw/tags` 新增 `light_novel_count` / `light_novel_titles`
- 标签库 11031 → **11067** 条（+38 轻小说，-2 重复）

## v1.6.1 — 2026-10-12

### 兼容：老工作流不会因为多了 mode 而打不开（重要）

`mode` 一开始放进了 `required`，结果 **v1.6.0 之前保存的工作流直接 400
`required_input_missing`** —— 用户看到的就是「工作流加载不出来 / 节点报缺少必需的输入」。

关键点：ComfyUI 的校验顺序是 **INPUT_TYPES → build()**，
所以光在 `build()` 里给默认值没用，必须让 `mode` 根本不在 `required` 里。

现在：

- `mode` 移到 **`optional`**（带 `default: NSFW（不限）`）
- `build()` 的 `mode` / `base_enabled` / `intensity` 等参数也都给了默认值
- 控件位置不变，示例工作流里也去掉了这个参数
- **已用真实请求验证**：把 `mode` 从 prompt 里删掉，出图正常（panel_00021）

## v1.6.0 — 2026-10-12

### 新增：SFW / NSFW 双模式（一个节点两用）

提示词面板和负面构建器都加了 **`mode`** 下拉：`NSFW（不限）` / `SFW（全年龄）`。
面板头部也多了一个一键切换按钮（`🔞 NSFW（不限）` ⇄ `🧸 SFW（全年龄）`）。
以后画全年龄和画露骨内容不需要再维护两套提示词节点了。

**为什么不用 rating（分级）来判**：分级太粗 —— `school swimsuit`、
`black thighhighs`、`leotard` 都被标成 hard，但它们是正常服装；反过来
`nipples`、`covered nipples` 是 soft，却显然不该出现在 SFW 里。
所以改成两层判据：

| 层 | 内容 | 说明 |
|---|---|---|
| 1 | 显式露骨词表 257 条 | 性行为/性器官/体液/束缚/裸露/泳装内衣/氛围场景，命中即拦 |
| 2 | 服装白名单 60 条 | 泳装内衣等**具体单品**：只有预设自动带进来才豁免 |

第 2 条是关键：你选「芭蕾舞服」，预设里的 `leotard` 会保留；
但你自己去点 `leotard` 会被拦下。这样 `thighhighs`、`pantyhose`、
`corset`、`leotard` 这类正常服装不会被误杀（早期草稿把它们放进黑名单，
结果 351/518 套服装预设被误杀，已修正）。

**SFW 模式下还会**：

- 正向自动追加 `rating:safe, safe, general`（booru/Anima 系最强的一道保险，
  从训练数据分布上把画面推向全年龄）
- 负面把「NSFW 安全」段换成全年龄向反向词：
  `nsfw, explicit, nude, naked, topless, nipples, pussy, penis, sex, cum,
  cumshot, creampie, ahegao, bondage, blood, gore, violence…`
- 自然语言描述不再写性行为、体液、裸露，收尾换成
  `The overall mood stays light and wholesome.` /
  `Nothing in the frame goes beyond an all-ages illustration.` 这类句式
- 面板侧栏把 **性爱姿势 / 前戏服务 / 自慰单人 / 体液射精** 四个分类整条收起，
  网格里被拦下的标签也一并藏掉（已选中的仍显示，方便取消）
- 已经选中的露骨标签会在应用时被自动剔除，并在预览的 `dropped.sfw` 里列出

### 兼容：老工作流不会因为多了 mode 而打不开

`mode` 一开始放进了 `required`，结果 **v1.6.0 之前保存的工作流会直接 400
`required_input_missing`** —— 用户表现就是「老工作流加载不出来」。
ComfyUI 的校验顺序是 INPUT_TYPES → build()，所以 `build()` 里给默认值不管用。

现在 `mode` 改到 `optional`（带 `default`），并且 `build()` 的 `mode` /
`base_enabled` 等参数也都给了默认值。控件位置不变，示例工作流也不需要带这个参数。
已用真实请求验证：把 `mode` 从 prompt 里删掉照样能出图。

### 修复：「NSFW 安全」负面段落勾了没效果

前端发过来的段落名是 `NSFW安全`（无空格），而后端字典的键是 `NSFW 安全`
（有空格），`NEGATIVE_EXTRA.get()` 永远返回 None —— 也就是说从 v1.0 起
这个勾选项就没生效过。现在 `compose_negative()` 做了空格容错匹配，
两种写法都能命中；前端也统一成了带空格的键名。

### 修复：`is_sfw()` 的 `nsfw` / `sfw` 子串陷阱

初版写成 `"sfw" in mode.lower()`，而 `"nsfw"` 里**包含** `"sfw"`，
结果 NSFW 模式被误判成 SFW（一开面板所有露骨标签就被拦）。
现在先检查明确的 NSFW 标记，再看 SFW 标记，前后端逻辑一致。

### 其它

- 标签库注册了 4 个 SFW 安全词（`rating:safe` / `safe` / `general` / `nsfw`，
  均为 hidden，勾「显示隐藏标签」可见）
- `/anima_nsfw/tags` 新增 `sfw` 字段：`modes` / `hidden_categories` /
  `block_count` / `quality` / `block_keys`（前端据此过滤网格）
- 新增 `py/sfw.py`；离线冒烟测试增加了模式切换断言（现代 + 低版本前端都跑）

## v1.5.2 — 2026-10-12

### 修复：面板点了没反应（严重）

**根因**：模块顶层调用了只在 `buildPanel` 作用域内的 `loadChars()`：

```js
// 文件末尾（模块作用域）
loadTagData().catch(() => {});
loadChars().catch(() => {});   // ← ReferenceError
```

模块一加载就抛 `ReferenceError`，`app.registerExtension()` 从未执行 →
节点上没有面板按钮 / 点了没反应。同一函数在 `openPanel` 里也被错误调用了一次。
现在两处都改到正确作用域（`buildPanel` 内）。

### 修复：低版本 ComfyUI 前端打不开

之前 `ensurePreviewWidget()` 直接调用 `node.addDOMWidget()`，
老前端没有这个 API → 抛异常 → `setupBuilder` 中断 → 连按钮都出不来。
现在：

- `addDOMWidget` 缺失/抛错 → **自动退回画布绘制预览**（`onDrawForeground` 画几行文字）
- 新增 `raf()`：`requestAnimationFrame` 不存在时用 `setTimeout`
- 新增 `setStyle()`：`element.style.cssText` 被限制时逐条赋值
- 复制按钮改用 `copyText()`：没有 `navigator.clipboard` 时退回 `execCommand("copy")`
- 所有 `localStorage` 访问都在 try/catch 内（无痕模式/禁用存储也不会炸）
- `openPanel()` 全程加保护：构建失败会弹窗提示并把错误打到控制台，
  而不是静默失败

### 新增：离线冒烟测试（不需要启动 ComfyUI）

`tools/animansfw_panel_smoke.mjs` —— 用 Node 桩出 DOM / app / fetch，
把面板 JS 真跑一遍：模块加载 → 注册扩展 → onNodeCreated → 点按钮 →
面板浮层是否挂上 → 点里面的每个按钮/分类 → 画布回调。

```bash
node tools/animansfw_panel_smoke.mjs            # 现代前端
node tools/animansfw_panel_smoke.mjs --legacy   # 模拟低版本（剥掉 addDOMWidget 等）
```

两种模式都必须全绿才算通过。**这个测试不启动 ComfyUI、不联网**（fetch 全走桩，
数据来自 `tools/tags_fixture.json`）。

## v1.5.1 — 2026-10-12

### 改进：角色按作品归位（不再是 8000 个平铺）

之前的「角色名」分类把 8000 个角色平铺在一起，没法用。现在改成 **作品 → 角色** 层级：

- **侧栏的「游戏/作品」变成可展开的父项**：点作品名 → 网格先铺开该作品的全部角色
  （卡片形式），下面再跟这个作品名标签本身；点左侧 ▶ 则在侧栏就地展开角色名单
- 作品列表**合并了两处来源**：标签库里精挑的 104 个热门作品 + 角色库里
  实际有角色的 826 个作品（按角色数排序），并带**搜索框**
- 「角色名」分类**从侧栏移除**（避免和作品层级重复、也避免那个混乱的平铺）
- 「🧑‍🎤 角色」视图保留，作为需要跨作品找角色时的入口（作品条 + 搜索）

### 中文名覆盖率说明

- 作品名：234 / 826 有中文
- 角色名：310 / 8000（手工校对 231 + 本机中文资料 79）
- 其余角色显示罗马音 —— 这是 Anima 的标准写法，不影响出图。
  想看中文可以自己补 `py/character_names_zh.py`

### 修复

- 上一轮补丁把面板 JS 里 hiddenRow 那一块写重复了、并截掉了后半部分代码。
  已从发布包恢复并重做补丁（当前 106 KB，语法校验通过，关键函数齐全）

## v1.5.0 — 2026-10-12

### 新增：中文翻译层（所有标签都有中文）

之前有 2198 条标签的 `zh` 只是英文占位（服装库导入的细碎词），现在全部过一遍
分层翻译：

1. **手工校对表** `CURATED`（137 条）—— 修正机翻离谱的条目
2. **本机中文资料** `MERGED`（4531 条）—— 合并
   `ComfyUI-Danbooru-Anima-Prompt` 的 `weilin_tags.db`(3637) + `all_tags_cn.json`(1269)
3. **逐词词典** `WORDS`（529 词）—— 组合词逐个翻译，例如
   `aqua shawl` → 水蓝披肩、`armpit cutout` → 腋下镂空、`barcode tattoo` → 条形码纹身
4. 都命中不了就保留英文（Anima 照样认，不影响出图）

新增 `py/translations.py`，并提供 `coverage()` 便于统计。
非角色标签的翻译覆盖率从 **0% → 约 93%**（完全中文 2341 + 中英混合 1186）。

### 新增：角色库（8000 个角色，可选标签）

从本机 `Comfyui-Anima-Tools` 的角色资料合并生成
（`character_official_data.json` 的触发词与推荐标签 +
`character_data.js` 的作品/热度），共 **8000 个角色 / 826 个作品**：

- 新增「角色名」分类，**所有角色共用一个 `character_base` 互斥组**
  （一张图只可能是一个角色，换角色会自动替换）
- 热度 ≥ 300 的 **6412 个角色默认可见**，其余 1588 个标记 hidden
  （搜索 / 按作品筛 / 勾「显示隐藏标签」都能找到）
- 面板新增 **🧑‍🎤 角色** 视图：按作品筛选（角色数最多的前 24 个作品做成一排按钮）
  + 中英日文搜索，卡片显示中文名 / 英文名 / 作品 / 热度 / 标签数
- 选中角色后会出现一条提示条，**一键补齐该角色的推荐标签**
  （资料里给该角色标注的发色、瞳色、服装等）
- 数据文件 `web/characters.json`（1.7 MB）；后端只在需要时读取

### 中文名覆盖率说明

- 作品名：234 / 826 有中文（热门作品全覆盖）
- 角色名：**310 / 8000** 有中文，其中 231 条是手工校对的
  （`py/character_names_zh.py`），另外 79 条来自本机中文资料

**为什么大部分角色没有中文名**：本机那份中文资料里角色词条只有 103 条，
逐词翻译对日本人名会出灾难性错误（实测把 `saber alter` 译成"圣诞老人"、
`koakuma` 译成"小熊"）。所以我加了黑名单校验，**宁可留英文也不给错的中文名** ——
角色名用英文/罗马音是 Anima 的标准写法，对出图没有影响。
想补中文名：在 `py/character_names_zh.py` 里加一行、重跑生成脚本即可。

### 其它

- `py/character_store.py` 角色库读取（延迟 + 缓存）
- 新增接口 `GET /anima_nsfw/characters`
- 标签库 3047 → **11027 条**（+8000 角色），分类 13 → **14**

## v1.4.1 — 2026-10-12

### 修复：「预设补充」分类点进去什么都没有

**原因**：那个分类里 2187 个标签**全部**是自动兜底的 `hidden` 标签
（衣服颜色变体、手持物、饰品这类细碎词），而面板默认不渲染 hidden 标签。
侧栏却显示了这个分类，点进去自然是空白 —— 是个 UX bug。

**改动**

- **全是隐藏标签的分类不再出现在侧栏**，「预设补充」因此从分类列表里消失
- 侧栏新增 **「显示隐藏标签 (2187)」勾选框**：勾上后这些细碎词
  在各自分类里都能浏览与点选（下方有说明文字）
- 「全部标签」的计数改成**只统计可见标签**（不再虚高）
- 选中过但被隐藏的标签照旧会显示在已选区，不影响使用

### 改进：把 100 个常用细碎词提升为正常标签

`outfit` 272（+70）· `body` 94（+12）· `prop` 88（+12），
例如 `argyle` 格纹、`anklet` 脚链、`off shoulder` 露肩、`zettai ryouiki` 绝对领域、
`underboob`、`plunged neckline` 深 V、`turtleneck` 高领毛衣、`tuxedo` 燕尾服、
`sunglasses` 太阳镜、`hoop earrings` 圈状耳环、`stethoscope` 听诊器…
这些本来就常用，不该埋在隐藏里。

### 说明

「预设补充」的设计目的是**让服装/姿势预设里的每一个标签都能被后端正确处理**
（去重、互斥、排序、强度过滤），它们不是一个给人逐条翻阅的标签集。
现在既能保持干净的默认视图，也能在需要时展开查看。

## v1.4.0 — 2026-10-12

### 新增：作品 / 版权标签（104 个）

新增「游戏/作品」分类，覆盖本地 Anima 角色库里出现频次最高的作品（826 个不同
作品里挑出 104 个），并给出中文名：

- 📱 手游：`blue archive` 蔚蓝档案 · `azur lane` 碧蓝航线 · `kantai collection` 舰队
  Collection · `arknights` 明日方舟 · `genshin impact` 原神 · `honkai: star rail` 崩铁 ·
  `umamusume` 赛马娘 · `nikke` · `wuthering waves` 鸣潮 · `zenless zone zero` 绝区零…
- 🎮 游戏：`fate (series)` · `pokemon` · `fire emblem` · `final fantasy` · `persona 5` ·
  `nier: automata` · `league of legends` · `elden ring`…
- 📺 动画/漫画：`touhou` 东方 · `precure` · `evangelion` · `jojo` · `gundam` ·
  `danganronpa` · `chainsaw man` · `bocchi the rock!`…
- 🎤 偶像/音乐：`hololive` · `nijisanji` · `vocaloid` · `idolmaster` · `bang dream!`…
- 🌐 其它：`original` 原创角色

**所有作品名共用一个互斥组**（`copyright_base`）：一次只画一个作品的角色，
多选只会互相覆盖，避免「原神 + 蔚蓝档案」这种必然崩坏的组合。

> 顺带修了一个 bug：`touhou` / `kantai collection` 这类词既在作品表里，
> 又出现在某些服装库套装的标签里，之前会被自动兜底的 hidden 标签覆盖，
> 导致在作品分类里看不见。现在自动兜底不再盖掉手工登记的标签。

### 新增：自定义库「⭐ 我的」（触发词 / 角色 / 服装 / 姿势）

面板新增 **⭐ 我的** 视图，四类可保存、编辑、删除、一键套用：

| 类型 | 用途 | 「套用」行为 |
|---|---|---|
| 🔑 我的触发词 | LoRA 触发词、画师名、常用前置词 | 拼到「前置文本」最前面，不动已选标签 |
| 🧑 我的角色 | 角色名 + 一串标签（可当角色模板） | 角色名与标签一起铺进标签选择 |
| 👗 我的服装 | 自己搭的服装套装 | 等同服装预设 |
| 🧍 我的姿势 | 自己常用的姿势组合 | 等同姿势参考 |

- 面板底部新增两个快捷按钮：**🔑 存为触发词**（存 `extra_front` 的内容）、
  **🧑 存为角色**（存当前选中的全部标签 + 第一个标签当角色名）
- 持久化：写进节点目录的 `custom_library.json`（重启不丢、可直接备份/分发），
  浏览器 localStorage 仅作离线兜底；后端不可用时会提示「暂存到浏览器」
- 支持 **导出 / 导入**（同名同类型覆盖），方便换机器或分享自己的角色库
- 每类上限 500 条、单条最多 120 个标签，避免文件无限膨胀

### 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/anima_nsfw/custom` | 读取自定义库 + 存储路径/配额信息 |
| POST | `/anima_nsfw/custom/save` | 新增或更新（带 id） |
| POST | `/anima_nsfw/custom/delete` | 删除 |
| POST | `/anima_nsfw/custom/import` | 合并导入 |
| GET | `/anima_nsfw/custom/export` | 下载 JSON 备份 |
| GET | `/anima_nsfw/status` | 适配器清单 + profile 参数 |

### 关于「质量词 / 负面是否内置」

两者**从 v1.0.0 起就已内置**，本次只是补充文档说明（见 README 第 5 节）：

- 质量预置 5 档：`turbo` / `base` / `pony（score_ 系）` / `极简` / `无`
- 负面：`base_enabled` 给 325 字符通用负面，另有 6 段可勾选补丁
  （手部修复 / 面部修复 / 人体结构 / NSFW 安全 / 画面干净 / 防伪影）

### 测试

- 自定义库 API 全链路：新增 / 更新 / 删除 / 读取 / 导出，
  空名字与未知类型被正确拒绝（HTTP 400），测试数据自动清理
- 版权标签：104 条全部带中文、全部挂在 `copyright_base` 互斥组
- 标签库 2941 → **3037 条**（+104 作品名，hidden 2271）

## v1.3.0 — 2026-10-12

### 新增：预设可视化缩略图

- 服装预设卡片显示预览图（服装库 430 套全部带图，84×126 竖版）
- 姿势参考卡片显示预览图（297 个全部带图，166×150）
- 图片用 `<img loading="lazy">` 懒加载，失败/离线自动退回「无图」占位，不留破图
- 顶部 **`🖼 缩略图 开/关`** 一键切纯文字模式，状态存 localStorage
- **本包不打包任何图片**：预览图直接从上游 CDN 加载
  （Dressing-doll / AnimaTags-DB），避免几十 MB 体积与二次分发
- 预设卡片一次最多渲染 150 张，避免 800+ 卡片带图拖慢面板

### 新增：姿势参考库（297 个 / 8 组）

从本机 `Comfyui-Anima-Tools/js/pose_data.js`（Anima 姿势选择器）导入：

🙌 手势与手臂 100 · 🚶 日常与其它 92 · 💇 整理服饰发型 25 · 👥 双人与互动 24 ·
🎒 道具与携物 22 · 🤸 站立与动态 14 · 🪑 坐姿 12 · 🛏 卧姿与趴姿 8

- 新增 `姿势参考` 控件，姿势标签插在「身体之后、性交动作之前」
  （对应 Anima 语法的 外观 → 姿势 → 动作），与服装/其它标签可自由组合
- 提示条现在同时显示生效中的服装预设与姿势参考，各自可单独取消

### 变更

- 标签库 2455 → **2941 条**（新增姿势库标签）
- `rank_of()` 顺序调整：新增 outfit 档，手工与导入预设的顺序更符合 Anima 语法
- 顶部按钮增加姿势参考与缩略图开关；面板 JS 从 46 KB 增至 58 KB

### 测试

- 服装 430 套 + 姿势 297 个，**预览图 URL 100% 存在**，抽查 HEAD 200 image/webp
- 预设标签 100% 存在于标签库
- 端到端：`serafuku` 服装预设 + `Arms Behind Back` 姿势预设 + 用户标签
  真实出图 success，姿势词位置正确

## v1.2.0 — 2026-10-12

### 新增：导入「Anima 服装 tag 选择器」的 430 套服装

从本机 `Comfyui-Anima-Tools/js/clothing_data.js` 导入，服装预设 **88 → 518 套**
（手工精选 88 + 服装库 430），分组 **8 → 14 组**。

- 导入脚本 `tools/animansfw_import_dressing.py` 会清洗源数据：
  剥权重（`(sweater dress:1.1)` → `sweater dress`）、去转义与不成对括号
  （`pom pom \(clothes` → `pom pom`）、`_` 转空格、标签去重、重名加序号
- 按原始分类重新映射成 6 个分组：日常休闲 74 / 性感暴露 160 / 礼服裙装 64 /
  泳装内衣 63 / 制服西服 41 / 角色扮演 28
- 用源库英文名当卡片标题（比机翻中文名好认），中文名放副标题
- 源库涉及 1978 个不同标签，其中 1788 个主标签表没有的细碎单品词/发色/手持物，
  自动登记进「预设补充」并标 `hidden`：网格默认不展示，选中后正常出现在已选区

### 新增：面板来源筛选

服装预设视图新增「来源」筛选：`全部 518` / `手工精选 88` / `服装库 430`；
分组条与搜索（预设名/英文名/角色名/标签内容）均支持联合过滤，搜索带 140ms 防抖。

### 变更

- 标签库 701 → **2455 条**（大部分是 hidden 的预设补充标签）
- 导入预设的卡片标题用英文名，副行显示中文名 + 标签数 + 来源

### 测试

- 预设标签 100% 存在于标签库（0 缺失）
- 源数据权重残留 0 处，生成的 `preset_import.py` 无 SyntaxWarning
- 端到端：三条「服装库」预设（泳装/礼服/性感暴露）真实出图全部 success

## v1.1.0 — 2026-10-12

### 新增：服装预设（88 套 / 8 组）

面板顶部新增 **👗 服装预设** 视图，一键铺一整套服装标签。

- **分组**：🎒 校园 10 · 💼 职业 11 · ⛩️ 传统和风 10 · 🩱 泳装内衣 10 ·
  ⚔️ 奇幻战斗 12 · 🎤 偶像舞台 6 · 👗 日常礼服 12 · 🎮 游戏角色 17
- **两类预设**：仅服装 / 🔒 锁定角色（预设第一个标签为角色触发词）
- **角色互斥**：套了锁定角色预设会自动清掉手选的其它角色；换预设直接替换角色。
  用户手打角色名也会被识别（靠 `locked_characters` 名单），不会出现双角色打架
- **服装优先**：预设生效时，用户手选的另一套 `outfit_base` 服装会被挤掉，
  不会出现「预设是死库水、同时还留着校服」
- 节点上新增可见的 `服装预设` 控件，序列化格式 `名字[L],,tag1, tag2`，
  可以手改、可以自己加私有套装

### 新增：服装标签大幅扩充

- 新增「服装」分类：141 条服装本体标签（水手服/校服/体操服/死库水/旗袍/汉服/
  巫女服/女仆/护士/兔女郎/振袖/浴衣/骑士铠甲/乳胶衣/偶像打歌服/婚纱…），
  `outfit_base` 组互斥，选一套就自动换掉上一套
- 新增「预设补充」分类与 39 条隐藏标签（角色名/版权名），
  只在被预设选中时出现在已选区
- 补充发色/瞳色（11 条）、道具手持物（24 条）、服装细项（60 条）、场景细项（18 条）
- 标签库从 393 → **701 条**，分类 10 → 12
- 所有标签都核对过本地 Anima 角色数据（7999 个角色的触发词与标签分布），不是自造词

### 修复

- 质量预置与标签重复时会输出两遍（例如 `best quality, best quality`），
  现在 `_join` 会做一次逗号级去重
- 空 `tags` 的报错文案补充了「或套一个服装预设」

### 测试

- 纯逻辑测试：预设标签 100% 存在于标签库、互斥/去重/角色锁定/服装替换
- 端到端：死库水 / 初音未来（锁定）/ 骑士铠甲 三套预设真实出图全部 success
  （768×768 → 1024×1024，Turbo LoRA）

## v1.0.1 — 2026-10-12

### 修复

- **`缺少必需的输入: tags`**（严重）
  面板为了隐藏 `tags` 控件曾把它设成 `widget.type = "hidden"`，
  而 ComfyUI 生成 prompt 时会直接跳过 `type === "hidden"` 的控件，
  于是 `tags` 根本没进请求体，报「缺少必需的输入」。
  现在改为**只接管绘制与高度**（`draw = () => {}` + `computeSize = () => [0, -4]`），
  控件本体、`type`、`value`、序列化行为全部保持原样。
- 面板写回标签时不再触发 `widget.callback`（避免与面板内部刷新互相打断）。

### 新增

- 后端防御：`tags` 为空时报出可读的中文错误
  （「请点节点上的 🎛 打开 NSFW 面板…」），而不是静默出一张没有提示词的图。

### 文档

- README 3.1 节补齐完整连线图与链路顺序说明
  （`UNETLoader → LoRA → 调制引导 → ModelSamplingAuraFlow → KSampler`）。

## v1.0.0 — 2026-10-12

首个版本。

### 新增节点

- **Anima NSFW 提示词面板**（`AnimaNsfwPromptBuilder`）
  - 393 条 NSFW 标签，10 个分类，含中文名
  - 可视化浮层面板：分类、中英文搜索、风险颜色分级（soft/hard/extreme/meta）
  - 同互斥组自动互相取消；按 Anima 推荐顺序自动排序；去重
  - 三档强度（soft/hard/extreme）自动剔除超档标签，并支持一键铺底
  - 自动生成 Anima 风格自然语言描述（模板化，不依赖 LLM；中英通用）
  - 输出 `positive` + `info`（JSON 调试信息）
- **Anima NSFW 负面构建器**（`AnimaNsfwNegativeBuilder`）
  - 基础负面 + 6 段可勾选补丁（手部/面部/人体/NSFW 安全/画面干净/防伪影）
- **Anima 调制引导**（`AnimaNsfwModGuidance`）
  - AdaLN 调制空间的质量引导，`MODEL → MODEL` 补丁，与 CFG 正交可叠加
  - 分层调度（start/end/taper/final_w）与 6 个 profile
  - σ-FiLM 适配器自动识别，缺失时回退 σ-flat
- **Anima NSFW 描述生成**（`AnimaNsfwCaptionOnly`）

### 接口

- `GET  /anima_nsfw/tags` — 标签库 + 预置
- `POST /anima_nsfw/preview` — 与后端同一份合成逻辑做实时预览
- `GET  /anima_nsfw/status` — 适配器清单 + profile 参数

### 实测记录

- ComfyUI 0.39.0 / 前端 1.53.10 / Python 3.12.10 / torch 2.9.1+cu130 / RTX 5070 12G
- 端到端：1024×1216 → Latent ×1.5 → 1536×1824，Turbo LoRA 12 步 / CFG 1，
  单张约 35 s
- 调制引导同 seed A/B：关闭 vs 开启像素差 mean=47.6（确认生效）；
  `w=3` 会让偏粉像素从 0.01 升至 0.17，故默认 profile 设为 `light_w1.5`
  并在 README 6.5 节记录完整数据

### 已知限制

- 调制引导需要用户自行下载 `pooled_text_proj-0611.safetensors`（约 12 MB），
  本包不自动联网下载
- 调制引导在部分模型 + LoRA 组合下会降低饱和度/偏粉，可用 `light` profile
  或直接关闭；它与提示词面板是两个独立节点
- 自然语言描述为模板拼接，不是 LLM 生成；想要更自然的措辞请填
  `caption_text` 或用 LLM 节点
