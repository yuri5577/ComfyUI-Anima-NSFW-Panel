# tools —— 离线测试

三套测试，**都不需要启动 ComfyUI、不联网**（fetch 全走桩）。

## 1. 面板 JS 冒烟测试

把面板 JS 用 Node 桩环境真跑一遍：模块加载 → 注册扩展 → `onNodeCreated` →
点「打开面板」→ 面板浮层是否挂上 → 点里面每个按钮/分类 → 画布回调 →
种子推送 → 剧情套用 → 角色立绘。

```bash
node tools/animansfw_panel_smoke.mjs            # 现代前端
node tools/animansfw_panel_smoke.mjs --legacy   # 剥掉 addDOMWidget / localStorage / rAF
node tools/animansfw_panel_smoke.mjs --oldfe    # 老前端契约（1.12.8）
```

## 2. SFW 双模式自测（需要 ComfyUI 的 python）

```bash
# 需要能 import torch（因为要加载 nodes.py）
D:\ComfyUI-aki-v2\python\python.exe tools/animansfw_sfw_selftest.py
```

或用环境变量指定 ComfyUI 根：

```bash
COMFY_ROOT=/path/to/ComfyUI python tools/animansfw_sfw_selftest.py
```

## 3. 打包/发布前验证

```bash
python tools/animansfw_verify_zip.py [解压出来的包目录]
```

会跑上面两个 + 剧情全库 198 组体检（11 线 × 6 拍 × 全部主角）。

## 重新生成 fixture

改了标签库或剧情之后，重新生成测试数据：

```bash
python tools/animansfw_make_fixture.py
```

## 重新生成角色库

```bash
python tools/animansfw_import_characters.py
```

## 4. 真浏览器测试（需要先启动 ComfyUI）

用 headless Chrome + CDP 在真实页面里跑，需要本机有 Chrome 或 Edge。

```bash
node tools/animansfw_browser_e2e.mjs     # 开面板 / 点标签 / 防抖 / 截图
node tools/animansfw_browser_views.mjs   # 每个视图点一遍 + 剧情套用
```

会启动独立的 headless 实例（独立临时 profile），**不影响你自己开着的浏览器**。
两个脚本都会把截图写到当前工作目录（`animansfw_panel_screenshot.png` /
`animansfw_view_*.png`），可以直接看面板长什么样。

## 5. 服装随机约束测试（离线）

```bash
node tools/animansfw_random_test.mjs
```

跑 4000 次随机配饰，统计四类违规（同槽位重复 / 重复标签 / 与预设同类冲突 /
色系不符），并验证游戏 COS 预设的标签都在标签库里。四项都应为 0。

## 6. 服装视图真浏览器测试（需要先启动 ComfyUI）

```bash
node tools/animansfw_browser_outfit.mjs
```

测分组按钮、随机 30 次（含分组内随机）、配饰开关、切换性能、搜索过滤。
会截图到 `animansfw_outfit_view.png`。

## 7. 作品点击流程（需要先启动 ComfyUI）

```bash
node tools/animansfw_browser_works.mjs
```

测侧栏作品列表是否合并了角色库的 `copies`（`封印者` 这类作品必须在列表里）、
点作品后侧栏是否还在、网格是否铺出该作品的角色卡、「显示更多」是否可用。

> ⚠️ 改动作品相关逻辑时**务必拿一个只在角色库里、不是版权标签的作品测**
> （例如 `封印者`）。只测「原神 / 碧蓝航线」这类版权标签作品是发现不了问题的
> —— 它们一直正常。

## 8. 服装分类（离线，不用启动 ComfyUI）

改完 `py/outfit_groups.py` 的 `RULE_GROUPS` 后：

```bash
python tools/animansfw_verify_zip.py     # 分组数 / 分布均衡 / 无空组
node tools/animansfw_browser_outfit.mjs  # 真浏览器：分组按钮 + 组内随机
```

> ⚠️ 两条防退化断言：**最大组 < 15%**、**没有空组**。
> 原来「服装库·性感暴露」一组就占 160/518（31%），等于没分类。

## 9. 动作 / 视角快速条（需要先启动 ComfyUI）

```bash
node tools/animansfw_browser_actview.mjs
```

测面板顶部那三行（动作 / 腿·手 / 视角）：写入节点、组内互斥、跨组叠加、
chip 选中态、覆盖视图里隐藏、侧栏两个新分类。

> ⚠️ 定位容器时**别按文字找** —— `querySelectorAll("div")` 返回文档顺序
> （外层在前），overlay 祖先的文字里也含「腿/手」，会抓到最外层。
> 用 `d.style.padding === "6px 10px"` 精确定位。
