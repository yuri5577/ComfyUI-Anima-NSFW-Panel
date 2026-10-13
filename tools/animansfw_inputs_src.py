# -*- coding: utf-8 -*-
"""两个节点的 INPUT_TYPES 源码片段（供 animansfw_rewrite_inputs.py 使用）。

mode 放在 optional（带 default）—— v1.6.0 之前保存的老工作流没有这个输入，
放进 required 会直接 400 required_input_missing，用户表现为「老工作流打不开」。
"""

POS = '''    @classmethod
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
                "upstream_prompt": ("STRING", {"forceInput": True}),
            },
        }

'''

NEG = '''    @classmethod
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

'''
