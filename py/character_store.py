# -*- coding: utf-8 -*-
"""角色库读取（后端侧）。

数据文件：``web/characters.json``（由 tools/animansfw_import_characters.py 生成）
  共约 8000 个角色，字段 n=英文名 z=中文名 c=作品 p=热度 t=推荐标签

后端只用它来**索引**：让角色名参与去重 / 互斥（一个角色一次只能选一个），
以及给 /tags 接口提供一份轻量清单。完整数据由前端从 /anima_nsfw/characters 取。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(os.path.dirname(_HERE), "web", "characters.json")

_LOCK = threading.RLock()
_CACHE: Optional[Dict] = None


def load() -> Dict:
    """加载角色库（延迟 + 缓存）。缺失时返回空结构，不影响其它功能。"""
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        data = {"meta": {"total": 0}, "copies": {}, "chars": []}
        if os.path.isfile(PATH):
            try:
                with open(PATH, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict) and isinstance(raw.get("chars"), list):
                    data = raw
            except Exception:
                pass
        _CACHE = data
        return _CACHE


def reload() -> Dict:
    global _CACHE
    with _LOCK:
        _CACHE = None
    return load()


def meta() -> Dict:
    d = load()
    return {
        "path": PATH,
        "exists": os.path.isfile(PATH),
        "total": len(d.get("chars") or []),
        "copies": len(d.get("copies") or {}),
        **(d.get("meta") or {}),
    }


def tag_entries() -> List[tuple]:
    """轻量标签清单：(英文名, 中文名, 作品, 热度)。

    只有热度 >= ``visible_min_posts`` 的角色会在网格里可见，
    其余打 hidden（可用搜索 / 按作品筛选，或勾「显示隐藏标签」）。
    """
    d = load()
    minp = int((d.get("meta") or {}).get("visible_min_posts") or 1000)
    out = []
    for c in d.get("chars") or []:
        try:
            out.append((str(c["n"]), str(c.get("z") or c["n"]),
                        str(c.get("c") or ""), int(c.get("p") or 0), int(c.get("p") or 0) >= minp))
        except Exception:
            continue
    return out


def names() -> List[str]:
    return [c["n"] for c in (load().get("chars") or []) if c.get("n")]


def char_tags_map() -> Dict[str, List[str]]:
    """角色名(小写) -> 推荐标签，供节点在需要时补齐用（可选）。"""
    out = {}
    for c in load().get("chars") or []:
        n = str(c.get("n") or "").strip().lower()
        if n:
            out[n] = [str(t) for t in (c.get("t") or [])]
    return out
