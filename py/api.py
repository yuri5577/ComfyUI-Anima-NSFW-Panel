# -*- coding: utf-8 -*-
"""前端用的 aiohttp 路由。

* ``GET  /anima_nsfw/tags``            标签库 + 预置 + 强度档位
* ``POST /anima_nsfw/preview``         复用后端合成逻辑做实时预览
* ``GET  /anima_nsfw/status``          调制引导适配器/权重列表
* ``GET  /anima_nsfw/custom``          读取自定义库（触发词 / 角色 / 服装 / 姿势）
* ``POST /anima_nsfw/custom/save``     新增或更新一条
* ``POST /anima_nsfw/custom/delete``   删除一条
* ``POST /anima_nsfw/custom/import``   合并导入
"""

from __future__ import annotations

import json
import traceback

from aiohttp import web

try:
    from server import PromptServer
except Exception:  # pragma: no cover
    PromptServer = None

from . import custom_store as cs
from . import mod_guidance as mg
from .prompt_builder import preview
from .tags import as_dict


def _json(data, status: int = 200):
    return web.json_response(data, status=status, dumps=lambda o: __import__("json").dumps(o, ensure_ascii=False))


def register_routes() -> bool:
    if PromptServer is None or getattr(PromptServer, "instance", None) is None:
        return False

    routes = PromptServer.instance.routes

    @routes.get("/anima_nsfw/tags")
    async def anima_nsfw_tags(_request):
        try:
            return _json(as_dict())
        except Exception as exc:  # pragma: no cover
            return _json({"error": str(exc), "trace": traceback.format_exc()}, 500)

    @routes.post("/anima_nsfw/preview")
    async def anima_nsfw_preview(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            return _json(preview(payload or {}))
        except Exception as exc:  # pragma: no cover
            return _json({"error": str(exc), "trace": traceback.format_exc()}, 500)

    @routes.get("/anima_nsfw/status")
    async def anima_nsfw_status(_request):
        try:
            adapters = mg.list_adapters()
        except Exception:
            adapters = []
        return _json({
            "adapters": adapters,
            "default_adapter": mg.DEFAULT_ADAPTER_FILENAME,
            "profiles": {k: {
                "w": v[0], "start_layer": v[1], "end_layer": v[2],
                "taper": v[3], "taper_scale": v[4], "final_w": v[5],
            } for k, v in mg.PROFILES.items()},
        })

    @routes.get("/anima_nsfw/story")
    async def anima_nsfw_story(_request):
        """剧情库：故事线 + 可选主角。"""
        try:
            from . import story

            return _json(story.as_dict())
        except Exception as exc:  # pragma: no cover
            return _json({"error": str(exc), "arcs": [], "cast": {}}, 500)

    @routes.get("/anima_nsfw/story/scene")
    async def anima_nsfw_story_scene(request):
        """把某一拍展开成生成参数（含连续性标签）。

        query: arc=故事id & scene=第几拍 & cast=主角key & extra=额外标签
        """
        try:
            from . import story

            q = request.rel_url.query
            data = story.build_scene(
                str(q.get("arc", "")),
                int(q.get("scene", 1) or 1),
                cast_key=(q.get("cast") or None),
                extra_tags=str(q.get("extra", "") or ""),
            )
            return _json({"ok": True, "scene": data})
        except Exception as exc:  # pragma: no cover
            import traceback

            return _json({"ok": False, "error": str(exc),
                          "trace": traceback.format_exc()}, 400)

    @routes.get("/anima_nsfw/characters")
    async def anima_nsfw_characters(_request):
        """完整角色库（约 8000 个），供面板的角色浏览器使用。"""
        try:
            from . import character_store as cstore

            data = cstore.load()
            return _json({
                "meta": cstore.meta(),
                "copies": data.get("copies") or {},
                "chars": data.get("chars") or [],
            })
        except Exception as exc:  # pragma: no cover
            return _json({"error": str(exc), "chars": [], "copies": {}}, 500)

    # ------------------------------------------------------------------
    # 自定义库（触发词 / 角色 / 服装 / 姿势）
    # ------------------------------------------------------------------

    @routes.get("/anima_nsfw/custom")
    async def anima_nsfw_custom_get(_request):
        try:
            return _json({"ok": True, "data": cs.all_entries(), "info": cs.info()})
        except Exception as exc:  # pragma: no cover
            return _json({"ok": False, "error": str(exc),
                          "trace": traceback.format_exc()}, 500)

    @routes.post("/anima_nsfw/custom/save")
    async def anima_nsfw_custom_save(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        kind = str((payload or {}).get("kind") or "")
        try:
            entry = cs.upsert(kind, payload or {})
            return _json({"ok": True, "entry": entry, "data": cs.all_entries()})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)}, 400)

    @routes.post("/anima_nsfw/custom/delete")
    async def anima_nsfw_custom_delete(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        kind = str((payload or {}).get("kind") or "")
        eid = str((payload or {}).get("id") or "")
        try:
            ok = cs.delete(kind, eid)
            return _json({"ok": True, "deleted": ok, "data": cs.all_entries()})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)}, 400)

    @routes.post("/anima_nsfw/custom/import")
    async def anima_nsfw_custom_import(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            data = cs.merge_import((payload or {}).get("data") or payload or {})
            return _json({"ok": True, "data": data})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)}, 400)

    @routes.get("/anima_nsfw/custom/export")
    async def anima_nsfw_custom_export(_request):
        try:
            payload = json.dumps(cs.all_entries(), ensure_ascii=False, indent=1)
        except Exception as exc:  # pragma: no cover
            return _json({"ok": False, "error": str(exc)}, 500)
        return web.Response(
            text=payload,
            content_type="application/json",
            charset="utf-8",
            headers={"Content-Disposition":
                     'attachment; filename="anima_nsfw_custom_library.json"'},
        )

    return True
