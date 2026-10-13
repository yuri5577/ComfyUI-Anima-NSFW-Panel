# -*- coding: utf-8 -*-
"""SFW 模式自测：过滤正确性 / 预设豁免 / 负面替换 / 节点参数。"""
import importlib.util, os, sys, types

# --- 自定位（脚本在 <包>/tools/ 下）---
import os as _os
import sys as _sys
TOOLS_DIR = _os.path.dirname(_os.path.abspath(__file__))
PKG_ROOT = _os.path.dirname(TOOLS_DIR)
COMFY_ROOT = _os.environ.get("COMFY_ROOT") or _os.path.dirname(
    _os.path.dirname(_os.path.dirname(PKG_ROOT)))
PY_EXE = _sys.executable

sys.path.insert(0, r"COMFY_ROOT")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = PKG_ROOT
pkg=types.ModuleType("p"); pkg.__path__=[ROOT]; sys.modules["p"]=pkg
py=types.ModuleType("p.py"); py.__path__=[os.path.join(ROOT,"py")]; sys.modules["p.py"]=py; pkg.py=py
def load(n):
    s=importlib.util.spec_from_file_location("p.py."+n, os.path.join(ROOT,"py",n+".py"))
    m=importlib.util.module_from_spec(s); sys.modules["p.py."+n]=m; s.loader.exec_module(m); return m
load("translations"); load("character_store"); load("sfw")
tags=load("tags"); nodes=load("nodes"); pb=load("prompt_builder")
sfw=sys.modules["p.py.sfw"]

fails=[]
def ok(cond, label, extra=""):
    print(("OK   " if cond else "FAIL ") + label + (f"  {extra}" if extra else ""))
    if not cond: fails.append(label)

ok(not sfw.is_sfw(sfw.MODE_NSFW), "NSFW 模式判定正确（nsfw 不含 sfw 子串陷阱）")
ok(sfw.is_sfw(sfw.MODE_SFW), "SFW 模式判定正确")
ok(sfw.is_sfw("sfw") and sfw.is_sfw("safe") and sfw.is_sfw("全年龄"), "别名 sfw/safe/全年龄")
ok(not sfw.is_sfw("nsfw") and not sfw.is_sfw("NSFW"), "别名 nsfw 不被误判")

# 节点 INPUT_TYPES 里有 mode，且在 required 第一位之后
for name, cls in (("提示词面板", nodes.AnimaNsfwPromptBuilder),
                  ("负面构建器", nodes.AnimaNsfwNegativeBuilder)):
    it = cls.INPUT_TYPES()
    req = list(it["required"].keys())
    opt = list(it.get("optional", {}).keys())
    # mode 必须在 optional 里：放 required 会让 v1.6.0 之前的老工作流 400
    ok("mode" in opt and "mode" not in req,
       f"{name} 的 mode 在 optional（老工作流兼容）",
       f"required={req[:2]}... optional={opt[:2]}...")
    opts = it["optional"]["mode"]
    ok(list(opts[0]) == list(sfw.MODES), f"{name} mode 选项", str(list(opts[0])))

# 过滤正确性：一组露骨 + 一组正常
dirty = ("1girl, nsfw, nude, cum, ahegao, doggystyle, bondage, shibari, pussy, "
         "nipples, creampie, sex, fellatio, masturbating, spread legs, "
         "serafuku, pleated skirt, thighhighs, smile, blue archive, hatsune miku")
r_n = pb.compose_prompt(tags=dirty, intensity="all", quality_preset="best quality",
                        caption_enabled=True, mode=sfw.MODE_NSFW)
r_s = pb.compose_prompt(tags=dirty, intensity="all", quality_preset="best quality",
                        caption_enabled=True, mode=sfw.MODE_SFW)
kept_s = set(r_s["info"]["tags"])
ok(not (kept_s & {"nsfw","nude","cum","ahegao","doggystyle","bondage","shibari",
                  "pussy","nipples","creampie","sex","fellatio","masturbating",
                  "spread legs"}),
   "SFW 拦下全部露骨标签", f"拦下 {len(r_s['info']['dropped_by_sfw'])} 个")
ok({"serafuku","pleated skirt","thighhighs","smile","blue archive","hatsune miku",
    "1girl"} <= kept_s, "SFW 保留全部正常标签", ", ".join(sorted(kept_s))[:80])
ok("rating:safe" in r_s["prompt"] and "safe" in r_s["prompt"],
   "SFW 正向追加安全词", r_s["prompt"][:60])
ok("rating:safe" not in r_n["prompt"], "NSFW 不追加安全词")
ok(r_n["info"]["dropped_by_sfw"] == [], "NSFW 不做 SFW 过滤")
ok("all-ages" in r_s["info"]["caption"] or "wholesome" in r_s["info"]["caption"]
   or "modest" in r_s["info"]["caption"] or "family-friendly" in r_s["info"]["caption"],
   "SFW 描述换成全年龄收尾", r_s["info"]["caption"][-60:])
ok("nude" not in r_s["info"]["caption"].lower(), "SFW 描述不提裸露")

# 预设豁免
for zh, ts, want_keep in (
    ("芭蕾舞服", ["ballet","tutu","leotard","pantyhose","ballet slippers"], "leotard"),
    ("经典水手服", ["serafuku","pleated skirt","sailor collar","thighhighs"], "thighhighs"),
):
    rr = pb.compose_prompt(tags="1girl, solo", intensity="all", quality_preset="",
                           caption_enabled=False,
                           outfit_preset={"zh":zh,"tags":ts}, mode=sfw.MODE_SFW)
    ok(want_keep in rr["info"]["tags"], f"预设「{zh}」豁免 {want_keep}")

# 死库水：整体作为泳装被拦（这是有意的）
rr = pb.compose_prompt(tags="1girl", intensity="all", quality_preset="",
                       caption_enabled=False,
                       outfit_preset={"zh":"死库水","tags":["school swimsuit","one-piece swimsuit"]},
                       mode=sfw.MODE_SFW)
ok(not (set(rr["info"]["tags"]) & {"school swimsuit","one-piece swimsuit"}),
   "SFW 拦下死库水（泳装整体拦截）", str(rr["info"]["dropped_by_sfw"]))

# 负面
neg_n = pb.compose_negative(True, ["手部修复","NSFW安全"], mode=sfw.MODE_NSFW)["prompt"]
neg_s = pb.compose_negative(True, ["手部修复","NSFW安全"], mode=sfw.MODE_SFW)["prompt"]
ok(all(k in neg_n for k in ("child", "underage", "loli")),
   "NSFW 负面含未成年人安全词")
ok("censored" in neg_n and "censored" not in neg_s,
   "SFW 把「NSFW 安全」段换掉（不再要求打码 censored）")
ok("explicit" in neg_s and "ahegao" in neg_s, "SFW 负面换成全年龄反向词")
ok(len(neg_s) > len(neg_n), "SFW 负面更长（追加了安全段）")

# 标签库已注册 SFW 词
d = tags.as_dict()
ok(d["sfw"]["block_count"] > 200, "接口暴露 SFW 拦截词数", str(d["sfw"]["block_count"]))
ok(len(d["sfw"]["block_keys"]) == d["sfw"]["block_count"], "block_keys 与 block_count 一致")
ok(set(d["sfw"]["hidden_categories"]) == {"act","foreplay","solo","fluid"},
   "SFW 收起分类清单", str(d["sfw"]["hidden_categories"]))
for w in ("rating:safe","safe","general","nsfw"):
    ok(any(t["t"] == w for t in d["tags"]), f"标签库注册了 {w}")

# 轻小说分类
ok(d.get("light_novel_count") == 38, "轻小说 38 部", str(d.get("light_novel_count")))
groups = [g["id"] for g in d["copyright_groups"]]
ok("light_novel" in groups, "有 light_novel 分组", str(groups))
ln = [t for t in d["tags"] if t.get("g") == "light_novel_base"]
ok(len(ln) == 38, "轻小说共用 light_novel_base 互斥组", str(len(ln)))
ok("light_novel_base" != "copyright_base", "轻小说与游戏是两组（可同时选）")
for w in ("sword art online", "toaru majutsu no index", "overlord (maruyama)",
          "mushoku tensei", "kono subarashii sekai ni shukufuku wo!"):
    ok(any(t["t"] == w for t in ln), f"轻小说收录 {w}")
ok(len(ln) == len({t["t"].lower() for t in ln}), "轻小说无重复")

# 角色立绘数据
csx = __import__("json").load(open(
    r"{PKG_ROOT}\web\characters.json",
    encoding="utf-8"))
pv = (csx.get("meta") or {}).get("preview") or {}
ok(pv.get("enabled") and "animadex" in str(pv.get("base", "")),
   "角色库带立绘 URL 模板", str(pv.get("base", ""))[:60])

print()
print("RESULT:", "ALL OK" if not fails else f"{len(fails)} 项失败: {fails}")
sys.exit(0 if not fails else 1)