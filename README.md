# ComfyUI-Anima-NSFW-Panel

> **Anima 专用的 NSFW 提示词可视化面板 + 剧情模式 + 调制引导**
> 把「选标签 → 合成提示词 → 出图 → 修复 → 放大 → 保存」全链路做完的 ComfyUI 节点包。

适用范围：[circlestone-labs/Anima Base](https://huggingface.co/circlestone-labs/Anima)（Qwen3-0.6B 文本编码器 + T5XXL + 28 层 DiT）。

[![ComfyUI](https://img.shields.io/badge/ComfyUI-%E2%89%A5%201.12.8-blue)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()
[![NSFW](https://img.shields.io/badge/Content-NSFW-red)]()

---

## 目录

- [这是什么](#这是什么)
- [核心特性](#核心特性)
- [安装](#安装)
- [快速上手](#快速上手)
- [功能详解](#功能详解)
  - [1. 🎛 可视化提示词面板](#1--可视化提示词面板)
  - [2. 🔞/🧸 SFW 双模式](#2--sfw-双模式一个节点两用)
  - [3. 📖 剧情模式](#3--剧情模式故事线--主角固定--跨图连续)
  - [4. 🧑‍🎤 角色库与立绘](#4--角色库与立绘8000-个角色)
  - [5. 🎲 种子随机 / 固定](#5--种子随机--固定)
  - [6. ⭐ 自定义库](#6--自定义库把我的收藏存下来)
  - [7. 🚫 负面构建器](#7--负面构建器)
  - [8. 🎬 剧情工作流（修复 + 放大 + 保存）](#8--剧情工作流修复--放大--保存)
  - [9. 🧠 调制引导（Modulation Guidance）](#9--调制引导modulation-guidance)
- [四个节点](#四个节点)
- [依赖](#依赖)
- [兼容性](#兼容性)
- [HTTP 接口](#http-接口)
- [常见问题](#常见问题)
- [开发与测试](#开发与测试)
- [致谢与许可](#致谢与许可)

---

## 这是什么

Anima 是个写作习惯很特别的模型：**逗号分隔的英文 booru 标签在前，一段密集的自然语言描述在后**，
顺序还讲究（质量 → 主体 → 外观 → 姿势 → 动作 → 道具 → 体液 → 表情 → 场景 → 风格）。

手写这套东西很痛苦，而且 NSFW 标签又多又散。这个节点包解决三件事：

1. **选标签** —— 浮层面板里点，3782 个可见标签全中文、有分类、有搜索、有互斥约束和强度档位
2. **合成提示词** —— 自动排序 / 去重 / 互斥 / 生成自然语言描述，按 Anima 的语法输出
3. **讲故事** —— 11 条剧情线 / 66 拍，主角跨图固定，一键套用某一拍

再附带一条完整的**出图工作流**（修复手脚崩坏 + 人体崩坏 + 4× 放大 + 保存）。

---

## 核心特性

| | 特性 | 说明 |
|---|---|---|
| 🎛 | **可视化标签面板** | 3782 可见标签全中文、14 分类、搜索、互斥约束、强度档位、实时预览 |
| 🔞🧸 | **SFW / NSFW 双模式** | 一个节点两用。SFW 下自动拦下 257 个露骨词、追加 `rating:safe`、换负面词 |
| 📖 | **剧情模式** | 11 条故事线 × 6 拍，中文台词 + 场景标签，主角跨图固定 |
| 🧑‍🎤 | **角色库** | 8000 个角色 / 826 作品，带**立绘缩略图**，按作品筛选 |
| 📚 | **轻小说分类** | 38 部轻小说（刀剑神域 / 无职转生 / 春物 …），独立互斥组，可与游戏混用 |
| 🎲 | **种子控制** | 固定 / 每次随机 / 递增 / 递减，**直接写进下游 KSampler** |
| ⭐ | **自定义库** | 触发词 / 角色 / 服装 / 姿势存起来下次接着用，可导出 |
| 🚫 | **负面构建器** | 325 字符基线 + 6 段可勾选补丁 |
| 🎬 | **剧情工作流** | 潜空间放大 + 修脸/修手/修人体 + 4× 放大 + 保存，36~42 秒一张 |
| 🧠 | **调制引导** | Anima Modulation Guidance 的 ComfyUI 实现（AdaLN 空间质量引导） |

标签库统计：**11101 条**（含 8000 角色 / 102 游戏作品 / 38 轻小说 / 518 套服装预设 / 297 个姿势参考）。

---

## 安装

### 方式一：解压到 custom_nodes

把 `ComfyUI-Anima-NSFW-Panel` 整个目录放到 `ComfyUI/custom_nodes/` 下。

### 方式二：git clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/<你的用户名>/ComfyUI-Anima-NSFW-Panel.git
```

### 依赖

**没有额外 pip 依赖**（只用 ComfyUI 自带的 torch / numpy / aiohttp）。

想用**剧情工作流**（修手脚崩坏那块）需要额外装节点包：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git
```

并在 `ComfyUI/models/` 下准备：

| 路径 | 文件 | 来源 |
|---|---|---|
| `models/ultralytics/bbox/` | `face_yolov8m.pt` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) |
| `models/ultralytics/bbox/` | `hand_yolov8s.pt` | 同上 |
| `models/ultralytics/segm/` | `person_yolov8m-seg.pt` | 同上 |
| `models/sams/` | `sam_vit_b_01ec64.pth` | [facebook/sam-vit-base](https://huggingface.co/facebook/sam-vit-base) |
| `models/upscale_models/` | `RealESRGAN_x4plus_anime_6B.pth` | [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) |

安装完重启 ComfyUI，画布上双击搜 `AnimaNsfw` 就能看到四个节点。

---

## 快速上手

1. 双击画布 → 搜 `AnimaNsfw` → 添加 **Anima NSFW 提示词面板**
2. 点节点上的 **🎛 打开 NSFW 面板**
3. 左边点分类、中间点标签；右边有负面和预览
4. 点 **应用并关闭** → 节点上的 `tags` 就被写好了
5. 接 `CLIPTextEncode` → `KSampler` 出图

**想直接画一条故事线**：面板顶部 **📖 剧情** → 选故事线 → 选主角 → 点某一拍的
「🎬 套用这一拍」→ Queue。依次套用 #1~#6 就是连续的一卷（种子自动设成递增）。

---

## 功能详解

### 1. 🎛 可视化提示词面板

- **3782 个可见标签**，14 个分类：角色/人数、性爱姿势、前戏服务、自慰单人、服装、
  身体状态、表情神态、体液射精、道具束缚、场景视角、游戏/作品（含轻小说）、画质风格
- **全中文**：非角色标签中文覆盖 **89.8%**（手工校对表 + 本机中文资料 + 逐词词典三层合并）
- **强度档位**：轻柔 / 露骨 / 极限，一键铺底，标签自带 `lvl` 参与过滤
- **互斥约束**：50+ 个互斥组（`1girl`/`1boy`、姿势、场景、体液…），同一组只保留最后一个
- **服装预设 518 套 / 14 组**，带预览图（水手服、女仆装、死库水、和服、铠甲…）
- **姿势参考 297 个 / 8 组**，带预览图
- **实时预览**：面板底部直接显示合成后的正面/负面，改一个标签就刷新
- **缩略图开关**：`🖼 缩略图 开/关`，关掉后纯文字，可完全离线使用

> 预览图和缩略图都走 CDN，**不随包分发**。关掉开关就是纯离线。

### 2. 🔞/🧸 SFW 双模式（一个节点两用）

节点上有 `mode` 下拉，面板右上角也有一键切换按钮。

**为什么不用 rating 分级来判**：分级太粗 —— `school swimsuit`、`black thighhighs`、
`leotard` 都被标成 hard，但它们是正常服装；反过来 `nipples`、`covered nipples`
是 soft，却显然不该出现在 SFW 里。所以用了两层判据：

| 层 | 内容 | 规则 |
|---|---|---|
| 1 | **显式露骨词表 257 条** | 性行为/性器官/体液/束缚/裸露/泳装内衣/情色场景，命中即拦 |
| 2 | **服装白名单 60 条** | 泳装内衣等具体单品：**只有预设自动带进来才豁免** |

第 2 条是关键：选「芭蕾舞服」→ `leotard` 保留；你自己去点 `leotard` → 拦下。
这样 `thighhighs`、`pantyhose`、`corset` 这类正常服装不会被误杀
（早期草稿把它们放黑名单，结果 518 套服装预设里 351 套被误杀）。

SFW 模式下还会：

- 正向自动追加 `rating:safe, safe, general`
- 负面把「NSFW 安全」段换成 `nsfw, explicit, nude, sex, cum, ahegao, bondage, blood, gore…`
- 自然语言描述不写性行为/体液/裸露，收尾换成 all-ages 句式
- 侧栏把 **性爱姿势 / 前戏服务 / 自慰单人 / 体液射精** 四个分类整条收起

### 3. 📖 剧情模式（故事线 + 主角固定 + 跨图连续）

**11 条故事线 / 66 拍**，每条 6 拍，每拍都有中文台词 + 英文台词 + 场景标签：

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
| **青梅竹马** | 日常 / 青春 | 亚丝娜 / 优香 / 白子 |
| **催眠怀表** | 心理 / 暗示 | 达克妮丝 / 高雄 / 宝钟玛琳 |
| **时间停止** | 奇幻 / 时间 | 雷电将军 / 白子 / 惠惠 |

#### 图片连续性怎么保证

靠四件事叠加，缺一不可：

1. **同一个 `char_lock` 主角** —— 每拍都带 `char_lock:<角色名>`，配合互斥组保证
   一次只画一个主角、触发词写法完全一致
2. **同一套立绘标签** —— 每个主角的发色/瞳色/体型写死在 `py/story.py` 的 `CAST` 里
3. **固定服装** —— 以「锁定角色」预设（`[L]`）写进 `outfit_preset`，跨图不换衣服
4. **同一套镜头风格 + 种子成序列** —— 套用时把种子模式自动切成「递增 +1」，
   连点 6 次生成就是一张接一张的连续画面

台词可以直接改：编辑 `py/story.py` 里对应那一拍的 `dialogue`（中文）/ `dialogue_en`（英文）。
想加自己的故事线，照抄一个 dict 改内容即可。

> ⚠️ **台词不会写进提示词**。早期版本把英文台词放进 `caption_text`，
> 结果模型把它当成"要渲染的文字"，在图底部画出一行乱码字幕、角落画出一个假 logo。
> 现在台词只在面板里给你读（点分镜卡片的「复制台词」）。

### 4. 🧑‍🎤 角色库与立绘（8000 个角色）

- **8000 个角色 / 826 个作品**，按热度排序，热度 ≥ 300 的 6412 个默认可见
- **立绘缩略图**：卡片是 3:4 立绘 + 名字 + 作品/热度。图片来自 Animadex 官方 thumbs，
  抽样实测覆盖 **93%**，拿不到图的显示「无图」占位
- **按作品筛选**：侧栏「游戏/作品」是可展开的父项，点作品名先铺开该作品的全部角色
- **搜索**：中文名 / 英文名 / 作品名都能搜
- **分页懒加载**：每个作品先渲染 60 张，往下滚自动加载下一批
- **补齐推荐标签**：选中角色后一键把资料库给该角色标注的发色/瞳色/服装标签一起铺开
- **角色中文名 310 / 8000**（手工校对 231 + 本机中文资料 79）

> 为什么不给剩下 7690 个角色翻中文名：那份本机中文资料里角色词条只有 103 条，
> 逐词翻译对日本人名会出灾难性错误（实测把 `saber alter` 译成"圣诞老人"、
> `koakuma` 译成"小熊"）。我加了黑名单校验，**宁可留罗马音也不给错的中文名**——
> 角色名用罗马音是 Anima 的标准写法，不影响出图。
> 想补：编辑 `py/character_names_zh.py` 加一行，重跑生成脚本。

### 5. 🎲 种子随机 / 固定

面板左侧的 **🎲 种子** 一行，节点上也有对应控件：

| 模式 | 行为 |
|---|---|
| **固定（每次同图）** | 用你填的 seed，采样器锁成 `fixed` —— 调提示词时图不会乱跳 |
| **每次随机** | 每次按「应用」立刻抽一个新 seed 写进去，采样器设为 `randomize` |
| **递增 +1 / 递减 -1** | 每生成一次自动加减 |

**种子是真的写进下游 KSampler 的** —— 面板沿本节点的输出连线往下找采样器
（`KSampler` / `KSamplerAdvanced` / `RandomNoise`，最多 6 层），
**不需要改工作流结构、不用重新连线**。顺带解决了「在界面里点生成会换图、
用 API 提交种子却是死的」这个不一致。

### 6. ⭐ 自定义库（把我的收藏存下来）

四种类型：**触发词 / 角色 / 服装 / 姿势**。

- 「＋ 新建一条」，填名字 + 标签
- 也可以在标签面板里选好标签后点「⭐ 存为角色」
- 持久化到 `custom_nodes/ComfyUI-Anima-NSFW-Panel/custom_library.json`
  （跟着节点包走，重装 ComfyUI 不丢；已加进 `.gitignore`）
- 支持导出 / 导入，方便备份和分享
- 配额：500 条 / 每条 120 标签

### 7. 🚫 负面构建器

- **325 字符基线**（质量 + 人体 + 手部 + 画面）
- **6 段可勾选补丁**：手部修复 / 面部修复 / 人体结构 / NSFW 安全 / 画面干净 / 防伪影
- 逐段说明见节点 tooltip

### 8. 🎬 剧情工作流（修复 + 放大 + 保存）

`workflows/Anima剧情工作流-修复放大保存.json` 拖进 ComfyUI 即用，实测 **36~42 秒/张**：

```
基础采样 1024²（12 步 / CFG 1 / Turbo LoRA）
→ 潜空间放大 1.5× → 二次采样 1536²（denoise 0.45）
→ 修脸    FaceDetailer + face_yolov8m      + SAM
→ 修手    FaceDetailer + hand_yolov8s      + SAM   ← 治手脚崩坏
→ 修人体  FaceDetailer + person_yolov8m-seg + SAM  ← 治人体结构崩坏
→ 4× anime 放大（1152 → 4608）→ 缩到 2534²
→ 保存到 output/AnimaStory/
→ ImageGridComposite2x2 四格拼图
```

三个修复步骤的参数是**按问题类型分别调的**，不是复制粘贴：

| 步骤 | denoise | 关键调整 | 为什么 |
|---|---|---|---|
| 修脸 | 0.45 | guide 512 | 脸最容易被看出来 |
| 修手 | **0.5** | `bbox_threshold 0.4` / dilation 12 / guide 384 | 手崩得狠要敢重画；阈值放低让模糊的手也能检出 |
| 修人体 | **0.35** | guide 768 / max 1536 / crop 2.0 | **低 denoise 才能纠正结构而不重画角色** |

逐环节说明、调参建议、8 条常见问题见
[`workflows/Anima剧情工作流-说明.md`](workflows/Anima剧情工作流-说明.md)。

### 9. 🧠 调制引导（Modulation Guidance）

Anima **Modulation Guidance** 的 ComfyUI 实现 —— 在 AdaLN 空间做质量引导。

- `pooled_text_proj` 是个 MLP：`Linear(1024→2048) → SiLU → Linear(2048→2048)`
- `delta_unit = proj(quality_pos) − proj(quality_neg)`
- 基础投影从 `max_pool(crossattn_emb)` 取，加在 `t_embedding_norm` 上
- 每个 block 的 pre-hook 加 `w(ℓ)·delta_unit`，用 `WrappersMP.APPLY_MODEL` 包装

**⚠️ 默认关（`enabled = False`）**。开了画面更"精致"但可能偏色 —— A/B 实测：
同种子开/关像素差 mean=47.58（确实生效），但 w=3 会把粉色占比从 0.01 拉到 0.17。
所以默认档位是 `light_w1.5`。

### 10. ⚡ 性能

v1.9.4 修掉了一次严重的性能退化。用真实数据量（11097 标签 / 8000 角色）离线基准
量出来的数字：

| 操作 | 修前 | 修后 | 倍数 |
|---|---|---|---|
| 开面板建 DOM | **110315** | **1981** | **56×** |
| 开面板写 style | **625184** | **2068** | **302×** |
| 点标签建 DOM | 115 | **3** | **38×** |
| 连点 5 标签的预览请求 | 5 次 | **1 次** | 5× |

**原因**：`renderGrid()` 里的 `list.slice(0, CARD_LIMIT)` 在某次恢复文件时丢了，
循环变成遍历全部 11097 个标签，每个建 3 个 DOM 节点 —— 十万节点 + 六十二万次
样式写入，全同步执行。

**优化点**：恢复分页、`el()` 改用 `cssText` 批量写样式、点标签只重画受影响的卡片、
预览请求防抖、作品→角色索引、角色库延迟预取、搜索防抖。

详细分析和排查指引见 [`workflows/性能说明.md`](workflows/性能说明.md)。


---

## 四个节点

| 节点 | 显示名 | 作用 |
|---|---|---|
| `AnimaNsfwPromptBuilder` | Anima NSFW 提示词面板 | 主节点。可视化选标签 → 合成正面提示词 + 调试 JSON |
| `AnimaNsfwNegativeBuilder` | Anima 负面构建器 | 基线 + 6 段可勾选补丁 |
| `AnimaNsfwModGuidance` | Anima 调制引导 | MODEL → MODEL 补丁（AdaLN 空间质量引导） |
| `AnimaNsfwCaptionOnly` | Anima 仅描述 | 只要自然语言描述，不要标签 |

`AnimaNsfwPromptBuilder` 的三路输出：

| 输出 | 内容 |
|---|---|
| `positive` | 合成好的正面提示词 |
| `info` | 本次合成的调试信息（JSON：标签、被移除项、描述…） |
| `story_info` | 剧情元数据（故事线 / 这一拍 / 台词，JSON） |

---

## 依赖

| 项目 | 要求 |
|---|---|
| ComfyUI | 前端 **≥ 1.12.8**（实测 1.12.8 ~ 1.53.10） |
| Python | 3.10+ |
| 额外 pip 包 | **无** |
| ComfyUI-Impact-Pack | 只在用**剧情工作流**时需要 |
| 模型 | Anima Base + Turbo LoRA（示例参数按 12 步 / CFG 1 调的） |

---

## 兼容性

**面板从 ComfyUI 前端 1.12.8 起可用。**

我为老前端补了三处防线：

1. **`addDOMWidget` 老前端只吃 3 个参数**（`name, type, element`），第 4 个 config 被忽略
   → 缺失或抛异常时**自动退回画布绘制预览**，不会把 `setupBuilder` 打断
2. **`widget.options` 可能不存在**（1.12.x 的 `addWidget` 不一定带）→
   5 处访问全部有 `|| {}` 前置
3. **`graph.links[id]` 字段名**老前端用 `target`、新的用 `target_id`；`getNodeById`
   可能没有 → 两种都认，并退回 `graph._nodes_by_id`

更早的版本（内置前端的 1.3.x ~ 1.11.x）不在 PyPI 上，**没有实测过**。
完整分析见 [`workflows/低版本兼容说明.md`](workflows/低版本兼容说明.md)。

> ⚠️ 如果 `mode` / `seed_mode` 这类新增输入让**老工作流加载失败**：
> 它们都在 `optional` 里（带默认值），正常情况下老工作流能直接打开。
> 如果不行，删掉节点重新添加一个。

---

## HTTP 接口

节点包注册了几个接口，前端面板和外部脚本都能用：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/anima_nsfw/tags` | 完整标签库 + 分类 + 预设 + 剧情统计（约 1.5 MB） |
| GET | `/anima_nsfw/characters` | 角色库（8000 角色 / 826 作品） |
| GET | `/anima_nsfw/story` | 剧情库（11 条故事线 + 可选主角） |
| GET | `/anima_nsfw/story/scene` | 展开某一拍：`?arc=&scene=&cast=` |
| GET | `/anima_nsfw/status` | 调制引导适配器与档位 |
| POST | `/anima_nsfw/preview` | 预览合成结果（面板实时预览走这里） |
| GET/POST | `/anima_nsfw/custom` `/save` `/delete` `/import` `/export` | 自定义库 |

---

## 常见问题

<details>
<summary><b>点「打开面板」没反应 / 节点上没有按钮</b></summary>

按顺序查：

1. **Ctrl+F5 硬刷新**（浏览器缓存最常见）
2. F12 看控制台有没有 `[AnimaNSFW]` 开头的报错
3. 服务端日志里本包有没有 `IMPORT FAILED`
4. `curl http://127.0.0.1:8188/anima_nsfw/tags` 有没有返回 JSON
   （拿不到 = 后端/端口问题，跟前端版本无关）
5. `curl http://127.0.0.1:8188/extensions/ComfyUI-Anima-NSFW-Panel/anima_nsfw_panel.js`
   有没有返回 JS（拿不到 = 静态资源路径问题）
6. 都正常才怀疑前端版本

</details>

<details>
<summary><b>报「缺少必需的输入: tags」</b></summary>

v1.5.2 之前版本的 bug（面板把 widget 的 `type` 改成 `hidden`，ComfyUI 生成 prompt
时会跳过它）。升级即可。如果 `tags` 真的是空的，后端会给出中文提示告诉你去面板选标签。

</details>

<details>
<summary><b>套用剧情后图是全黑的</b></summary>

v1.9.2 之前版本的 bug：`char_lock:` 含下划线，被规范化成 `char lock:`，
锁前缀失效、垃圾文本进了提示词 → 整张全黑。升级即可。

</details>

<details>
<summary><b>图上出现字幕 / 假 logo / 乱码文字</b></summary>

**不要把台词放进 `caption_text`** —— 它会被拼进正面提示词，模型当成"要渲染的文字"。
面板从 v1.9.2 起套用剧情时不再自动填它。

背景物体（纸箱、书脊）上长出伪文字是 4× 放大模型的特性，
把负面构建器的 **画面干净** 勾上（里面有一长串
`text / watermark / signature / english text / chinese text`）。

</details>

<details>
<summary><b>手还是崩 / 放大后脸变糊</b></summary>

- **手崩**：把修手那步的 `denoise` 提到 0.6、`cycle` 改成 2（重画两轮）
- **脸糊**：① 把修脸挪到放大之后；② `scale_by` 降到 0.35；
  ③ 换 `4x-ClearRealityV1_Soft.pth`（更柔和但文件更大）

</details>

<details>
<summary><b>太慢</b></summary>

按收益排序砍：① 关掉修人体（省 ~8s）；② 二次采样 steps 8→6；
③ `max_size` 2048→1536；④ 基础分辨率 1024→768。

</details>

<details>
<summary><b>角色没有中文名</b></summary>

8000 个角色里只有 310 个有中文名。原因见上面「角色库」一节 ——
逐词翻译对日本人名会出灾难性错误，所以宁可留罗马音。
想补：编辑 `py/character_names_zh.py` 加一行 `"英文名": "中文名"`，重跑生成脚本。

</details>

---

## 开发与测试

仓库带三套离线测试，**都不需要启动 ComfyUI、不联网**（fetch 全走桩）：

```bash
# 面板 JS 冒烟测试：模块加载 → 注册扩展 → onNodeCreated → 点按钮 →
# 面板浮层 → 点每个按钮/分类 → 画布回调 → 种子推送 → 剧情套用 → 立绘
node tools/animansfw_panel_smoke.mjs            # 现代前端
node tools/animansfw_panel_smoke.mjs --legacy   # 剥掉 addDOMWidget 等
node tools/animansfw_panel_smoke.mjs --oldfe    # 老前端契约（1.12.8）

# SFW 双模式自测（40 项）
python tools/animansfw_sfw_selftest.py

# 性能基准（看 DOM 节点数 / 样式写入次数有没有退化）
node tools/animansfw_perf.mjs
```

三种模式都必须全绿。剧情全库体检遍历 11 线 × 6 拍 × 全部主角，
确认**没有重复标签、没有引号、每拍都带 `char_lock`、每拍都有台词、
数量锚点恰好一组**。

<details>
<summary>开发中踩过的坑（留作记录）</summary>

- `hideWidget` **绝不能**把 `widget.type` 改成 `"hidden"` —— ComfyUI 生成 prompt
  时会跳过它，报「缺少必需的输入」
- 新增节点输入要放 `optional` 且给默认值，否则**老工作流加载失败** ——
  ComfyUI 的校验顺序是 `INPUT_TYPES` → `build()`，`build()` 里加默认值救不了
- `"nsfw"` 里**包含** `"sfw"` 子串，不能用 `"sfw" in mode` 判断模式
- `char_lock:` 含下划线，会被 `normalize_token` 改成 `char lock:` → 锁失效 + 全黑
- 台词进正面提示词 → 被当成字幕画出来
- 官方「单人/多人」是**同一个互斥组**，`solo` 会把 `1boy` 顶掉 →
  双人镜头没有男性锚点，模型就复制一个主角（画成双胞胎）
- 模块顶层只能调模块级函数：`loadChars` 定义在 `buildPanel` 里，
  在模块作用域调用会抛 `ReferenceError` → 整个扩展注册失败

</details>

---

## 致谢与许可

- **MIT License** —— 见 [LICENSE](LICENSE)
- 预设素材参考自 [nregret/Dressing-doll](https://github.com/nregret/Dressing-doll)
  与 [AnimaTags-DB](https://github.com/nregret/AnimaTags-DB)（服装 / 姿势标签与预览图）
- 角色资料来自本机 `Comfyui-Anima-Tools`
- 角色立绘缩略图来自 Animadex 官方 CDN（**不随包分发**）
- 调制引导参考 Anima 官方 Modulation Guidance 实现

**内容声明**：本仓库只有**代码、标签数据和文字剧情台本**，
不含任何 NSFW 图片，也没有抓取或打包任何图库。
面板里的缩略图是可关闭的在线资源。

---

<p align="center">
  <sub>仅供成年人使用 · 请遵守你所在地区的法律与 GitHub 的服务条款</sub>
</p>
