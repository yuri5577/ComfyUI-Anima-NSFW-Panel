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

import asyncio
import json
import traceback

from aiohttp import web

try:
    from server import PromptServer
except Exception:  # pragma: no cover
    PromptServer = None

from . import custom_store as cs
from . import mod_guidance as mg
from . import thumb_cache as tc
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

    # ------------------------------------------------------------------
    # 缩略图本地缓存
    #
    # 面板的预览图全部来自境外 CDN（jsDelivr / animadex），用户反馈要挂 VPN。
    # 前端改成请求这里，后端负责"下载一次 → 存本地 → 之后只读磁盘"。
    # ------------------------------------------------------------------

    @routes.get("/anima_nsfw/thumb")
    async def anima_nsfw_thumb(request):
        url = str(request.query.get("u") or "").strip()
        if not url:
            return web.Response(body=tc.TRANSPARENT_PNG,
                                content_type="image/png",
                                headers={"X-Anima-Cache": "miss"})
        force = str(request.query.get("force") or "") in ("1", "true", "yes")
        # 下载是阻塞 IO，扔到线程池，别卡住 aiohttp 的事件循环
        loop = asyncio.get_running_loop()
        path, err, hit = await loop.run_in_executor(
            None, lambda: tc.fetch(url, force=force))
        if not path:
            # 失败也返回一张 1×1 透明图（前端就不会出现破图边框），
            # 并把原因放在 header 里方便排查。**不缓存失败结果**。
            return web.Response(body=tc.TRANSPARENT_PNG, content_type="image/png",
                                headers={"X-Anima-Cache": "miss",
                                         "X-Anima-Error": (err or "unknown")[:180]})
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as exc:  # noqa: BLE001
            return web.Response(body=tc.TRANSPARENT_PNG, content_type="image/png",
                                headers={"X-Anima-Cache": "miss",
                                         "X-Anima-Error": f"read {exc}"[:180]})
        return web.Response(
            body=data, content_type=tc.content_type(path),
            headers={
                "X-Anima-Cache": "hit" if hit else "stored",
                # 内容不会变，长缓存；文件名带 URL 哈希，改了 URL 就是新文件
                "Cache-Control": "public, max-age=2592000, immutable",
            })

    @routes.get("/anima_nsfw/thumb_cache/stats")
    async def anima_nsfw_thumb_stats(_request):
        try:
            s = tc.stats()
            return _json(s)
        except Exception as exc:  # pragma: no cover
            return _json({"error": str(exc)}, 500)

    @routes.post("/anima_nsfw/thumb_cache/warm")
    async def anima_nsfw_thumb_warm(request):
        """批量预热。前端把当前需要的 URL 列表发过来，后台慢慢下。"""
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        urls = payload.get("urls") or []
        if not isinstance(urls, list):
            return _json({"ok": False, "error": "urls 必须是数组"}, 400)
        force = bool(payload.get("force"))
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, lambda: tc.warm(urls, force=force))
        return _json({"ok": True, **res, **tc.stats()})

    @routes.post("/anima_nsfw/thumb_cache/clear")
    async def anima_nsfw_thumb_clear(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not bool(payload.get("confirm")):
            return _json({"ok": False, "error": "需要 confirm: true"}, 400)
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, tc.clear)
        return _json({**res, **tc.stats()})

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
