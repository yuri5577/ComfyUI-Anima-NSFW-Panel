# -*- coding: utf-8 -*-
"""Anima Modulation Guidance（调制引导）— ComfyUI 模型补丁实现。

原理（Starodubcev et al., "Rethinking Global Text Conditioning in Diffusion
Transformers", ICLR 2026；Anima 侧实现见 sorryhyun/anima_lora 的
``docs/inference/mod-guidance.md``）：

Anima 的 AdaLN shift/scale/gate 原本只依赖 timestep，文本只走 cross-attention。
调制引导额外训练了一个小 MLP（``pooled_text_proj``，约 8M 参数）把
``max_pool(crossattn_emb)`` 投影进 timestep embedding 空间，于是可以在
**调制空间**里沿「质量正方向 − 质量负方向」做一次引导，与 CFG（噪声空间）正交、
可叠加。

实现要点（与上游 ComfyUI-Spectrum-KSampler 保持一致的做法）：

1. ``t_embedding_norm`` 上挂 forward hook，把「基础投影」
   ``proj(pool(条件文本))`` 加到 timestep embedding 上（cond / uncond 各一份）。
2. 每个 transformer block 之前挂 pre-hook，把 ``w(ℓ) * delta_unit`` 加到
   ``t_embedding`` 参数上，其中 ``delta_unit = proj(quality_tags) − proj(quality_neg)``，
   ``w(ℓ)`` 由 start/end/taper 组成的分段调度给出。
3. 用 ``WrappersMP.APPLY_MODEL`` 包装器在每次前向之前写入这两个量，
   在 ``torch.compile`` 边界之外，保证编译缓存不被破坏。

本实现只依赖 ``comfy``、``torch``，不改动任何 ComfyUI 核心文件，也不与
Spectrum-KSampler 的节点冲突（函数名与 wrapper key 均带 ``animansfw`` 前缀）。
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import torch

import comfy.patcher_extension
import folder_paths

try:  # ComfyUI 0.39 里 model_patches 目录一定存在
    _MODEL_PATCH_DIRS = list(folder_paths.get_folder_paths("model_patches"))
except Exception:  # pragma: no cover
    _MODEL_PATCH_DIRS = []

logger = logging.getLogger("AnimaNSFW.ModGuidance")

MOD_STATE_KEY = "animansfw_mod_guidance_state"
MOD_APPLY_WRAPPER_KEY = "animansfw_mod_guidance_apply"

DEFAULT_ADAPTER_FILENAME = "pooled_text_proj-0611.safetensors"

# 质量轴正/负基准（与上游默认一致，属于 Anima 文本编码器的分布内词）
DEFAULT_QUALITY_TAGS = "absurdres, masterpiece, score_9"
DEFAULT_QUALITY_NEG = "worst quality, low quality, score_1"
# 基础投影用的提示词：AdaIN 调制路径需要「与画面内容同分布」的文本特征。
# 上游实现用的是用户正面提示词的池化投影，我们没有办法在图层面拿到它，
# 因此让用户给一句能概括画面的短描述（不需要和主提示词完全一致）。
DEFAULT_BASE_PROMPT = "1girl, solo, nude, large breasts, on bed, looking at viewer, masterpiece, best quality, absurdres"

PROJ_KEYS = ("0.weight", "0.bias", "2.weight", "2.bias")

# 名字 -> (w, start_layer, end_layer, taper, taper_scale, final_w)
# 上游 profile 参数原样保留（step_i8_skip27 / step_i14 / uniform_w3），
# 另外给了两档更轻/更重的档位。适配器与模型/LoRA 的搭配会明显影响体感，
# 建议先用 light 档对比，再决定要不要加码。
PROFILES = {
    "light_w1.5（先试这个）": (1.5, 8, 27, 0, 0.25, 0.0),
    "step_i8_skip27（上游推荐 w=3）": (3.0, 8, 27, 0, 0.25, 0.0),
    "step_i14（安全，防人体崩坏）": (3.0, 14, -1, 0, 0.25, 0.0),
    "strong_w5（强烈，易过曝）": (5.0, 8, 27, 0, 0.25, 0.0),
    "uniform_w3（旧版均匀，慎用）": (3.0, 0, -1, 0, 0.25, 0.0),
    "自定义": (3.0, 8, 27, 0, 0.25, 0.0),
}

_ADAPTER_CPU_CACHE: Dict[str, Dict[str, torch.Tensor]] = {}
_ADAPTER_TYPED_CACHE: Dict[str, Dict[str, torch.Tensor]] = {}


# ---------------------------------------------------------------------------
# 适配器（pooled_text_proj）加载
# ---------------------------------------------------------------------------

def list_adapters() -> List[str]:
    names: List[str] = []
    for d in _MODEL_PATCH_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in files:
                if f.endswith((".safetensors", ".sft", ".pt", ".ckpt", ".bin")):
                    names.append(os.path.relpath(os.path.join(root, f), d).replace("\\", "/"))
    return sorted(set(names)) or [DEFAULT_ADAPTER_FILENAME]


def resolve_adapter(name: str) -> str:
    if name and os.path.isfile(name):
        return os.path.abspath(name)
    for d in _MODEL_PATCH_DIRS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    # 回退到默认文件名
    for d in _MODEL_PATCH_DIRS:
        cand = os.path.join(d, DEFAULT_ADAPTER_FILENAME)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    raise FileNotFoundError(
        f"找不到调制引导适配器 {name!r}；请把 {DEFAULT_ADAPTER_FILENAME} 放进 "
        f"ComfyUI/models/model_patches/ 目录。已扫描: {_MODEL_PATCH_DIRS}"
    )


def _load_adapter_cpu(path: str) -> Dict[str, torch.Tensor]:
    path = os.path.abspath(path)
    cached = _ADAPTER_CPU_CACHE.get(path)
    if cached is not None:
        return cached

    from safetensors.torch import load_file as safe_load

    raw = safe_load(path, device="cpu")
    keys = list(PROJ_KEYS)
    if "sigma_film.weight" in raw:
        keys += ["sigma_film.weight"]
        if "sigma_film.bias" in raw:
            keys += ["sigma_film.bias"]
    missing = [k for k in PROJ_KEYS if k not in raw]
    if missing:
        raise RuntimeError(f"{path} 不是有效的 pooled_text_proj 文件，缺少 {missing}")
    state = {k: raw[k].detach().float().cpu().contiguous() for k in keys}
    _ADAPTER_CPU_CACHE[path] = state
    return state


def _get_adapter_typed(path: str, device, dtype) -> Dict[str, torch.Tensor]:
    key = (os.path.abspath(path), str(device), str(dtype))
    hit = _ADAPTER_TYPED_CACHE.get(key)
    if hit is not None:
        return hit
    typed = {k: v.to(device=device, dtype=dtype) for k, v in _load_adapter_cpu(path).items()}
    _ADAPTER_TYPED_CACHE[key] = typed
    return typed


def _project(pooled, state, film_w=None, film_b=None, t_emb=None, out_dtype=None):
    """Linear → [σ-FiLM] → SiLU → Linear。"""
    w_in, b_in = state["0.weight"], state["0.bias"]
    h = torch.nn.functional.linear(pooled.to(w_in.dtype), w_in, b_in)
    if t_emb is not None and film_w is not None:
        film = torch.nn.functional.linear(t_emb.to(film_w.dtype), film_w, film_b)
        scale, shift = film.chunk(2, dim=-1)
        h = h * (1.0 + scale) + shift
    h = torch.nn.functional.silu(h)
    w_out, b_out = state["2.weight"], state["2.bias"]
    out = torch.nn.functional.linear(h.to(w_out.dtype), w_out, b_out)
    return out if out_dtype is None else out.to(out_dtype)


def build_schedule(num_blocks: int, w: float, start_layer: int, end_layer: int,
                   taper: int = 0, taper_scale: float = 0.25) -> List[float]:
    end = num_blocks if end_layer < 0 else min(int(end_layer), num_blocks)
    start = max(0, min(int(start_layer), end))
    sched = [0.0] * num_blocks
    w = float(w)
    for i in range(start, end):
        sched[i] = w
    if taper > 0 and end > start:
        taper_start = max(start, end - int(taper))
        tw = w * float(taper_scale)
        for i in range(taper_start, end):
            sched[i] = tw
    return sched


def _compute_t_emb(dit, t):
    """复现 DiT 里 norm 之后的 timestep embedding（σ-FiLM 用），返回 (B, C)。"""
    te = dit.t_embedder
    wdt = next((p.dtype for p in te[1].parameters() if p.dtype.is_floating_point), t.dtype)
    t_bt = t.reshape(-1, 1) if t.ndim == 1 else t
    emb = te[1](te[0](t_bt).to(wdt))
    if isinstance(emb, (tuple, list)):
        emb = emb[0]
    emb = dit.t_embedding_norm(emb)
    if emb.ndim == 3:
        emb = emb[:, 0, :]
    return emb


# ---------------------------------------------------------------------------
# 运行期状态与 hook
# ---------------------------------------------------------------------------

class _BlockState:
    __slots__ = ("delta_unit", "schedule", "final_w")

    def __init__(self, delta_unit, schedule, final_w):
        self.delta_unit = delta_unit
        self.schedule = schedule
        self.final_w = float(final_w)


class ModGuidanceState:
    """每个 MODEL 补丁一份；前向时惰性预计算一次投影。"""

    def __init__(self, adapter_path, w, tag_raw, base_raw, neg_raw, qneg_raw,
                 dit, start_layer, end_layer, taper, taper_scale, final_w):
        self.adapter_path = adapter_path
        self.w = float(w)
        self.tag_raw = tag_raw
        self.base_raw = base_raw
        self.neg_raw = neg_raw
        self.qneg_raw = qneg_raw
        self.dit = dit
        self.start_layer = int(start_layer)
        self.end_layer = int(end_layer)
        self.taper = int(taper)
        self.taper_scale = float(taper_scale)
        self.final_w = float(final_w)

        self.cond_combined = None
        self.uncond_combined = None
        self.delta_unit = None
        self.per_block_schedule = None
        self.has_film = False
        self.adapter_state = None
        self.base_pooled = self.tag_pooled = self.neg_pooled = self.qneg_pooled = None
        self.info = {}

    # -- 编码 ---------------------------------------------------------------
    def _encode_pool(self, raw, device, dtype):
        adapted = self.dit.preprocess_text_embeds(
            raw.unsqueeze(0).to(device=device, dtype=dtype), None, None
        )
        return adapted.max(dim=1).values.to(device)

    def ensure_precomputed(self, device, dtype):
        if self.cond_combined is not None:
            return
        state = _get_adapter_typed(self.adapter_path, device, dtype)
        with torch.no_grad():
            base_pooled = self._encode_pool(self.base_raw, device, dtype)
            tag_pooled = self._encode_pool(self.tag_raw, device, dtype)
            qneg_pooled = (
                base_pooled if self.qneg_raw is None
                else self._encode_pool(self.qneg_raw, device, dtype)
            )
            proj_base = _project(base_pooled, state)
            proj_tag = _project(tag_pooled, state)
            proj_qneg = proj_base if self.qneg_raw is None else _project(qneg_pooled, state)

            # 基础投影对 cond / uncond 行给同一个值，使 CFG 差值保持干净；
            # 训练时该注入就是与文本内容无关的加性项。
            self.cond_combined = proj_base.detach()
            self.uncond_combined = proj_base.detach()
            # 质量引导方向 = proj(质量正词) − proj(质量负词)
            self.delta_unit = (proj_tag - proj_qneg).detach()

            self.has_film = "sigma_film.weight" in state
            if self.has_film:
                self.adapter_state = _get_adapter_typed(self.adapter_path, device, torch.float32)
                self.base_pooled = base_pooled.detach()
                self.tag_pooled = tag_pooled.detach()
                self.qneg_pooled = (
                    base_pooled.detach() if self.qneg_raw is None else qneg_pooled.detach()
                )

        self.per_block_schedule = build_schedule(
            len(self.dit.blocks), self.w, self.start_layer, self.end_layer,
            self.taper, self.taper_scale,
        )
        self.info = {
            "w": self.w,
            "start_layer": self.start_layer,
            "end_layer": self.end_layer,
            "final_w": self.final_w,
            "blocks": len(self.dit.blocks),
            "sigma_film": bool(self.has_film),
            "delta_norm": float(self.delta_unit.float().norm().item()),
        }
        logger.info("调制引导已就绪: %s", self.info)


def _t_emb_hook(module, _inputs, output):
    delta = getattr(module, "_animansfw_mod_delta", None)
    if delta is None:
        return output
    return output + delta


def _ensure_t_emb_hook(dit) -> None:
    t_norm = dit.t_embedding_norm
    if getattr(t_norm, "_animansfw_hook_installed", False):
        return
    t_norm._animansfw_mod_delta = None
    t_norm.register_forward_hook(_t_emb_hook)
    t_norm._animansfw_hook_installed = True


def _ensure_block_hooks(dit) -> None:
    if getattr(dit, "_animansfw_block_hooks_installed", False):
        return

    def make_block_prehook(idx):
        def _prehook(_module, args, kwargs):
            st = getattr(dit, "_animansfw_block_state", None)
            if st is None or st.schedule is None or idx >= len(st.schedule):
                return None
            w_l = st.schedule[idx]
            if w_l == 0.0 or len(args) < 2:
                return None
            t_emb = args[1]
            delta = st.delta_unit
            if delta.device != t_emb.device or delta.dtype != t_emb.dtype:
                delta = delta.to(device=t_emb.device, dtype=t_emb.dtype)
                st.delta_unit = delta
            return (args[0], t_emb + (w_l * delta).unsqueeze(1)) + tuple(args[2:]), kwargs

        return _prehook

    def final_prehook(_module, args, kwargs):
        st = getattr(dit, "_animansfw_block_state", None)
        if st is None or st.final_w == 0.0 or len(args) < 2:
            return None
        t_emb = args[1]
        delta = st.delta_unit
        if delta.device != t_emb.device or delta.dtype != t_emb.dtype:
            delta = delta.to(device=t_emb.device, dtype=t_emb.dtype)
            st.delta_unit = delta
        return (args[0], t_emb + (st.final_w * delta).unsqueeze(1)) + tuple(args[2:]), kwargs

    for idx, blk in enumerate(dit.blocks):
        blk.register_forward_pre_hook(make_block_prehook(idx), with_kwargs=True)
    dit.final_layer.register_forward_pre_hook(final_prehook, with_kwargs=True)
    dit._animansfw_block_state = None
    dit._animansfw_block_hooks_installed = True


def _mod_apply_wrapper(executor, *args, **kwargs):
    """APPLY_MODEL 包装器：在编译边界外写入基础投影与分块调度。"""
    transformer_options = (
        args[5] if len(args) > 5 and isinstance(args[5], dict)
        else kwargs.get("transformer_options", {})
    )
    st = transformer_options.get(MOD_STATE_KEY)
    if st is None:
        return executor(*args, **kwargs)

    x = args[0]
    device = x.device
    model = executor.class_obj
    try:
        dtype = model.get_dtype_inference()
    except Exception:
        dtype = x.dtype

    dit = getattr(model, "diffusion_model", st.dit)
    if dit is None:
        return executor(*args, **kwargs)
    if st.dit is not dit:
        logger.info("调制引导重新绑定到当前活跃 diffusion_model")
        st.dit = dit
        st.cond_combined = None
    _ensure_t_emb_hook(dit)
    _ensure_block_hooks(dit)
    st.ensure_precomputed(device, dtype)
    if not getattr(dit, "_animansfw_logged", False):
        logger.info(
            "调制引导生效检查: dtype=%s blocks=%s delta_norm=%.5f schedule_nonzero=%s",
            dtype, len(dit.blocks), float(st.delta_unit.float().norm().item()),
            sum(1 for v in (st.per_block_schedule or []) if v),
        )
        dit._animansfw_logged = True

    cond_or_uncond = transformer_options.get("cond_or_uncond", [0])

    combined = None
    delta_unit_typed = None
    if st.has_film and st.adapter_state is not None:
        try:
            t_emb = _compute_t_emb(dit, args[1].to(device))
            state = st.adapter_state
            film_w = state.get("sigma_film.weight")
            film_b = state.get("sigma_film.bias")
            pieces = []
            for i, cou in enumerate(cond_or_uncond):
                ti = t_emb[i:i + 1] if t_emb.shape[0] > i else t_emb[:1]
                pooled_i = st.base_pooled
                pieces.append(_project(pooled_i, state, film_w, film_b, ti, dtype))
            combined = torch.cat(pieces, dim=0)
            t0 = t_emb[:1]
            delta_unit_typed = (
                _project(st.tag_pooled, state, film_w, film_b, t0, dtype)
                - _project(st.qneg_pooled, state, film_w, film_b, t0, dtype)
            )
        except Exception as exc:  # 退回 σ-flat
            combined = None
            if not getattr(dit, "_animansfw_film_warned", False):
                logger.warning("σ-FiLM 投影回退到 σ-flat: %s", exc)
                dit._animansfw_film_warned = True

    if combined is None:
        cond_c = st.cond_combined.to(device=device, dtype=dtype)
        uncond_c = st.uncond_combined.to(device=device, dtype=dtype)
        combined = torch.cat(
            [uncond_c if cou else cond_c for cou in cond_or_uncond], dim=0
        )
        delta_unit_typed = st.delta_unit.to(device=device, dtype=dtype)

    t_norm = dit.t_embedding_norm
    t_norm._animansfw_mod_delta = combined.unsqueeze(1)
    dit._animansfw_block_state = _BlockState(
        delta_unit=delta_unit_typed,
        schedule=st.per_block_schedule,
        final_w=st.final_w,
    )
    dit._animansfw_last_info = st.info
    try:
        return executor(*args, **kwargs)
    finally:
        t_norm._animansfw_mod_delta = None
        dit._animansfw_block_state = None


# ---------------------------------------------------------------------------
# 对外入口：给 MODEL 打补丁
# ---------------------------------------------------------------------------

def _encode_tokens(clip, text: str) -> torch.Tensor:
    tokens = clip.tokenize(text)
    out = clip.encode_from_tokens(tokens, return_pooled=True, return_dict=True)
    cond = out["cond"]
    raw = cond[0].detach().cpu() if cond.ndim == 3 else cond.detach().cpu()
    return raw


def apply_mod_guidance(
    model,
    clip,
    adapter_name: str,
    quality_tags: str = DEFAULT_QUALITY_TAGS,
    quality_neg: str = DEFAULT_QUALITY_NEG,
    base_prompt: str = DEFAULT_BASE_PROMPT,
    w: float = 3.0,
    start_layer: int = 8,
    end_layer: int = 27,
    taper: int = 0,
    taper_scale: float = 0.25,
    final_w: float = 0.0,
):
    """给 ``model`` 打上调制引导补丁，返回新的 MODEL。"""
    if model is None:
        raise ValueError("调制引导需要一个 MODEL 输入")
    if clip is None:
        raise ValueError("调制引导需要 CLIP 输入（用于编码质量提示词）")

    adapter_path = resolve_adapter(adapter_name)
    model_clone = model.clone()
    dm = model_clone.model.diffusion_model

    model_channels = getattr(dm, "model_channels", None)
    if model_channels is None:
        raise RuntimeError("当前模型的 diffusion_model 缺少 model_channels，不是 Anima 模型？")
    if not hasattr(dm, "t_embedding_norm") or not hasattr(dm, "blocks"):
        raise RuntimeError("当前模型结构不匹配（缺少 t_embedding_norm / blocks），无法使用调制引导。")

    adapter_cpu = _load_adapter_cpu(adapter_path)
    if adapter_cpu["0.weight"].shape[0] != int(model_channels):
        raise RuntimeError(
            f"适配器输出维度 {adapter_cpu['0.weight'].shape[0]} 与模型 model_channels "
            f"{model_channels} 不一致，请换用匹配的 pooled_text_proj 权重。"
        )

    q_tags = (quality_tags or "").strip() or DEFAULT_QUALITY_TAGS
    q_neg = (quality_neg or "").strip()
    q_base = (base_prompt or "").strip() or DEFAULT_BASE_PROMPT

    base_raw = _encode_tokens(clip, q_base)
    tag_raw = _encode_tokens(clip, q_tags)
    if q_neg:
        qneg_raw = _encode_tokens(clip, q_neg)
        neg_raw = qneg_raw
    else:
        # 留空 = 复用基础投影作为质量负基准（此时引导方向只有正向分量）
        qneg_raw = None
        neg_raw = base_raw

    state = ModGuidanceState(
        adapter_path=adapter_path,
        w=w,
        tag_raw=tag_raw,
        base_raw=base_raw,
        neg_raw=neg_raw,
        qneg_raw=qneg_raw,
        dit=dm,
        start_layer=start_layer,
        end_layer=end_layer,
        taper=taper,
        taper_scale=taper_scale,
        final_w=final_w,
    )
    state.info = {"adapter": os.path.basename(adapter_path), "quality_tags": q_tags,
                  "quality_neg": q_neg or "(无，仅正向)", "base_prompt": q_base}

    _ensure_t_emb_hook(dm)
    _ensure_block_hooks(dm)

    try:
        model_clone.remove_wrappers_with_key(
            comfy.patcher_extension.WrappersMP.APPLY_MODEL, MOD_APPLY_WRAPPER_KEY
        )
    except Exception:
        pass

    model_clone.model_options.setdefault("transformer_options", {})[MOD_STATE_KEY] = state
    model_clone.add_wrapper_with_key(
        comfy.patcher_extension.WrappersMP.APPLY_MODEL,
        MOD_APPLY_WRAPPER_KEY,
        _mod_apply_wrapper,
    )

    logger.info(
        "调制引导补丁已应用: adapter=%s, w=%s, blocks=[%s, %s), final_w=%s",
        os.path.basename(adapter_path), w, start_layer, end_layer, final_w,
    )
    return model_clone, state
