# -*- coding: utf-8 -*-
"""不启动 ComfyUI，直接从 py/tags.py 导出 /anima_nsfw/tags 的回复，作为冒烟测试的数据。

用法: python tools/animansfw_make_fixture.py
"""
import importlib.util
import json
import os
import sys
import types

# --- 自定位（脚本在 <包>/tools/ 下）---
import os as _os
import sys as _sys
TOOLS_DIR = _os.path.dirname(_os.path.abspath(__file__))
PKG_ROOT = _os.path.dirname(TOOLS_DIR)
COMFY_ROOT = _os.environ.get("COMFY_ROOT") or _os.path.dirname(
    _os.path.dirname(_os.path.dirname(PKG_ROOT)))
PY_EXE = _sys.executable


sys.stdout.reconfigure(encoding="utf-8")
ROOT = PKG_ROOT
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags_fixture.json")

pkg = types.ModuleType("p")
pkg.__path__ = [ROOT]
sys.modules["p"] = pkg
py = types.ModuleType("p.py")
py.__path__ = [os.path.join(ROOT, "py")]
sys.modules["p.py"] = py
pkg.py = py


def load(n):
    s = importlib.util.spec_from_file_location("p.py." + n, os.path.join(ROOT, "py", n + ".py"))
    m = importlib.util.module_from_spec(s)
    sys.modules["p.py." + n] = m
    s.loader.exec_module(m)
    return m


load("translations")
load("character_store")
tags = load("tags")
d = tags.as_dict()
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
# 顺带导出剧情库 + 每一拍的展开结果（给离线冒烟测试用）
story = load("story")
scenes = {}
for _arc in story.ARCS:
    for _sc in _arc["scenes"]:
        for _k in (_arc.get("cast") or []):   # 全部候选主角都要有（测试会换主角）
            scenes[f"{_arc['id']}|{_sc['id']}|{_k}"] = story.build_scene(
                _arc["id"], _sc["id"], _k)
SOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story_fixture.json")
with open(SOUT, "w", encoding="utf-8") as f:
    json.dump({"story": story.as_dict(), "scenes": scenes}, f, ensure_ascii=False,
              separators=(",", ":"))
print(f"写入 {SOUT}: {os.path.getsize(SOUT) / 1024:.0f} KB  "
      f"({story.counts()['arcs']} 条故事线 / {len(scenes)} 拍已展开)")

print(f"写入 {OUT}: {os.path.getsize(OUT) / 1024:.0f} KB")
print(f"  标签 {len(d['tags'])} / 分类 {len(d['categories'])} / 角色 {d['character_count']}"
      f" / 服装预设 {len(d['outfit_presets'])} / 姿势预设 {len(d['pose_presets'])}")
