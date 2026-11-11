"""路径浏览接口：媒体根目录 / 目录浏览 / 新建文件夹（/api/paths）

只允许浏览 config.MEDIA_ROOTS 与自动识别的媒体根目录，不再枚举整个文件系统。
"""
import os
import shutil

from flask import Blueprint, request

from auth import require_login
from responses import ok, fail
from storage import is_within, media_roots, sanitize_filename

bp = Blueprint("paths", __name__, url_prefix="/api/paths")


def _disk_entry(path):
    """媒体根目录信息：路径、显示名、剩余/总空间"""
    entry = {"path": path, "name": os.path.basename(path.rstrip("/\\")) or path}
    try:
        usage = shutil.disk_usage(path)
        entry["free"] = usage.free
        entry["total"] = usage.total
    except OSError:
        pass
    return entry


def list_drives():
    """列出所有可用的媒体根目录（外接硬盘挂载后会自动出现在这里）"""
    return ok([_disk_entry(r) for r in media_roots()])


@bp.get("/drives")
@require_login
def drives_endpoint():
    return list_drives()


@bp.get("/list")
@require_login
def list_dir():
    """列出媒体根目录下某个子目录中的文件夹；dir 为空时返回根目录列表"""
    dir_path = (request.args.get("dir") or "").strip()
    if not dir_path:
        return list_drives()
    if not os.path.isabs(dir_path) or not os.path.isdir(dir_path):
        return fail("目录不存在或不可访问")
    if not is_within(dir_path):
        return fail("该目录不在允许的媒体目录内，请先在 config.py 的 MEDIA_ROOTS 中登记")
    try:
        names = sorted(
            (
                n
                for n in os.listdir(dir_path)
                if not n.startswith(".") and os.path.isdir(os.path.join(dir_path, n))
            ),
            key=str.lower,
        )
    except OSError as e:
        return fail(f"读取目录失败：{e}")
    parent = os.path.dirname(os.path.realpath(dir_path).rstrip("/\\")) or None
    # 上一级若已越出白名单则不提供，避免前端一层层爬到系统目录
    if parent and not is_within(parent):
        parent = None
    return ok({"path": os.path.realpath(dir_path), "parent": parent, "folders": names})


@bp.post("/mkdir")
@require_login
def make_dir():
    """在已登记的媒体目录下新建文件夹"""
    body = request.get_json(silent=True) or {}
    parent = (body.get("parent") or "").strip()
    name = sanitize_filename(body.get("name") or "")
    if not parent or not os.path.isabs(parent) or not os.path.isdir(parent):
        return fail("父目录无效或不存在")
    if not is_within(parent):
        return fail("父目录不在允许的媒体目录内")
    if not name:
        return fail("请输入文件夹名称")
    target = os.path.join(parent, name)
    if not is_within(target):
        return fail("目标路径越出允许的媒体目录")
    if os.path.exists(target):
        return fail("同名文件夹已存在")
    try:
        os.makedirs(target)
    except OSError as e:
        return fail(f"创建文件夹失败：{e}")
    return ok({"path": target, "name": name})
