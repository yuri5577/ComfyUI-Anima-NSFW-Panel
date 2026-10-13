# -*- coding: utf-8 -*-
"""节点定义：Anima NSFW 提示词面板 + 负面构建 + 调制引导 + 纯描述生成。"""

from __future__ import annotations

from typing import List

from . import mod_guidance as mg
from .prompt_builder import build_caption, compose_negative, compose_prompt
from .sfw import MODE_NSFW, MODE_SFW, MODES as SFW_MODES
from .tags import QUALITY_PRESETS

QUALITY_CHOICES = list(QUALITY_PRESETS.keys())
INTENSITY_CHOICES = ["soft", "hard", "extreme"]

CATEGORY = "Anima/NSFW"

SEED_MAX = 0xFFFFFFFFFFFFFFFF

# 种子模式。除了「固定」，其余都通过设置下游 KSampler 的
# control_after_generate 实现，所以生成的图会跟着变。
SEED_MODE_FIXED = "固定（每次同图）"
SEED_MODE_RANDOM = "每次随机"
SEED_MODE_INCREMENT = "递增 +1"
SEED_MODE_DECREMENT = "递减 -1"
SEED_MODES = (SEED_MODE_FIXED, SEED_MODE_RANDOM, SEED_MODE_INCREMENT, SEED_MODE_DECREMENT)

# 传给 ComfyUI 前端的 control_after_generate 取值
SEED_CONTROL = {
    SEED_MODE_FIXED: "fixed",
    SEED_MODE_RANDOM: "randomize",
    SEED_MODE_INCREMENT: "increment",
    SEED_MODE_DECREMENT: "decrement",
}

# 服装预设的序列化格式： "预设名[L],,tag1, tag2, tag3"
#   * ",," 分隔预设名与标签
#   * 预设名后缀 "[L]" 表示这条预设锁定角色（互斥，一次只能锁一个）
PRESET_SEP = ",,"
LOCK_MARK = "[L]"


def encode_outfit_preset(name: str, tags, locked: bool = False) -> str:
    head = f"{name}{LOCK_MARK}" if locked else str(name)
    return f"{head}{PRESET_SEP}{', '.join(tags)}"


def decode_outfit_preset(raw) -> dict:
    """把面板写入的服装预设字符串还原成 dict；空串返回空 dict。"""
    text = str(raw or "").strip()
    if not text:
        return {}
    if PRESET_SEP in text:
        name, _, rest = text.partition(PRESET_SEP)
    else:
        name, rest = "", text
    name = name.strip()
    locked = name.endswith(LOCK_MARK)
    if locked:
        name = name[: -len(LOCK_MARK)].strip()
    else:
        # 兼容：名字里带「锁定」字样也视为锁定角色
        locked = "锁定" in name
    tags = [t.strip() for t in rest.split(",") if t.strip()]
    return {"zh": name, "tags": tags, "lock": locked}


def outfit_presets_for_ui() -> list:
    """给前端用的服装预设列表（含锁定标记与预览图）。"""
    from .tags import outfit_presets_as_list

    return outfit_presets_as_list()


def pose_presets_for_ui() -> list:
    """给前端用的姿势参考预设列表（含预览图）。"""
    from .tags import pose_presets_as_list

    return pose_presets_as_list()


# ---------------------------------------------------------------------------
# 1. 提示词构建器
# ---------------------------------------------------------------------------

class AnimaNsfwPromptBuilder:
    """可视化 NSFW 提示词构建器。

    ``tags`` 是隐藏控件，由前端 JS 面板写入（也可直接用其它节点的字符串输入）。
    输出为符合 Anima 习惯的「英文标签 + 自然语言描述」。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tags": ("STRING", {
                    "multiline": True,
                    "default": "1girl, solo, large breasts, blush, looking at viewer",
                    "tooltip": "选中标签（逗号分隔）。点节点上的「🎛 打开 NSFW 面板」可视化选择。",
                }),
                "intensity": (INTENSITY_CHOICES, {"default": "hard"}),
                "quality_preset": (QUALITY_CHOICES, {"default": QUALITY_CHOICES[1]}),
                "caption_enabled": ("BOOLEAN", {"default": True,
                                                 "label_on": "生成描述", "label_off": "不生成"}),
                "caption_seed": ("INT", {"default": 0, "min": 0, "max": SEED_MAX}),
                "sort_tags": ("BOOLEAN", {"default": True,
                                          "label_on": "按 Anima 顺序",
                                          "label_off": "保持选择顺序"}),
                "dedupe_tags": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                # mode 必须在 optional 里：v1.6.0 之前保存的工作流没有这个输入，
                # 放进 required 会直接 400 required_input_missing（老工作流打不开）。
                "mode": (list(SFW_MODES), {
                    "default": MODE_NSFW,
                    "tooltip": "SFW（全年龄）：自动拦下性行为/裸露/体液/束缚/泳装内衣等标签，"
                               "正向追加 rating:safe, safe, general，负面换成全年龄向安全词，"
                               "自然语言描述也不写身体局部。NSFW（不限）：不做这些过滤，"
                               "按你选的标签原样输出。同一个节点就能两用。",
                }),
                "outfit_preset": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "服装预设（由面板写入，格式：预设名,,标签1, 标签2）。"
                               "手改这里也能直接生效；名字后缀 [L] 表示锁定角色。",
                }),
                "pose_preset": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "姿势参考预设（由面板写入，格式同 outfit_preset）。"
                               "姿势词会排在身体之后、性交动作之前。",
                }),
                "caption_text": ("STRING", {"multiline": True, "default": "",
                                            "tooltip": "留空则自动生成自然语言描述"}),
                "extra_front": ("STRING", {"multiline": True, "default": "",
                                           "tooltip": "插在质量词之后、标签之前"}),
                "extra_tail": ("STRING", {"multiline": True, "default": "",
                                          "tooltip": "追加在提示词最后"}),
                # ---- 种子控制（面板上也有同样的控件，两边同步）----
                "seed_mode": (list(SEED_MODES), {
                    "default": SEED_MODE_FIXED,
                    "tooltip": "固定（每次同图）：用下面的 seed，并把下游采样器设为 fixed。\n"
                               "每次随机：每次按「应用」都抽一个新 seed，并把下游采样器设为"
                               " randomize（连点生成会一直换图）。\n"
                               "递增 +1 / 递减 -1：每生成一次自动加减。",
                }),
                "seed": ("INT", {
                    "default": 1234, "min": 0, "max": SEED_MAX,
                    "tooltip": "种子数值。选「每次随机」时这里是上次抽到的值，"
                               "应用面板时会自动换新。",
                }),
                "upstream_prompt": ("STRING", {"forceInput": True}),
            },
        }


    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "info", "story_info")
    OUTPUT_TOOLTIPS = ("可直接接 CLIPTextEncode 的正面提示词", "本次合成的调试信息（JSON）")
    FUNCTION = "build"
    CATEGORY = CATEGORY
    DESCRIPTION = "Anima 专用 NSFW 提示词构建器：可视化选标签 → 自动排序 / 互斥 / 生成自然语言描述。"

    def build(self, tags, mode=MODE_NSFW, intensity="hard",
              quality_preset="base（原版 28~32 步）", caption_enabled=True,
              caption_seed=0, sort_tags=True, dedupe_tags=True,
              outfit_preset="", pose_preset="", caption_text="",
              extra_front="", extra_tail="", upstream_prompt="",
              seed_mode=SEED_MODE_FIXED, seed=1234):
        # mode 等都给默认值：老工作流（v1.6.0 之前保存的）里没有 mode 这个输入，
        # 不给默认值的话一加载就报「缺少必需的输入」。
        if (not str(tags or "").strip() and not str(outfit_preset or "").strip()
                and not str(pose_preset or "").strip()):
            raise ValueError(
                "Anima NSFW 提示词面板：tags 为空。\n"
                "请点节点上的「🎛 打开 NSFW 面板」选标签（或套一个服装/姿势预设）后按「应用并关闭」；\n"
                "也可以直接把标签（英文、逗号分隔）粘到连接的字符串节点里。"
            )
        preset = decode_outfit_preset(outfit_preset)
        pose = decode_outfit_preset(pose_preset)
        result = compose_prompt(
            tags=tags,
            intensity=intensity,
            quality_preset=QUALITY_PRESETS.get(quality_preset, ""),
            extra_front=extra_front,
            extra_tail=extra_tail,
            caption_enabled=caption_enabled,
            caption_seed=caption_seed,
            caption_text=caption_text,
            sort_tags=sort_tags,
            dedupe_tags=dedupe_tags,
            upstream_prompt=upstream_prompt,
            outfit_preset=preset,
            pose_preset=pose,
            mode=mode,
        )
        info = result["info"]
        import json

        payload = {
            "positive": result["prompt"],
            "tags": info.get("tags", []),
            "tag_count": info.get("tag_count", 0),
            "caption": info.get("caption", ""),
            "outfit_preset": info.get("outfit_preset", ""),
            "pose_preset": info.get("pose_preset", ""),
            "mode": info.get("mode", "nsfw"),
            "seed_mode": seed_mode,
            "seed": int(seed),
            "seed_control": SEED_CONTROL.get(seed_mode, "fixed"),
            "dropped": {
                "intensity": info.get("dropped_by_intensity", []),
                "group": info.get("dropped_by_group", []),
                "sfw": info.get("dropped_by_sfw", []),
            },
        }
        return {
            "ui": {"animansfw_preview": [payload]},
            # 第三路：剧情/台词等元数据（**不要接回提示词**，
            # 台词一旦进正面提示词，模型会把它当字幕画出来 —— 实测踩过）
            "result": (result["prompt"],
                       json.dumps(info, ensure_ascii=False, indent=2),
                       json.dumps(payload, ensure_ascii=False, indent=2)),
        }


# ---------------------------------------------------------------------------
# 2. 负面提示词构建器
# ---------------------------------------------------------------------------

class AnimaNsfwNegativeBuilder:
    """按需拼接 Anima 常用负面提示词（含 NSFW 安全项）。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_enabled": ("BOOLEAN", {"default": True,
                                             "label_on": "使用基础负面",
                                             "label_off": "只用自定义"}),
                "手部修复": ("BOOLEAN", {"default": True}),
                "面部修复": ("BOOLEAN", {"default": True}),
                "人体结构": ("BOOLEAN", {"default": False}),
                "NSFW安全": ("BOOLEAN", {"default": False,
                                         "tooltip": "加入 child/underage/loli 等安全词，"
                                                    "仅用于避免误出未成年内容"}),
                "画面干净": ("BOOLEAN", {"default": False}),
                "防伪影": ("BOOLEAN", {"default": False}),
                "extra_text": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                # 同提示词面板：optional + default，兼容 v1.6.0 之前的老工作流
                "mode": (list(SFW_MODES), {
                    "default": MODE_NSFW,
                    "tooltip": "SFW（全年龄）：把「NSFW 安全」段换成全年龄向反向词"
                               "（nsfw, explicit, nude, sex, cum, ahegao, bondage…），"
                               "并额外追加一段，确保安全级。NSFW（不限）：保持原有负面词。",
                }),
                "upstream_negative": ("STRING", {"forceInput": True}),
            },
        }


    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("negative",)
    FUNCTION = "build"
    CATEGORY = CATEGORY
    DESCRIPTION = "Anima 负面提示词构建器：基础负面 + 可勾选补丁段（手部/面部/人体/NSFW 安全/防伪影）。"

    def build(self, base_enabled=True, mode=MODE_NSFW, 手部修复=True, 面部修复=True,
              人体结构=False, NSFW安全=False, 画面干净=False, 防伪影=False,
              extra_text="", upstream_negative=""):
        # 同上：base_enabled / mode 给默认值，兼容老工作流
        picked = []
        segment_flags = (
            ("手部修复", 手部修复),
            ("面部修复", 面部修复),
            ("人体结构", 人体结构),
            ("NSFW 安全", NSFW安全),
            ("画面干净", 画面干净),
            ("防伪影", 防伪影),
        )
        for name, on in segment_flags:
            if on:
                picked.append(name)
        result = compose_negative(
            base_enabled=base_enabled,
            extras=picked,
            extra_text=extra_text,
            upstream_negative=upstream_negative,
            mode=mode,
        )
        return (result["prompt"],)


# ---------------------------------------------------------------------------
# 3. Modulation Guidance
# ---------------------------------------------------------------------------

class AnimaNsfwModGuidance:
    """Anima 调制引导（AdaLN 空间的质量引导），MODEL → MODEL 补丁。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "adapter": (mg.list_adapters(), {"default": mg.DEFAULT_ADAPTER_FILENAME}),
                "profile": (list(mg.PROFILES.keys()), {"default": list(mg.PROFILES.keys())[0]}),
                "quality_tags": ("STRING", {"multiline": False, "default": mg.DEFAULT_QUALITY_TAGS}),
                "quality_neg": ("STRING", {"multiline": False, "default": mg.DEFAULT_QUALITY_NEG}),
                "base_prompt": ("STRING", {
                    "multiline": True,
                    "default": mg.DEFAULT_BASE_PROMPT,
                    "tooltip": "调制路径的文本特征。建议直接抄一份正面提示词开头\n"
                               "（角色 + 站姿/场景 + 质量词即可），越接近主提示词越稳。\n"
                               "改动后重跑一次；若画面发灰/发粉，把 profile 调成 light。",
                }),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "w": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 20.0, "step": 0.1,
                                "tooltip": "引导强度；profile 选「自定义」时才生效"}),
                "start_layer": ("INT", {"default": 8, "min": 0, "max": 128}),
                "end_layer": ("INT", {"default": 27, "min": -1, "max": 128}),
                "taper": ("INT", {"default": 0, "min": 0, "max": 32}),
                "taper_scale": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05}),
                "final_w": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 10.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("MODEL", "STRING")
    RETURN_NAMES = ("MODEL", "状态")
    FUNCTION = "apply"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Anima Modulation Guidance：在 AdaLN 调制空间沿质量正/负方向引导，"
                   "与 CFG 正交可叠加。需要 pooled_text_proj 适配器。")

    def apply(self, model, clip, adapter, profile, quality_tags, quality_neg, base_prompt,
              enabled, w=3.0, start_layer=8, end_layer=27, taper=0, taper_scale=0.25, final_w=0.0):
        if not enabled:
            return (model, "调制引导: 已关闭")

        pw, ps, pe, pt, pts, pf = mg.PROFILES.get(profile, (w, start_layer, end_layer, taper,
                                                            taper_scale, final_w))
        if profile != "自定义":
            w, start_layer, end_layer, taper, taper_scale, final_w = pw, ps, pe, pt, pts, pf

        patched, state = mg.apply_mod_guidance(
            model=model,
            clip=clip,
            adapter_name=adapter,
            quality_tags=quality_tags,
            quality_neg=quality_neg,
            base_prompt=base_prompt,
            w=w,
            start_layer=start_layer,
            end_layer=end_layer,
            taper=taper,
            taper_scale=taper_scale,
            final_w=final_w,
        )
        status = (f"调制引导: {profile} | w={w} | blocks=[{start_layer}, {end_layer}) | "
                  f"final_w={final_w} | adapter={adapter}")
        return (patched, status)


# ---------------------------------------------------------------------------
# 4. 纯描述生成
# ---------------------------------------------------------------------------

class AnimaNsfwCaptionOnly:
    """只生成自然语言描述（用于已有标签、需要补一段 Anima 风格描述的场合）。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tags": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": SEED_MAX,
                    "tooltip": "描述变体种子。同一个 seed + 同一组标签 = 同一段描述文字。",
                }),
            },
            "optional": {
                "prefix": ("STRING", {"multiline": True, "default": "",
                                      "tooltip": "拼在描述前面的标签串"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    CATEGORY = CATEGORY
    DESCRIPTION = "从标签生成一段 Anima 风格自然语言描述（无需 LLM，模板化）。"

    def run(self, tags, seed, prefix=""):
        from .prompt_builder import split_tokens

        tokens = split_tokens(tags)
        caption = build_caption(tokens, seed=seed)
        text = ", ".join([t for t in [prefix.strip(), caption] if t])
        return (text,)


NODE_CLASS_MAPPINGS = {
    "AnimaNsfwPromptBuilder": AnimaNsfwPromptBuilder,
    "AnimaNsfwNegativeBuilder": AnimaNsfwNegativeBuilder,
    "AnimaNsfwModGuidance": AnimaNsfwModGuidance,
    "AnimaNsfwCaptionOnly": AnimaNsfwCaptionOnly,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaNsfwPromptBuilder": "Anima NSFW 提示词面板",
    "AnimaNsfwNegativeBuilder": "Anima NSFW 负面构建器",
    "AnimaNsfwModGuidance": "Anima 调制引导 (Mod Guidance)",
    "AnimaNsfwCaptionOnly": "Anima NSFW 描述生成",
}
