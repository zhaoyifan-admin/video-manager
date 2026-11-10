"""文件与路径工具：文件名清洗、路径解析、源文件物理删除"""
import os
import re

from config import BASE_DIR


def sanitize_filename(name):
    """保留中文等字符，仅替换文件系统非法字符与路径分隔符"""
    name = os.path.basename(name or "").strip()
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name or "video"


def resolve_video_path(path):
    """兼容两种存法：绝对路径（手填本机路径）与相对路径（上传文件，相对 backend 目录）"""
    if not path:
        return None
    if os.path.isabs(path):
        return path if os.path.isfile(path) else None
    candidate = os.path.join(BASE_DIR, path)
    return candidate if os.path.isfile(candidate) else None


def delete_source_file(path):
    """物理删除视频源文件（单文件删除，绝不递归）。

    兼容绝对路径与 uploads 相对路径；文件不存在或路径无效时静默跳过，
    不影响数据库删除结果。"""
    resolved = resolve_video_path(path)
    if not resolved:
        return False
    try:
        real = os.path.realpath(resolved)
        # 安全兜底：只删除真实存在的普通文件，不碰目录
        if not os.path.isfile(real):
            return False
        os.remove(real)
        return True
    except OSError:
        return False
