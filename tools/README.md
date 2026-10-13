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
