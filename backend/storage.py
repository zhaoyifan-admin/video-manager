"""文件与路径工具：媒体目录白名单、文件名清洗、安全路径解析、源文件物理删除

安全模型：所有本地视频路径必须同时满足
  1) 是已登记媒体根目录（uploads / 外接硬盘挂载点 / 常用媒体目录 / MEDIA_ROOTS）之内的文件；
  2) 扩展名在允许的视频扩展名集合内；
  3) realpath 解析后仍落在根目录内（挡住符号链接指向外部与 .. 穿越）。
写入、读取、删除、目录浏览共用这一套校验，避免把本机任意文件暴露给登录用户。
"""
import os
import platform
import re
import string
import time

import config
from config import BASE_DIR, UPLOAD_DIR

ALLOWED_VIDEO_EXTS = set(getattr(config, "ALLOWED_VIDEO_EXTS", ())) or {
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv",
    ".ts", ".m2ts", ".mpg", ".mpeg", ".rmvb", ".rm", ".3gp", ".ogv",
}


def sanitize_filename(name):
    """保留中文等字符，仅替换文件系统非法字符与路径分隔符"""
    name = os.path.basename(name or "").strip()
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name or "video"


def is_remote_url(path):
    """外链播放地址：允许登记，但后端不会把它当本地文件读取"""
    return isinstance(path, str) and path.lower().startswith(("http://", "https://"))


def has_video_ext(path):
    return os.path.splitext(path or "")[1].lower() in ALLOWED_VIDEO_EXTS


def _auto_roots():
    """自动识别的媒体根目录：上传目录、外接硬盘挂载点、本机常用媒体目录"""
    roots = [UPLOAD_DIR]
    system = platform.system()
    if system == "Darwin":
        base = "/Volumes"
        if os.path.isdir(base):
            roots.extend(os.path.join(base, n) for n in os.listdir(base))
    elif system == "Windows":
        roots.extend(f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\"))
    else:
        for base in ("/media", "/mnt", "/run/media"):
            if os.path.isdir(base):
                roots.append(base)
                roots.extend(
                    os.path.join(base, n) for n in os.listdir(base)
                    if os.path.isdir(os.path.join(base, n))
                )
    home = os.path.expanduser("~")
    roots.extend(os.path.join(home, d) for d in ("Movies", "Downloads", "Desktop", "Documents"))
    return roots


_root_cache = {"ts": 0.0, "roots": []}
_ROOT_CACHE_TTL = 5.0  # 秒：短缓存避免批量导入时反复 listdir，又能感知新挂载的外接硬盘


def media_roots():
    """返回当前生效的媒体根目录（已归一、去重、仅保留真实存在的目录）"""
    now = time.time()
    if _root_cache["roots"] and now - _root_cache["ts"] < _ROOT_CACHE_TTL:
        return _root_cache["roots"]
    roots = _auto_roots() + list(getattr(config, "MEDIA_ROOTS", []) or [])
    result = []
    for r in roots:
        if not r:
            continue
        real = os.path.realpath(os.path.abspath(r))
        if os.path.isdir(real) and real not in result:
            result.append(real)
    _root_cache["roots"] = result
    _root_cache["ts"] = now
    return result


def is_within(path, roots=None):
    """path 是否落在任一媒体根目录内（realpath 后比较，挡符号链接逃逸）。
    盘符根（如 Windows 的 "C:\\"）需去掉尾部分隔符再做前缀比较，否则子路径全部失配"""
    real = os.path.realpath(os.path.abspath(path))
    for root in media_roots() if roots is None else roots:
        base = root.rstrip(os.sep) or root
        if real == root or real == base or real.startswith(base + os.sep):
            return True
    return False


def validate_media_path(path, must_exist=False):
    """校验并规范化待入库的视频路径。

    返回 (可存储的路径, 错误信息)；错误信息非 None 表示校验失败。
    绝对路径原样保留，相对路径只允许 uploads/ 前缀。
    """
    p = (path or "").strip()
    if not p:
        return "", None  # 允许仅登记信息、暂不绑定文件
    if is_remote_url(p):
        return p, None

    if os.path.isabs(p):
        stored = os.path.abspath(p)
        candidate = os.path.realpath(stored)
    else:
        normalized = os.path.normpath(p).replace("\\", "/")
        if not (normalized == "uploads" or normalized.startswith("uploads/")):
            return None, "文件路径只允许 uploads/ 内的相对路径，或已登记媒体目录下的绝对路径"
        stored = normalized
        candidate = os.path.realpath(os.path.join(BASE_DIR, normalized))

    if not has_video_ext(candidate):
        return None, "不支持的文件类型，仅允许视频文件"
    if not is_within(candidate):
        return None, "路径不在允许的媒体目录内，请在 backend/config.py 的 MEDIA_ROOTS 中登记该目录"
    if must_exist and not os.path.isfile(candidate):
        return None, "源文件不存在或已被移走，请检查磁盘是否挂载"
    return stored, None


def resolve_video_path(path):
    """把入库路径解析成可安全读取的本地文件路径；不合规或文件不存在返回 None"""
    stored, error = validate_media_path(path, must_exist=True)
    if error or not stored or is_remote_url(stored):
        return None
    return os.path.realpath(os.path.abspath(
        stored if os.path.isabs(stored) else os.path.join(BASE_DIR, stored)
    ))


def delete_source_file(path):
    """物理删除视频源文件（单文件删除，绝不递归）。

    返回 (deleted, missing) 两个布尔值，供调用方区分三种结果并如实提示用户：
      - deleted=True：文件已成功删除；
      - missing=True：路径不在媒体白名单内、无法解析，或文件本就不存在（无文件可删，仅清理记录）；
      - 两者皆 False：文件存在但删除失败（如 Windows 下文件正被播放器占用），需提示用户手动处理。"""
    stored, error = validate_media_path(path)
    if error or not stored or is_remote_url(stored):
        # 路径不合法 / 不在白名单：不能按库里的路径碰磁盘，文件是否真实存在未知，按「删不掉」处理
        return False, False
    real = os.path.realpath(stored if os.path.isabs(stored) else os.path.join(BASE_DIR, stored))
    if not os.path.isfile(real):
        return False, True  # 文件本就不存在（已被移走或手动删除），视为无文件可删
    # Windows 下浏览器/播放器可能仍持有文件句柄，短暂重试等句柄释放
    last_error = None
    for attempt in range(4):
        try:
            os.remove(real)
            return True, False
        except FileNotFoundError:
            return False, True
        except OSError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.4)
    # 重试后仍失败：文件确实还在，调用方必须提示用户手动删除
    print(f"[storage] 源文件删除失败（重试 4 次）：{real} -> {last_error}", flush=True)
    return False, False


# 字幕等非视频资源复用同一套白名单，但使用各自的扩展名集合
ALLOWED_SUBTITLE_EXTS = {".vtt", ".srt"}


def validate_asset_path(path, exts, label="资源"):
    """校验白名单目录内的附属资源路径，返回 (规范化路径, 错误信息)"""
    p = (path or "").strip()
    if not p:
        return "", None
    if is_remote_url(p):
        return p, None
    if os.path.isabs(p):
        stored = os.path.abspath(p)
        candidate = os.path.realpath(stored)
    else:
        normalized = os.path.normpath(p).replace("\\", "/")
        if not (normalized == "uploads" or normalized.startswith("uploads/")):
            return None, f"{label}路径只允许 uploads/ 内的相对路径或已登记目录的绝对路径"
        stored = normalized
        candidate = os.path.realpath(os.path.join(BASE_DIR, normalized))
    if os.path.splitext(candidate)[1].lower() not in exts:
        return None, f"不支持的{label}文件类型"
    if not is_within(candidate):
        return None, f"{label}路径不在允许的媒体目录内"
    return stored, None


def resolve_asset_path(path, exts):
    """把附属资源路径解析成可安全读取的本地文件；不合规或不存在返回 None"""
    stored, error = validate_asset_path(path, exts)
    if error or not stored or is_remote_url(stored):
        return None
    full = stored if os.path.isabs(stored) else os.path.join(BASE_DIR, stored)
    return os.path.realpath(full) if os.path.isfile(full) else None
