# -*- coding: utf-8 -*-
"""ComfyUI-Anima-NSFW-Panel — Anima 专用的 NSFW 提示词 / 调制引导节点包。

面向 circlestone-labs 的 Anima Base（Qwen3 + T5XXL 文本编码器，28 层 DiT）
写作习惯：前置逗号分隔的英文 booru 标签 + 后置一段自然语言描述。

包含：
  * AnimaNsfwPromptBuilder    可视化 NSFW 提示词构建器（前端弹窗选标签）
  * AnimaNsfwNegativeBuilder  NSFW 安全向负面提示词构建器
  * AnimaNsfwModGuidance      Anima Modulation Guidance（模型补丁，AdaLN 引导）
  * AnimaNsfwCaptionOnly      仅生成自然语言描述（给已有标签用）

中文显示名同时注册在 NODE_DISPLAY_NAME_MAPPINGS 里。
"""

import logging

# ⚠️ WEB_DIRECTORY 必须在其它导入之前设置，否则前端 JS 不会加载。
WEB_DIRECTORY = "./web"

logger = logging.getLogger("AnimaNSFW")

from .py import nodes  # noqa: E402

NODE_CLASS_MAPPINGS = dict(nodes.NODE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS = dict(nodes.NODE_DISPLAY_NAME_MAPPINGS)

# 注册 aiohttp 路由（标签库 / 提示词预览 / 引导状态）
ROUTES_OK = False
try:
    from .py import api

    ROUTES_OK = bool(api.register_routes())
except Exception as exc:  # pragma: no cover - 路由失败不应阻塞节点加载
    import traceback

    logger.warning("[AnimaNSFW] API 路由注册失败（节点仍可用）: %s", exc)
    traceback.print_exc()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY",
           "ROUTES_OK"]
