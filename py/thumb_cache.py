# -*- coding: utf-8 -*-
"""缩略图本地缓存。

## 要解决什么

面板里的预览图全部来自**境外 CDN**：

| 资源 | 数量 | 来源 |
|---|---|---|
| 服装预设预览 | 430 | `cdn.jsdelivr.net` |
| 姿势参考预览 | 297 | `cdn.jsdelivr.net` |
| 角色立绘 | 8017 | `blobs.animadex.net` |

用户反馈「要挂上 VPN 才能打开」。实测这几个域名**直连是通的**，但：

* 每张图都是**独立的境外请求**，首屏一两百张 = 一两百次跨境握手，很慢
* jsDelivr 的 `gh` 路径在国内**经常被 DNS 污染 / 按 IP 限速**，时好时坏
* 完全没网（或 CDN 挂了）时，整面板全是「无图」

## 做法：后端代理 + 磁盘缓存

前端不再直接请求 CDN，而是请求**本地 ComfyUI**：

    /anima_nsfw/thumb?u=<原始URL>

后端逻辑：

1. 命中磁盘缓存 → 直接吐文件（只走 127.0.0.1，毫秒级，离线也能用）
2. 未命中 → 下载 → **校验确实是图片** → 落盘 → 吐给前端
3. 下载失败 → 返回一个 1×1 透明 PNG + 标 `miss`，前端显示占位，
   并且**不缓存失败结果**（下次还有机会补上）

所以：用户只要**成功加载过一次**，之后就永远走本地。

## 安全考虑

* **白名单域名**：只有下面 `ALLOWED_HOSTS` 里的域能被代理，
  否则这个接口会变成任意 URL 的开放代理（SSRF 风险）
* 只允许 http/https、只允许图片后缀
* 单文件大小上限，防止把磁盘塞满
* 落盘前校验 magic bytes —— CDN 出错时可能返回 HTML 错误页，
  直接存下来会让前端一直显示破图

## 缓存位置

优先 `<ComfyUI user 目录>/anima_nsfw_thumb_cache/`（跟着用户数据走），
取不到就退回插件目录下的 `.thumb_cache/`。可用环境变量
`ANIMANSFW_THUMB_CACHE` 覆盖。
"""
from __future__ import annotations

import http.client
import hashlib
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

# 允许被代理的域名（**必须白名单**，否则就是开放代理）
ALLOWED_HOSTS = (
    "cdn.jsdelivr.net",
    "fastly.jsdelivr.net",
    "gcore.jsdelivr.net",
    "testingcf.jsdelivr.net",
    "blobs.animadex.net",
)

MAX_BYTES = 12 * 1024 * 1024          # 单文件上限 12 MB
CONNECT_TIMEOUT = 8                    # 建连超时（连不上要快速失败，别耗满读超时）
READ_TIMEOUT = 30                      # 读超时（图最大 1MB 多，够用）
RETRIES = 2                            # 失败重试次数（404 不重试）
MAX_WARM = 4000                        # 一次预热最多接多少条
MAX_WORKERS = 8                        # 并发下载线程数（配合连接复用才有意义）

# 图片 magic bytes —— 落盘前必须对上，避免把 HTML 错误页当图片存下来
_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"BM", ".bmp"),
)

_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="animansfw-thumb")
_LOCK = threading.Lock()
_STATS = {"hit": 0, "miss": 0, "download": 0, "fail": 0, "retry": 0,
          "bytes": 0}
_STATS_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# keep-alive 连接池（**每线程独立**）
#
# 为什么不用 urllib：它**每个请求都新建连接**，小图（8-10KB）的 TCP + TLS
# 握手成本比传数据还大。实测 600-900ms/张，其中大部分是握手；
# 复用连接后降到 185-240ms/张。
#
# ⚠️ 为什么用 threading.local 而不是"全局按域名缓存一条"：
#    `http.client.HTTPConnection` **不是线程安全的**。第一版用全局字典缓存，
#    8 并发时 150 张里 129 张失败，错误全是
#    `CannotSendRequest: Request-sent` / `ResponseNotReady: Idle`
#    —— 多个线程抢同一条连接，状态机错乱。串行时完全正常，所以只看串行测不出来。
#
#    改成每线程各持一组连接即可。下载任务在**一个线程内**跑完
#    （`run_in_executor` / 线程池），所以"建连接"和"用连接"永远同线程。
# ---------------------------------------------------------------------------
_POOL_TLS = threading.local()
_POOL_MAX_IDLE = 90.0          # 闲置超过 90 秒的连接丢掉（服务器多半也关了）


def _pool() -> Dict[str, Tuple[http.client.HTTPConnection, float]]:
    d = getattr(_POOL_TLS, "conns", None)
    if d is None:
        d = {}
        _POOL_TLS.conns = d
    return d


def _conn_key(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def _get_conn(scheme: str, host: str, port: int) -> http.client.HTTPConnection:
    key = _conn_key(scheme, host, port)
    now = time.time()
    pool = _pool()
    hit = pool.get(key)
    if hit is not None:
        conn, ts = hit
        if now - ts < _POOL_MAX_IDLE:
            pool[key] = (conn, now)
            return conn
        try:
            conn.close()
        except Exception:
            pass
        pool.pop(key, None)
    if scheme == "https":
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(
            host, port, timeout=CONNECT_TIMEOUT, context=ctx)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=CONNECT_TIMEOUT)
    pool[key] = (conn, now)
    return conn


def _drop_conn(scheme: str, host: str, port: int) -> None:
    """连接坏了就丢掉，下次重建（keep-alive 复用必然会遇到服务端主动关）"""
    pool = _pool()
    hit = pool.pop(_conn_key(scheme, host, port), None)
    if hit is not None:
        try:
            hit[0].close()
        except Exception:
            pass


def close_pool() -> None:
    """关掉**当前线程**的连接（每线程独立，所以只能关自己那批）"""
    pool = _pool()
    conns = list(pool.values())
    pool.clear()
    for conn, _ts in conns:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 目录
# ---------------------------------------------------------------------------

def cache_dir() -> str:
    """缓存根目录（自动创建）。"""
    env = os.environ.get("ANIMANSFW_THUMB_CACHE", "").strip()
    if env:
        root = env
    else:
        root = ""
        # 跟着 ComfyUI 的用户目录走
        try:
            import folder_paths  # type: ignore
            base = getattr(folder_paths, "get_user_directory", None)
            if callable(base):
                root = os.path.join(str(base()), "anima_nsfw_thumb_cache")
            elif getattr(folder_paths, "base_path", None):
                root = os.path.join(str(folder_paths.base_path), "user",
                                    "anima_nsfw_thumb_cache")
        except Exception:
            root = ""
        if not root:
            root = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), ".thumb_cache")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception:
        pass
    return root


def _safe_stem(text: str, limit: int = 70) -> str:
    """把 URL 里的文件名清成安全的可读名字（便于人工翻缓存目录）。"""
    text = urllib.parse.unquote(str(text or ""))
    text = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", text)
    text = re.sub(r"\s+", "_", text).strip("._")
    if len(text) > limit:
        text = text[:limit]
    return text or "img"


def cache_path(url: str) -> str:
    """URL → 缓存文件路径（两级：可读文件名 + 短哈希防同名冲突）。"""
    u = str(url or "")
    parsed = urllib.parse.urlparse(u)
    raw_name = os.path.basename(parsed.path) or "img"
    # animadex 的文件名是 `角色名, 作品名.webp`（已 URL 编码），解出来才好读
    stem, ext = os.path.splitext(_safe_stem(raw_name))
    ext = ext.lower()
    if ext not in (".webp", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".avif"):
        ext = ".img"
    digest = hashlib.sha1(u.encode("utf-8")).hexdigest()[:12]
    sub = digest[:2]
    d = os.path.join(cache_dir(), sub)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, f"{stem}.{digest}{ext}")


# ---------------------------------------------------------------------------
# 白名单与校验
# ---------------------------------------------------------------------------

def url_allowed(url: str) -> Tuple[bool, str]:
    """检查 URL 是否可以被代理。返回 (是否允许, 原因)。"""
    try:
        p = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False, "URL 解析失败"
    if p.scheme not in ("http", "https"):
        return False, f"协议不允许：{p.scheme}"
    host = (p.hostname or "").lower()
    if not host:
        return False, "缺少主机名"
    if host not in ALLOWED_HOSTS:
        return False, f"域名不在白名单：{host}"
    return True, ""


def _sniff_image(data: bytes) -> Optional[str]:
    """按 magic bytes 判断是不是图片，返回推测的扩展名。"""
    if not data or len(data) < 12:
        return None
    for magic, ext in _MAGIC:
        if data.startswith(magic):
            return ext
    # WEBP: RIFF....WEBP
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    # AVIF / HEIF: ....ftypavif / ftypheic
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"avif", b"avis"):
            return ".avif"
        if brand in (b"heic", b"heix", b"mif1"):
            return ".heic"
    # SVG（文本）—— jsDelivr 上可能有，但预览图不该是 SVG，直接拒绝更安全
    return None


def _content_type_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp",
        ".avif": "image/avif", ".heic": "image/heic",
    }.get(ext, "application/octet-stream")


def _bump(key: str, n: int = 1) -> None:
    with _STATS_LOCK:
        _STATS[key] = _STATS.get(key, 0) + n


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------

_UA = "animansfw-thumb-cache/1.1 (+local ComfyUI panel)"


def _proxy_for(url: str) -> Optional[str]:
    """要走的代理（默认不走；环境变量可选）。

    ⚠️ 故意**不读** `HTTP_PROXY`/`HTTPS_PROXY`：缓存的目的就是
    "一次下好、之后本地读"，默认直连少一跳。用户环境必须走代理时设
    `ANIMANSFW_THUMB_PROXY`。
    """
    p = os.environ.get("ANIMANSFW_THUMB_PROXY", "").strip()
    return p or None


def _download_once(url: str) -> Tuple[Optional[bytes], str, bool]:
    """下载一次。返回 (数据, 错误, 是否值得重试)。不写盘。

    走连接池；连接类错误（复用了被服务端关掉的连接）会丢掉连接并标记可重试。
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    proxy = _proxy_for(url)
    if proxy:
        # 走代理时用 urllib（代理 CONNECT 隧道，连接复用收益不大）
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA, "Referer": "https://github.com/",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        })
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        try:
            with opener.open(req, timeout=READ_TIMEOUT) as r:
                data = r.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}", e.code >= 500
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}", True
        return _validate(data)

    headers = {
        "User-Agent": _UA,
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://github.com/",
        "Connection": "keep-alive",
    }
    try:
        conn = _get_conn(scheme, host, port)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        status = resp.status
        if status == 200:
            data = resp.read(MAX_BYTES + 1)
        else:
            resp.read(256)
            data = b""
        # 连接要放回池里复用，所以必须读干净
        if status == 200 and len(data) <= MAX_BYTES:
            return _validate(data)
        if status in (301, 302, 303, 307, 308):
            loc = resp.getheader("Location") or ""
            if loc:
                _drop_conn(scheme, host, port)
                return _download_once(urllib.parse.urljoin(url, loc))
        return None, f"HTTP {status}", status >= 500
    except (http.client.HTTPException, socket.timeout, OSError) as e:
        # keep-alive 复用撞上服务端主动关闭、或网络抖动 —— 丢连接后重试
        _drop_conn(scheme, host, port)
        return None, f"{type(e).__name__}: {e}", True
    except Exception as e:  # noqa: BLE001
        _drop_conn(scheme, host, port)
        return None, f"{type(e).__name__}: {e}", True


def _validate(data: bytes) -> Tuple[Optional[bytes], str, bool]:
    if not data:
        return None, "空响应", True
    if len(data) > MAX_BYTES:
        return None, f"文件超过上限 {MAX_BYTES // 1024 // 1024} MB", False
    if _sniff_image(data) is None:
        return None, f"返回内容不是图片（开头 {data[:24]!r}）", False
    return data, "", False


def _download(url: str) -> Tuple[Optional[bytes], str]:
    """带重试的下载。返回 (数据, 错误信息)。不写盘。"""
    ok, why = url_allowed(url)
    if not ok:
        return None, why
    last = "unknown"
    for attempt in range(RETRIES + 1):
        data, err, retry = _download_once(url)
        if data is not None:
            return data, ""
        last = err
        if not retry or attempt >= RETRIES:
            break
        # 退避：0.4s / 1.2s。连接类故障通常是瞬时的（实测重试立刻成功）
        time.sleep(0.4 * (3 ** attempt))
        _bump("retry")
    return None, last


def fetch(url: str, force: bool = False) -> Tuple[Optional[str], str, bool]:
    """取一个缩略图，必要时下载并落盘。

    返回 ``(本地文件路径 或 None, 错误信息, 是否命中缓存)``。
    """
    ok, why = url_allowed(url)
    if not ok:
        return None, why, False

    path = cache_path(url)
    if not force and os.path.exists(path) and os.path.getsize(path) > 0:
        _bump("hit")
        return path, "", True

    _bump("miss")
    data, err = _download(url)
    if data is None:
        _bump("fail")
        return None, err, False

    tmp = path + ".part"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception as e:  # noqa: BLE001
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return None, f"写缓存失败：{e}", False

    _bump("download")
    _bump("bytes", len(data))
    return path, "", False


# ---------------------------------------------------------------------------
# 预热 / 统计 / 清理
# ---------------------------------------------------------------------------

def warm(urls: List[str], force: bool = False,
         progress=None) -> Dict[str, object]:
    """批量预热。

    ⚠️ **真正的并发在这里**。第一版写成
    ``for okk in _EXECUTOR.map(_one, todo)`` —— `Executor.map` 是**阻塞迭代**
    的，而且在调用方的**同一个线程**里等结果。而调用方（aiohttp 路由）
    本身是 `run_in_executor` 起的一个线程，于是整个 warm 变成**串行**下载，
    "8 并发"完全是假的（实测 30 张 237 秒，还偶发 2 线程一起就雪崩）。

    现在改成 `submit` + `as_completed`（在**当前线程内**把任务派发给
    `_EXECUTOR` 的多个工作线程，每个任务自己从 thread-local 池拿连接）。

    ``progress`` 可选，形如 ``fn(done, total)``，供上层做进度显示。
    """
    todo: List[str] = []
    skipped = 0
    bad = 0
    for u in urls[:MAX_WARM]:
        u = str(u or "").strip()
        if not u:
            continue
        if not url_allowed(u)[0]:
            bad += 1
            continue
        p = cache_path(u)
        if not force and os.path.exists(p) and os.path.getsize(p) > 0:
            skipped += 1
            continue
        todo.append(u)

    done, failed = 0, 0
    total = len(todo)
    if total:
        from concurrent.futures import as_completed

        def _one(u: str) -> bool:
            try:
                return fetch(u, force=force)[0] is not None
            except Exception:  # noqa: BLE001
                return False

        futures = [_EXECUTOR.submit(_one, u) for u in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                if fut.result():
                    done += 1
                else:
                    failed += 1
            except Exception:  # noqa: BLE001
                failed += 1
            if progress is not None and (i % 20 == 0 or i == total):
                try:
                    progress(i, total)
                except Exception:  # noqa: BLE001
                    pass
    return {"requested": len(urls), "already": skipped, "downloaded": done,
            "failed": failed, "rejected": bad, "total": len(urls),
            "workers": MAX_WORKERS}


def stats() -> Dict[str, object]:
    """缓存统计（面板显示用）。

    ⚠️ 遍历时可能**同时有别的线程在写文件**（预热是并发的），
    Windows 上 `getsize` 撞上刚被删/重命名的文件会抛 OSError —— 逐条兜住，
    统计数字偶尔少一个无所谓，不能因此让接口 500。
    """
    root = cache_dir()
    files = 0
    total = 0
    try:
        for r, _dirs, fs in os.walk(root):
            for f in fs:
                if f.endswith(".part"):
                    continue
                try:
                    total += os.path.getsize(os.path.join(r, f))
                    files += 1
                except OSError:
                    pass
    except Exception:
        pass
    with _STATS_LOCK:
        s = dict(_STATS)
    return {"dir": root, "files": files,
            "mb": round(total / 1024 / 1024, 1),
            **s}


def clear() -> Dict[str, object]:
    """清空缓存。"""
    root = cache_dir()
    removed = 0
    freed = 0
    try:
        for r, dirs, fs in os.walk(root, topdown=False):
            for f in fs:
                p = os.path.join(r, f)
                try:
                    freed += os.path.getsize(p)
                    os.remove(p)
                    removed += 1
                except OSError:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(r, d))
                except OSError:
                    pass
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    return {"ok": True, "removed": removed, "freed_mb": round(freed / 1024 / 1024, 1)}


# 1×1 透明 PNG —— 下载失败时返回它，前端就不会出现破图边框
TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def content_type(path: str) -> str:
    return _content_type_for(path)
