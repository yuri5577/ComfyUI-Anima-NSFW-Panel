# -*- coding: utf-8 -*-
"""对「解压出来的副本」做最终验证：严格模拟新用户的环境。

把解压目录临时插入 sys.path 最前面，确保导入的是解压副本而不是开发目录，
然后检查节点、接口、标签库、示例工作流、前端 JS 语法。
"""
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

# --- 自定位（脚本在 <包>/tools/ 下）---
import os as _os
import sys as _sys


def _find_comfy_root(start):
    """从 start 往上找含 comfy/ 子目录的那一层（= ComfyUI 根）。

    ⚠️ 不能简单地"往上数三层"：那只在 `ComfyUI/custom_nodes/<包>/tools/`
    这种标准布局下成立。而且如果解析错了、只是碰巧靠当前工作目录才导入成功，
    换个目录跑就会 `ModuleNotFoundError: No module named 'comfy'`。
    """
    env = _os.environ.get("COMFY_ROOT")
    if env and _os.path.isdir(_os.path.join(env, "comfy")):
        return env
    # 先看包所在位置能不能找到（标准布局 custom_nodes/<包>/tools/）
    # 再从**当前工作目录**往上找 —— 常见用法就是在 ComfyUI 根下跑这个脚本，
    # 而包被解压到了别处（比如临时目录）。
    for start_dir in (_os.path.abspath(start), _os.getcwd()):
        cur = start_dir
        for _ in range(8):
            if _os.path.isdir(_os.path.join(cur, "comfy")):
                return cur
            parent = _os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return env or _os.path.dirname(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(start))))


TOOLS_DIR = _os.path.dirname(_os.path.abspath(__file__))
PKG_ROOT = _os.path.dirname(TOOLS_DIR)
COMFY_ROOT = _find_comfy_root(PKG_ROOT)
PY_EXE = _os.environ.get("PY_EXE") or _sys.executable


sys.stdout.reconfigure(encoding="utf-8")
# VERIFY = **包含本包的父目录**（即解压出来的那层），里面应当有 ComfyUI-Anima-NSFW-Panel/
# 默认就从本脚本所在位置推：tools/ 的上一级是包，再上一级是解压目录
VERIFY = os.environ.get("VERIFY_DIR") or _os.path.dirname(PKG_ROOT)
COMFY = COMFY_ROOT
PKG_DIR = os.path.join(VERIFY, "ComfyUI-Anima-NSFW-Panel")
PKG_NAME = "ComfyUI-Anima-NSFW-Panel"
# 跑 JS 测试用的 node（可由环境变量指定）
node = os.environ.get("NODE_EXE") or shutil.which("node") or "node"
# 这些路径下面的各个小节都要用，所以放在模块级（原来 js/node 定义在
# `if mod is not None:` 块里，模块级的冒烟测试段引用它们会 NameError）
js = os.path.join(PKG_DIR, "web", "anima_nsfw_panel.js")
_py = os.environ.get("PY_EXE") or PY_EXE
TOOLS = TOOLS_DIR

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"{'OK  ' if cond else 'ERR '} {label}{('  ' + str(extra)) if extra else ''}")
    if not cond:
        ok = False


# 1. 只把解压目录放到 sys.path 最前（custom_nodes 不加入）
sys.path.insert(0, COMFY)
sys.path.insert(0, VERIFY)

check("解压副本存在", os.path.isfile(os.path.join(PKG_DIR, "__init__.py")))

# 2. 导入
mod = None
try:
    mod = importlib.import_module(PKG_NAME)
    check("import 成功", True)
    check("导入来源是解压副本", os.path.abspath(mod.__file__).startswith(os.path.abspath(VERIFY)),
          mod.__file__)
except Exception:
    traceback.print_exc()
    check("import 成功", False)

if mod is not None:
    nodes = importlib.import_module(PKG_NAME + ".py.nodes")
    expect = {"AnimaNsfwPromptBuilder", "AnimaNsfwNegativeBuilder",
              "AnimaNsfwModGuidance", "AnimaNsfwCaptionOnly"}
    check("4 个节点齐全", set(nodes.NODE_CLASS_MAPPINGS) == expect,
          sorted(nodes.NODE_CLASS_MAPPINGS))
    check("中文显示名齐全", set(nodes.NODE_DISPLAY_NAME_MAPPINGS) == expect)
    check("WEB_DIRECTORY", mod.WEB_DIRECTORY == "./web")

    # 3. INPUT_TYPES 全部可构造
    for name, cls in nodes.NODE_CLASS_MAPPINGS.items():
        try:
            spec = cls.INPUT_TYPES()
            check(f"{name} INPUT_TYPES", bool(spec.get("required")))
        except Exception as e:
            check(f"{name} INPUT_TYPES", False, e)

    # 4. 合成逻辑
    pb = importlib.import_module(PKG_NAME + ".py.prompt_builder")
    r = pb.compose_prompt(tags="1girl, 1boy, doggystyle, ahegao, cum",
                          intensity="hard", quality_preset="best quality")
    check("提示词合成", r["prompt"].startswith("best quality") and "doggystyle" in r["prompt"],
          r["prompt"][:80])
    n = pb.compose_negative(base_enabled=True, extras=["手部修复"])
    check("负面合成", "worst quality" in n["prompt"] and "bad hands" in n["prompt"])

    # 5. 标签库
    tags = importlib.import_module(PKG_NAME + ".py.tags")
    d = tags.as_dict()
    check("标签库 11157 条 / 14 分类", len(d["tags"]) == 11157 and len(d["categories"]) == 14,
          f'{len(d["tags"])} / {len(d["categories"])}')
    check("每条标签都有中文", all(t.get("zh") for t in d["tags"]))
    cop = [t for t in d["tags"] if t["c"] == "copyright"]
    check("作品/版权标签 140 条（102 游戏 + 38 轻小说）", len(cop) == 140, len(cop))
    check("作品标签分两个互斥组（游戏 / 轻小说）",
          {t.get("g") for t in cop} == {"copyright_base", "light_novel_base"},
          sorted({t.get("g") for t in cop}))
    for want in ("blue archive", "azur lane", "kantai collection", "touhou",
                 "sword art online", "mushoku tensei"):
        hit = next((t for t in cop if t["t"] == want), None)
        check(f"作品标签 {want} 可见", bool(hit), hit.get("zh") if hit else "缺失")
    check("质量预置 5 档", len(d["quality_presets"]) == 5, list(d["quality_presets"]))
    check("负面基线内置", len(d["negative_base"]) > 200, f'{len(d["negative_base"])} 字符')
    check("负面分段 6 段", len(d["negative_extra"]) == 6, list(d["negative_extra"]))

    # 5b. 角色库
    cch = [t for t in d["tags"] if t["c"] == "character"]
    check("角色库 8017 个", len(cch) == 8017, len(cch))
    # 可见 = 热度 >= visible_min_posts（角色库按热度过滤，不是 hidden 字段）
    check("角色可见 6413 / 隐藏 1604",
          sum(1 for t in cch if not t.get("hidden")) == 6413
          and sum(1 for t in cch if t.get("hidden")) == 1604,
          f'{sum(1 for t in cch if not t.get("hidden"))} / {sum(1 for t in cch if t.get("hidden"))}')
    check("角色共用一个互斥组", {t.get("g") for t in cch} == {"character_base"},
          sorted({t.get("g") for t in cch}))
    for w, zh in (("hatsune miku", "初音未来"), ("hakurei reimu", "博丽灵梦"),
                  ("pikachu", "皮卡丘"), ("raiden shogun", "雷电将军")):
        t = next((x for x in cch if x["t"] == w), None)
        check(f"角色中文名 {w}", bool(t) and t["zh"] == zh, t["zh"] if t else "缺失")

    # 5c. 中文翻译覆盖率（非角色标签）
    nonchar = [t for t in d["tags"] if t["c"] != "character"]
    zh_ok = sum(1 for t in nonchar if any("\u4e00" <= ch <= "\u9fff" for ch in t["zh"]))
    rate = zh_ok / max(1, len(nonchar))
    check("非角色标签中文覆盖 > 80%", rate > 0.80, f"{rate * 100:.1f}%")
    tr = importlib.import_module(PKG_NAME + ".py.translations")
    check("翻译层 aqua shawl", tr.translate("aqua shawl") == "水蓝披肩", tr.translate("aqua shawl"))
    check("翻译层 armpit cutout", tr.translate("armpit cutout") == "腋下镂空")
    # 剧情模式
    _story = importlib.import_module(PKG_NAME + ".py.story")
    _sc = _story.counts()
    check("剧情 11 条故事线 / 66 拍", _sc["arcs"] == 11 and _sc["scenes"] == 66,
          f'{_sc["arcs"]} 线 / {_sc["scenes"]} 拍 / {_sc["cast"]} 主角')
    check("每条故事线 6 拍", all(len(x["scenes"]) == 6 for x in _story.ARCS))
    check("每拍都有中文台词",
          all(s.get("dialogue") for x in _story.ARCS for s in x["scenes"]))
    _r = _story.build_scene("onsen_ryokan", 3, "raiden")
    check("展开某一拍带 char_lock（主角锁定）", "char_lock:raiden shogun" in _r["tags"])
    check("展开某一拍带主角立绘标签", "purple hair" in _r["tags"])
    check("展开某一拍带固定服装", "kimono" in _r["tags"])
    check("标签串里没有引号（台词走 caption_text）", '"' not in _r["tags"])
    _toks = [x.strip().lower() for x in _r["tags"].split(", ")]
    check("展开的标签无重复", len(_toks) == len(set(_toks)))
    check("台词单独给出", bool(_r["caption_text"]) and bool(_r["dialogue"]))
    check("seed_hint 为递增", _r.get("seed_hint") == "递增 +1")
    # 全库体检：不能有重复标签 / 引号 / 缺 char_lock / 缺台词
    _bad = []
    for _a in _story.ARCS:
        for _s in _a["scenes"]:
            for _k in _a["cast"]:
                _r2 = _story.build_scene(_a["id"], _s["id"], _k)
                _tk = [x.strip().lower() for x in _r2["tags"].split(", ")]
                if len(_tk) != len(set(_tk)):
                    _bad.append("dup:" + _a["id"])
                if '"' in _r2["tags"]:
                    _bad.append("quote:" + _a["id"])
                if "char_lock:" not in _r2["tags"]:
                    _bad.append("nolock:" + _a["id"])
                if not _r2["dialogue"] or not _r2["caption_text"]:
                    _bad.append("nodlg:" + _a["id"])
    check("剧情全库体检（无重复/无引号/都锁主角/都有台词）", not _bad,
          str(sorted(set(_bad))[:4]) if _bad else "OK")
    # 每拍的数量锚点必须恰好一组
    _anchor_bad = []
    for _a in _story.ARCS:
        for _s in _a["scenes"]:
            for _k in _a["cast"]:
                _r3 = _story.build_scene(_a["id"], _s["id"], _k)
                _tk2 = [x.strip().lower() for x in _r3["tags"].split(", ")]
                _cnt = [x for x in _tk2 if x in _story._COUNT_TAGS]
                if len(_cnt) != 2 or "1girl" not in _cnt:
                    _anchor_bad.append(f'{_a["id"]}#{_s["id"]}:{_cnt}')
                if "2people" in _tk2:
                    _anchor_bad.append(f'{_a["id"]}#{_s["id"]}:2people')
    check("每拍数量锚点恰好一组（无双胞胎风险）", not _anchor_bad,
          str(_anchor_bad[:3]) if _anchor_bad else "OK")
    check("新增题材已收录（青梅竹马/催眠/时间停止）",
          {"childhood_promise", "hypno_pocketwatch", "time_stop_watch"}
          <= {x["id"] for x in _story.ARCS})
    _tg = importlib.import_module(PKG_NAME + ".py.tags")
    for _w in ("spiral eyes", "hypnosis", "time stop", "clock",
               "childhood friend", "pendulum", "frozen in time"):
        check(f"剧情标签已入正式标签库 {_w}", _w in _tg.TAG_INDEX)

    # 种子控制
    _it = importlib.import_module(PKG_NAME + ".py.nodes").AnimaNsfwPromptBuilder.INPUT_TYPES()
    _opt = list(_it.get("optional", {}).keys())
    check("面板有 seed_mode 控件", "seed_mode" in _opt, str(_opt[-3:]))
    check("面板有 seed 控件", "seed" in _opt)
    _sm = _it["optional"]["seed_mode"][0]
    check("种子 4 种模式", len(list(_sm)) == 4, str(list(_sm)))
    _nod = importlib.import_module(PKG_NAME + ".py.nodes")
    check("种子模式→自动控制映射", _nod.SEED_CONTROL.get(_nod.SEED_MODE_RANDOM) == "randomize")
    check("轻小说 38 部", d.get("light_novel_count") == 38, d.get("light_novel_count"))
    lng = [g["id"] for g in d["copyright_groups"]]
    check("有 light_novel 分组", "light_novel" in lng, str(lng))
    ln = [t for t in d["tags"] if t.get("g") == "light_novel_base"]
    check("轻小说共用独立互斥组", len(ln) == 38 and len({x["t"] for x in ln}) == 38, len(ln))
    for w in ("sword art online", "toaru majutsu no index", "mushoku tensei"):
        check(f"轻小说收录 {w}", any(x["t"] == w for x in ln))
    _cj = json.load(open(os.path.join(PKG_DIR, "web", "characters.json"), encoding="utf-8"))
    _pv = (_cj.get("meta") or {}).get("preview") or {}
    check("角色库带立绘 URL 模板", bool(_pv.get("enabled")) and "animadex" in str(_pv.get("base")),
          str(_pv.get("base"))[:46])
    csx = importlib.import_module(PKG_NAME + ".py.character_store")
    check("角色库文件随包分发", csx.meta().get("total") == 8017, csx.meta().get("total"))
    # 封印者（Closers）角色：直接查角色库文件（cch 的结构不保证有 c 字段）
    _cl = [c for c in ((csx.load() or {}).get("chars") or []) if c.get("c") == "closers"]
    check("新增封印者角色 21 个", len(_cl) >= 21, len(_cl))
    check("封印者角色都有性别标注",
          all(c.get("gender") in ("1girl", "1boy", "uncertain") for c in _cl),
          f'{sum(1 for c in _cl if c.get("gender") == "uncertain")} 个存疑')

    pc = d["outfit_preset_count"]
    check("服装预设 568 套 / 37 组",
          pc["all"] == 568 and len(d["outfit_groups"]) == 37,
          f'{pc["all"]} (手工 {pc["curated"]} + 服装库 {pc["imported"]}'
          f' + 游戏COS {sum(1 for p in d["outfit_presets"] if p.get("src") == "game-cos")})'
          f' / {len(d["outfit_groups"])}')
    # 游戏分组 8 个：碧蓝 6 阵营 + 封印者 + 通用 COS
    # （v1.9.9 把封印者的「基础」「各队制服」并成一组）
    check("游戏 COS 服装 50 套 / 8 组",
          sum(1 for p in d["outfit_presets"] if p.get("src") == "game-cos") >= 50
          and len([g for g in d["outfit_groups"] if g.get("src") == "game-cos"]) == 8)

    # 服装分组分布检查：568 套 / 37 组，最大的组不能超过 15%（防止又退化成
    # 原来那种"性感暴露一组占 160/518"的样子 —— 那样等于没分类）
    _gcount = {}
    for _p in d["outfit_presets"]:
        _gcount[_p["g"]] = _gcount.get(_p["g"], 0) + 1
    _total = sum(_gcount.values()) or 1
    _biggest = max(_gcount.items(), key=lambda kv: kv[1]) if _gcount else ("", 0)
    check("服装分组分布均衡（最大组 < 15%）",
          _biggest[1] / _total < 0.15,
          f'{_biggest[0]} {_biggest[1]}/{_total} = {_biggest[1] / _total:.0%}，共 {len(_gcount)} 组')
    check("服装分组没有空组",
          all(v > 0 for v in _gcount.values()),
          f'{len(_gcount)} 组')
    check("服装带预览图 430",
          sum(1 for p in d["outfit_presets"] if p["preview"]) == 430)
    check("姿势预设 297 个 / 8 组",
          len(d["pose_presets"]) == 297 and len(d["pose_groups"]) == 8,
          f'{len(d["pose_presets"])} / {len(d["pose_groups"])}')
    check("姿势带预览图 297",
          all(p["preview"].startswith("https://") for p in d["pose_presets"]))
    preset_tag_set = {t["t"].lower() for t in d["tags"]}
    missing = {t for p in d["outfit_presets"] + d["pose_presets"]
               for t in p["tags"] if t.lower() not in preset_tag_set}
    check("预设标签都在标签库里", not missing, sorted(missing)[:5])
    check("锁定角色预设 17 条",
          sum(1 for p in d["outfit_presets"] if p["lock"]) == 17)
    bad = [p["zh"] for p in d["outfit_presets"] + d["pose_presets"]
           if ":1." in " ".join(p["tags"])]
    check("预设里没有权重残留", not bad, bad[:3])

    # 6. 前端 JS 资源
    check("面板 JS 存在", os.path.isfile(js))
    if shutil.which(node) or os.path.isfile(node):
        tmp = os.path.join(tempfile.gettempdir(), "verify_panel.mjs")
        shutil.copyfile(js, tmp)
        p = subprocess.run([node, "--check", tmp], capture_output=True, text=True, encoding="utf-8", errors="replace")
        check("面板 JS 语法", p.returncode == 0, p.stderr.strip()[:200])
    else:
        print("SKIP  未找到 node，跳过 JS 语法检查")

    # 6b. 自定义库模块
    cs = importlib.import_module(PKG_NAME + ".py.custom_store")
    check("custom_store 可导入", hasattr(cs, "upsert") and hasattr(cs, "merge_import"))
    check("自定义库四类", tuple(cs.KINDS) == ("trigger", "character", "outfit", "pose"),
          cs.KINDS)
    check("自定义库有配额限制", cs.MAX_ENTRIES > 0 and cs.MAX_TAGS > 0,
          f"{cs.MAX_ENTRIES} 条 / {cs.MAX_TAGS} 标签")
    check("自定义库文件不随包分发（用户数据）",
          not os.path.isfile(os.path.join(PKG_DIR, "custom_library.json")))

# 6b2. SFW 双模式自测
_sfw_test = os.path.join(TOOLS, "animansfw_sfw_selftest.py")
if os.path.isfile(_sfw_test):
    p = subprocess.run([_py, _sfw_test], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = [l for l in (p.stdout or "").splitlines() if l.startswith("RESULT")]
    check("SFW 双模式自测", p.returncode == 0, (tail[-1] if tail else "")[:60])
    if p.returncode != 0:
        for l in (p.stdout or "").splitlines():
            if l.startswith("FAIL"):
                print("        " + l)
else:
    print("SKIP  缺少 SFW 自测脚本，跳过")

# 6c. 离线冒烟测试（现代 + 低版本前端），不需要启动 ComfyUI
SMOKE = os.path.join(TOOLS, "animansfw_panel_smoke.mjs")
FIXTURE = os.path.join(TOOLS, "tags_fixture.json")
_py = os.environ.get("PY_EXE") or PY_EXE
_dshpy = _py
if os.path.isfile(FIXTURE) and os.path.isfile(SMOKE):
    subprocess.run([_dshpy, os.path.join(os.path.dirname(SMOKE), "animansfw_make_fixture.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    for mode, label in (([], "现代前端"), (["--legacy"], "低版本前端"),
                        (["--oldfe"], "老前端契约 1.12.x")):
        p = subprocess.run([node, SMOKE, *mode, js], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tail = (p.stdout or "").strip().splitlines()[-1:] or [""]
        check(f"离线冒烟测试（{label}）", p.returncode == 0, tail[0][:70])
        if p.returncode != 0:
            errs = [l for l in (p.stdout or "").splitlines() if l.startswith("ERR")]
            for e in errs[:6]:
                print("        " + e)
else:
    print("SKIP  缺少冒烟测试或 fixture，跳过")

# 6d. 性能回归门限（离线基准，不需要启动 ComfyUI）
_PERF = os.path.join(TOOLS, "animansfw_perf.mjs")
if os.path.isfile(_PERF):
    _r = subprocess.run([node, _PERF], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=900)
    _out = _r.stdout or ""
    # 开面板那行的格式： 开面板（首次）    —   1981   2068  （...）
    _m = re.search(r"开面板（首次）\s+[—\-]\s+(\d+)\s+(\d+)", _out)
    if _m:
        _dom, _sty = int(_m.group(1)), int(_m.group(2))
        # 修前是 110315 / 625184；这里卡住数量级，防分页或批量化被改回去
        check("性能：开面板建 DOM < 8000", _dom < 8000, f"{_dom}")
        check("性能：开面板写 style < 8000", _sty < 8000, f"{_sty}")
    else:
        check("性能基准可解析", False, (_out or _r.stderr or "")[-160:])
    _m2 = re.search(r"连点 5 个标签的预览请求.*?稳定后\s*(\d+)\s*次", _out)
    if _m2:
        check("性能：预览请求已防抖（连点 5 次 → 1 次）",
              int(_m2.group(1)) <= 2, f"{_m2.group(1)} 次")
    _m3 = re.search(r"点一个标签\s+([\d.]+) ms\s+(\d+)\s+(\d+)", _out)
    if _m3:
        check("性能：点标签建 DOM < 40", int(_m3.group(2)) < 40, f"{_m3.group(2)}")
else:
    print("SKIP  缺少性能基准脚本，跳过")

# 7. 示例工作流
wf = os.path.join(PKG_DIR, "workflows", "Anima-NSFW面板-调制引导.json")
try:
    data = json.load(open(wf, encoding="utf-8"))
    types = {n["type"] for n in data["nodes"]}
    check("示例工作流可解析", True, f'{len(data["nodes"])} 节点 / {len(data["links"])} 连线')
    check("示例工作流含新面板节点", "AnimaNsfwPromptBuilder" in types and
          "AnimaNsfwModGuidance" in types and "AnimaNsfwNegativeBuilder" in types)
    check("示例工作流含模型与 LoRA", "UNETLoader" in types and "LoraLoaderModelOnly" in types)
except Exception as e:
    check("示例工作流", False, e)

# 8. 压缩包本体里不能有 __pycache__/.pyc（导入会就地生成，所以查 zip 而不是查目录）
zip_path = os.environ.get("ZIP_PATH") or ""
if os.path.isfile(zip_path):
    import zipfile

    with zipfile.ZipFile(zip_path) as z:
        bad = [n for n in z.namelist() if "__pycache__" in n or n.endswith(".pyc")]
    check("压缩包本体无 __pycache__/.pyc", not bad, f"entries={len(z.namelist())}")
else:
    print("SKIP  未找到 zip，跳过包体检查")

# 9. 文档齐全
for name in ("README.md", "安装说明.md", "CHANGELOG.md", "LICENSE",
             "pyproject.toml", "requirements.txt", "00-先读我-安装说明.md"):
    check(f"文档 {name}", os.path.isfile(os.path.join(PKG_DIR, name)))

# 10. 不该出现的文件
check("没有 nsfw_tags.json（体积过大，前端走 API）",
      not os.path.isfile(os.path.join(PKG_DIR, "web", "nsfw_tags.json")))

print("\nRESULT:", "ALL OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
