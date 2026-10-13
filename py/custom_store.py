# -*- coding: utf-8 -*-
"""用户自定义库：触发词 + 自定义角色。

存成节点目录下的 ``custom_library.json``（UTF-8），这样：
  * 重启 ComfyUI 不丢
  * 可以直接复制/备份/发给别人
  * 想在多台机器同步就同步这一个文件

前端还有 localStorage 缓存，两边以文件为准（写入走 API 即刻落盘）。
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(os.path.dirname(_HERE), "custom_library.json")

_LOCK = threading.RLock()
_CACHE: Optional[Dict[str, list]] = None

KINDS = ("trigger", "character", "outfit", "pose")
MAX_ENTRIES = 500          # 每类上限，防止文件无限膨胀
MAX_TAGS = 120             # 单条最多多少个标签
MAX_NAME = 60

DEFAULT = {
    "version": 1,
    "trigger": [],          # 自定义触发词（LoRA 触发词、画师名等）
    "character": [],        # 自定义角色（角色名 + 一串标签）
    "outfit": [],           # 自定义服装套装
    "pose": [],             # 自定义姿势
}


def _clean_tags(raw) -> List[str]:
    """接受字符串（逗号/换行分隔）或列表，清洗成标签数组。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,，、\n]+", raw)
    elif isinstance(raw, (list, tuple)):
        parts = []
        for x in raw:
            parts.extend(re.split(r"[,，、\n]+", str(x)))
    else:
        parts = [str(raw)]
    out, seen = [], set()
    for p in parts:
        t = p.strip().strip(",").lower().replace("_", " ")
        t = re.sub(r"\s+", " ", t)
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out


def _clean_name(raw) -> str:
    s = str(raw or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:MAX_NAME]


def _new_id(kind: str) -> str:
    return f"{kind[0]}{int(time.time() * 1000) % 10**10}{os.urandom(2).hex()}"


def _load(force: bool = False) -> Dict[str, list]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None and not force:
            return _CACHE
        data = {k: [] for k in KINDS}
        data["version"] = DEFAULT["version"]
        if os.path.isfile(STORE_PATH):
            try:
                with open(STORE_PATH, encoding="utf-8") as f:
                    raw = json.load(f)
                for k in KINDS:
                    items = raw.get(k) or []
                    if isinstance(items, list):
                        data[k] = [x for x in items if isinstance(x, dict)]
            except Exception:
                # 文件坏了不要静默清空：备份一份再重来
                try:
                    os.replace(STORE_PATH, STORE_PATH + ".broken")
                except OSError:
                    pass
        _CACHE = data
        return _CACHE


def _save(data: Dict[str, list]) -> None:
    with _LOCK:
        tmp = STORE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STORE_PATH)


def all_entries(force: bool = False) -> Dict[str, list]:
    with _LOCK:
        data = _load(force)
        return {k: list(data.get(k) or []) for k in KINDS}


def upsert(kind: str, payload: Dict) -> Dict:
    """新增或更新一条。带 id 且存在 = 更新，否则新增。"""
    if kind not in KINDS:
        raise ValueError(f"未知类型: {kind}")
    name = _clean_name(payload.get("name"))
    if not name:
        raise ValueError("名字不能为空")
    tags = _clean_tags(payload.get("tags"))
    trigger = _clean_name(payload.get("trigger"))
    icon = _clean_name(payload.get("icon"))[:4]

    with _LOCK:
        data = _load()
        items = data.setdefault(kind, [])
        eid = _clean_name(payload.get("id"))
        entry = None
        if eid:
            entry = next((x for x in items if x.get("id") == eid), None)
        if entry is None and len(items) >= MAX_ENTRIES:
            raise ValueError(f"{kind} 条目已达上限 {MAX_ENTRIES}，请先删掉一些")
        if entry is None:
            entry = {"id": _new_id(kind), "created": int(time.time())}
            items.append(entry)
        entry.update({
            "name": name,
            "trigger": trigger,
            "tags": tags,
            "icon": icon or entry.get("icon", ""),
            "updated": int(time.time()),
        })
        if kind == "trigger" and not entry["tags"] and not entry["trigger"]:
            raise ValueError("触发词不能为空")
        _save(data)
        return dict(entry)


def delete(kind: str, entry_id: str) -> bool:
    if kind not in KINDS:
        raise ValueError(f"未知类型: {kind}")
    with _LOCK:
        data = _load()
        items = data.setdefault(kind, [])
        before = len(items)
        data[kind] = [x for x in items if x.get("id") != entry_id]
        changed = len(data[kind]) != before
        if changed:
            _save(data)
        return changed


def merge_import(payload: Dict) -> Dict[str, list]:
    """整体导入（合并模式：同名同类型覆盖）。"""
    with _LOCK:
        data = _load()
        for kind in KINDS:
            incoming = payload.get(kind)
            if not isinstance(incoming, list):
                continue
            items = data.setdefault(kind, [])
            by_name = {x.get("name", "").lower(): x for x in items}
            for raw in incoming:
                if not isinstance(raw, dict):
                    continue
                name = _clean_name(raw.get("name"))
                if not name:
                    continue
                target = by_name.get(name.lower())
                if target is None:
                    if len(items) >= MAX_ENTRIES:
                        continue
                    target = {"id": _new_id(kind), "created": int(time.time())}
                    items.append(target)
                    by_name[name.lower()] = target
                target.update({
                    "name": name,
                    "trigger": _clean_name(raw.get("trigger")),
                    "tags": _clean_tags(raw.get("tags")),
                    "icon": _clean_name(raw.get("icon"))[:4] or target.get("icon", ""),
                    "updated": int(time.time()),
                })
        _save(data)
        return all_entries(force=True)


def info() -> Dict:
    data = _load()
    return {
        "path": STORE_PATH,
        "counts": {k: len(data.get(k) or []) for k in KINDS},
        "limits": {"per_kind": MAX_ENTRIES, "tags_per_entry": MAX_TAGS},
    }
