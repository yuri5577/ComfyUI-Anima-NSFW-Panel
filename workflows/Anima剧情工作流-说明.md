# Anima 剧情工作流（修复 + 放大 + 保存）

配套 **ComfyUI-Anima-NSFW-Panel v1.9.2** 使用。文件两个：

| 文件 | 用途 |
|---|---|
| `Anima剧情工作流-修复放大保存.json` | **UI 格式** —— ComfyUI 里直接拖进去 / 工作流菜单里打开 |
| `Anima剧情工作流-修复放大保存.API.json` | **API 格式** —— 脚本调用（`/prompt`）用 |

---

## 一句话流程

```
加载模型 → 🎬 剧情面板选一拍 → 基础采样 1024²
→ 潜空间放大 1.5× → 二次采样 1536²（denoise 0.45）
→ 修脸 → 修手（手脚崩坏）→ 修人体（结构崩坏）
→ 4× anime 放大 → 缩到 2534² → 存到 output/AnimaStory/
→ 四格拼图（可选）
```

27 个节点 / 51 条连线。实测一张 **约 36~42 秒**（1024 基础 + 1536 高清 + 三次修复 + 4× 放大）。

---

## 怎么用

1. 打开这个工作流
2. 找到蓝色标题的 **「🎬 剧情面板」** 节点，点上面的 **🎛 打开 NSFW 面板**
3. 面板顶部点 **📖 剧情** → 选故事线 → 选主角 → 点某一拍的「🎬 套用这一拍」
4. 面板会自动写好这一拍的标签 / 服装 / 种子（递增），回标签视图
5. 点 ComfyUI 的 **Queue** 出图
6. 出图落在 `ComfyUI/output/AnimaStory/`

想一次画完整一卷：依次套用 #1 ~ #6，种子保持「递增 +1」，就是连续的一条序列。

---

## 每个环节在干什么（以及为什么这么设）

### ① 基础采样 1024² / 12 步 / CFG 1.0
配合 **Turbo LoRA**。`er_sde` + `simple` 是 Anima 常用的组合。

### ② 高清修复：潜空间放大 1.5× + 二次采样 denoise 0.45
**denoise 低是关键** —— 只补细节、不改构图。denoise 超过 0.6 会把人物和姿势都重画一遍，
连续性就断了。放大方法用 `bislerp`（比 nearest 平滑，比 lanczos 少振铃）。

### ③ 修脸（FaceDetailer + face_yolov8m + SAM）
`guide_size 512` / `denoise 0.45`。脸是最容易被看出来的地方，单独重画一遍。

### ④ 修手（FaceDetailer + **hand_yolov8s** + SAM）—— 治「手脚崩坏」
注意：FaceDetailer 这个节点名虽然叫 face，但它接受任意检测器。
把 `bbox_detector` 换成手部模型，它就变成手部修复器。

参数比修脸更激进：
- `denoise 0.5`（手崩得比较狠，要敢重画）
- `bbox_threshold 0.4`（手模糊、畸变也要能检出来）
- `bbox_dilation 12` / `feather 6`（边界糊得开一点，不然接缝明显）
- `guide_size 384`（手需要的分辨率比脸低，省时间）

### ⑤ 修人体（FaceDetailer + **person_yolov8m-seg** 分割 + SAM）—— 治「人体结构崩坏」
用**分割**模型拿到整个人形轮廓，然后：
- `denoise` **只有 0.35** —— 这是刻意的：结构性问题（多条腿、脖子过长、
  四肢粘连）要在低 denoise 下纠正，高了就变成重画角色，连续性没了
- `guide_size 768` / `max_size 1536` —— 全身需要更大画布
- `bbox_crop_factor 2.0`（全身不用裁太宽）

### ⑥ 4× 放大 + 缩放
`RealESRGAN_x4plus_anime_6B` 是动漫专用放大模型。
**实测倍率**：1152 输入 → **4608 输出**（真的是 4×）。
最后 `ImageScaleBy 0.55` 缩到约 **2534×2534**（约 3.8 MB）。

> 想要原尺寸就把 `scale_by` 改成 `1.0`（4608²，约 13 MB）；
> 想更小改成 `0.35`（1613²，约 2.2 MB）。

### ⑦ 保存
`filename_prefix = AnimaStory/story` → 落在 `ComfyUI/output/AnimaStory/story_00001_.png` 等。

### ⑧ 四格拼图（ImageGridComposite2x2）
默认四个输入都指向同一张（占位）。画完 4 拍以后，
把另外 3 张的 SaveImage 输出接到 `image2/3/4`，就能拼成一页分镜。

---

## 常见问题

**Q：图偏暗 / 发黑？**
A：这个工作流本身实测亮度 0.28~0.45（正常）。如果整张纯黑，先检查是不是
把「台词」写进了正面提示词 —— 见下一条。另外 `shift=3.0` 是 Anima 的常用值，
调到 1.0 会亮一些但结构会松。

**Q：图上出现字幕 / 假 logo / 乱码文字？**
A：**不要把台词放进 `caption_text`**。面板从 v1.9.2 起套用剧情时不再自动填它 ——
因为英文台词（"Ten years, and you got so tall."）会被模型当成「要渲染的文字」，
在底部画出乱码字幕、角落画出一个假 logo。台词只在面板里给你读，
要用的话点分镜卡片上的「复制台词」。

如果背景物体（纸箱、书脊）上还是长出伪文字：这是 4× 放大模型的特性，
把「🚫 负面构建器」的 **画面干净** 勾上（已经默认勾了，里面有一长串
`text / watermark / signature / username / logo / english text / chinese text`）。

**Q：放大后脸变糊 / 变对称呆滞？**
A：4× 动漫放大模型对脸的还原有限。两个办法：
① 把修脸那一步挪到放大之后（现在是之前）；
② 把 `scale_by` 降到 0.35，或换 `4x-ClearRealityV1_Soft.pth`（更柔和但文件更大）。

**Q：手还是崩？**
A：把修手那一步的 `denoise` 提到 0.6、`cycle` 改成 2（重画两轮）。
代价是可能改变手部姿势。

**Q：太慢？**
A：按收益排序砍：
1. 关掉修人体（省 ~8s）—— 结构性崩坏不是每张都有
2. 二次采样的 steps 从 8 降到 6
3. `max_size` 2048 → 1536
4. 基础分辨率 1024 → 768

**Q：调制引导（Modulation Guidance）要不要开？**
A：默认**关**（`enabled = False`）。开了画面更「精致」但可能偏色，
先看 v1.9.0 那段说明再决定。

---

## 依赖

| 类型 | 需要的东西 |
|---|---|
| 模型 | `anima_baseV10.safetensors` / `qwen_3_06b_base.safetensors` / `qwen_image_vae.safetensors` |
| LoRA | `Anima lora/anima-turbo-lora-v0.2.safetensors` |
| 放大 | `RealESRGAN_x4plus_anime_6B.pth`（或 `4x-ClearRealityV1_Soft.pth`） |
| 检测 | `bbox/face_yolov8m.pt` / `bbox/hand_yolov8s.pt` / `segm/person_yolov8m-seg.pt` |
| 分割 | `sam_vit_b_01ec64.pth` |
| 节点包 | **ComfyUI-Impact-Pack**（FaceDetailer / UltralyticsDetectorProvider / SAMLoader） |
| 本包 | ComfyUI-Anima-NSFW-Panel **≥ v1.9.2** |

三个检测模型和 SAM 都放在 `ComfyUI/models/ultralytics/` 与 `ComfyUI/models/sams/`。
