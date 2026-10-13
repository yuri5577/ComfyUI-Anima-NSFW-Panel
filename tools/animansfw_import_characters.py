# -*- coding: utf-8 -*-
"""生成角色库 JSON（供后端索引 + 前端浏览）。

输出：
  web/characters.json   { "meta": {...}, "copies": {...}, "chars": [...] }

字段：
  n 英文名 / z 中文名(可能空) / c 作品 / p 热度 / t 推荐标签
"""
import importlib.util
import json
import os
import re
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
BASE = r"COMFY_ROOT\custom_nodes\Comfyui-Anima-Tools\js"
ROOT = PKG_ROOT
DST = os.path.join(ROOT, "web", "characters.json")
VISIBLE_MIN_POSTS = 300

# 机翻高频误译：这些词命中就认为不是真中文译名
BAD_TOKENS = re.compile(
    r"(裙子|连衣裙|外套|衬衣|衬衫|卫衣|毛衣|裤子|内裤|胸罩|袜子|鞋子|靴子|帽子|"
    r"头发|眼睛|耳朵|尾巴|武器|盔甲|颜色|蓝色|红色|白色|黑色|粉色|紫色|绿色|"
    r"黄色|橙色|灰色|银色|金色|水蓝|上衣|下装|领带|缎带|蝴蝶结|面具|护目镜|"
    r"眼镜|口袋|袖子|衣领|腰带|围巾|手套|披风|斗篷|光环|翅膀|角|十字架|"
    r"圣|魔法|机器|人偶|机械|手镯|项链|耳环|戒指|胸针|吊坠|徽章|条纹|格纹)"
)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def load_translations():
    pkg = types.ModuleType("p")
    pkg.__path__ = [ROOT]
    sys.modules["p"] = pkg
    py = types.ModuleType("p.py")
    py.__path__ = [os.path.join(ROOT, "py")]
    sys.modules["p.py"] = py
    pkg.py = py
    s = importlib.util.spec_from_file_location("p.py.translations",
                                              os.path.join(ROOT, "py", "translations.py"))
    m = importlib.util.module_from_spec(s)
    sys.modules["p.py.translations"] = m
    s.loader.exec_module(m)
    return m


def main():
    tr = load_translations()

    official = json.load(open(BASE + r"\character_official_data.json", encoding="utf-8"))
    raw = open(BASE + r"\character_data.js", encoding="utf-8", errors="replace").read()
    rows = json.loads(raw[raw.find("["): raw.rfind("]") + 1])

    by_trigger = {}
    for _k, v in official.items():
        trig = (v.get("trigger") or "").strip().lower()
        if trig:
            by_trigger[trig] = v.get("tags") or []

    chars, best = [], {}
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        copy = (r.get("copyright") or "").strip()
        trig = f"{name}, {copy}".lower() if copy else name.lower()
        tags = by_trigger.get(trig)
        if tags is None:
            for k, v in by_trigger.items():
                if k.startswith(name.lower() + ","):
                    tags = v
                    break
        tags = [str(t).strip().lower() for t in (tags or []) if str(t).strip()]
        posts = int(r.get("post_count") or 0)
        k = name.lower()
        if k not in best or posts > best[k]["posts"]:
            best[k] = {"name": name, "copyright": copy, "posts": posts, "tags": tags}
    chars = sorted(best.values(), key=lambda c: -c["posts"])
    print(f"角色 {len(chars)}（热度 >= {VISIBLE_MIN_POSTS}: "
          f"{sum(1 for c in chars if c['posts'] >= VISIBLE_MIN_POSTS)}）")

    # 手工校对的角色名（优先）
    sys.path.insert(0, os.path.join(ROOT, "py"))
    from character_names_zh import CHARACTER_ZH as CURATED_CHARS

    accepted = rejected = from_db = from_curated = 0
    out = []
    samples_ok, samples_bad = [], []
    for c in chars:
        zh = ""
        curated = CURATED_CHARS.get(c["name"].lower(), "")
        raw_zh = tr.MERGED.get(norm(c["name"])) or ""
        # 1) 手工校对 2) 中文资料里干净的真译名（必须没有残留英文）
        if curated:
            zh = curated
            from_curated += 1
            accepted += 1
        elif (raw_zh and raw_zh.lower() != c["name"].lower()
                and re.search(r"[\u4e00-\u9fff]", raw_zh)
                and not re.search(r"[a-zA-Z]", raw_zh)
                and not BAD_TOKENS.search(raw_zh) and len(raw_zh) <= 24):
            zh = raw_zh
            from_db += 1
            accepted += 1
        else:
            rejected += 1
            if raw_zh and len(samples_bad) < 8:
                samples_bad.append((c["name"], raw_zh))
        if zh and len(samples_ok) < 14:
            samples_ok.append((c["name"], zh))
        out.append({
            "n": c["name"], "z": zh, "c": c["copyright"],
            "p": c["posts"], "t": c["tags"],
        })

    print(f"手工校对: {from_curated}   中文资料命中: {from_db}")
    print(f"采用中文名: {accepted}   放弃: {rejected}")
    print("采用样例:")
    for a, b in samples_ok:
        print(f"   {a:<28} -> {b}")
    print("被判定为机翻而放弃的样例:")
    for a, b in samples_bad:
        print(f"   {a:<28} -> {b}  ← 看起来是硬凑的")

    copies = {}
    for c in chars:
        cp = c["copyright"]
        if not cp:
            continue
        copies.setdefault(cp, 0)
        copies[cp] = max(copies[cp], 0)
    copy_zh = {}
    for cp in copies:
        zh = tr.CURATED.get(cp) or tr.MERGED.get(norm(cp)) or ""
        if not zh:
            cand = tr.translate(cp, default="")
            if (cand and re.search(r"[\u4e00-\u9fff]", cand)
                    and not BAD_TOKENS.search(cand) and len(cand) <= 30):
                zh = cand
        if zh:
            copy_zh[cp] = zh
    print(f"\n作品 {len(copies)} 个，拿到中文 {len(copy_zh)} 个")

    payload = {
        "meta": {
            "schema": 1,
            "total": len(chars),
            "visible_min_posts": VISIBLE_MIN_POSTS,
            "visible": sum(1 for c in chars if c["posts"] >= VISIBLE_MIN_POSTS),
            "source": "Comfyui-Anima-Tools character_official_data.json + character_data.js",
            # 角色立绘缩略图：URL 由前端按 `角色名, 作品名` 拼接
            # （Animadex 官方 thumbs，抽样实测覆盖率 93%；404 时前端退回纯文字卡片）
            "preview": {
                "enabled": True,
                "base": "https://blobs.animadex.net/Outputs/thumbs/{}.webp",
                "note": "404 时自动退回纯文字卡片",
            },
        },
        "copies": copy_zh,
        "chars": out,
    }
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"已写入 {DST}  {os.path.getsize(DST) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
