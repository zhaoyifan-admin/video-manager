"""路径浏览接口：磁盘挂载点 / 目录浏览 / 新建文件夹（/api/paths）"""
import getpass
import os
import platform
import shutil
import string

from flask import Blueprint, request

from auth import require_login

from responses import ok, fail
from storage import sanitize_filename

bp = Blueprint("paths", __name__, url_prefix="/api/paths")


def _disk_entry(path):
    """磁盘挂载点信息：路径、显示名、剩余/总空间"""
    entry = {"path": path, "name": os.path.basename(path.rstrip("/\\")) or path}
    try:
        usage = shutil.disk_usage(path)
        entry["free"] = usage.free
        entry["total"] = usage.total
    except OSError:
        pass
    return entry


def list_drives():
    """枚举本机磁盘与外接硬盘挂载点（macOS: /Volumes，Linux: /media /mnt，Windows: 盘符）"""
    system = platform.system()
    roots = []
    if system == "Darwin":
        base = "/Volumes"
        if os.path.isdir(base):
            roots = [os.path.join(base, n) for n in sorted(os.listdir(base))]
    elif system == "Windows":
        roots = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    else:
        candidates = set()
        for base in ("/media", "/mnt", "/run/media"):
            if not os.path.isdir(base):
                continue
            candidates.add(base)
            user_base = os.path.join(base, getpass.getuser())
            if os.path.isdir(user_base):
                candidates.add(user_base)
                candidates.update(os.path.join(user_base, n) for n in os.listdir(user_base))
        roots = sorted(candidates)
    if not roots:
        roots = [os.path.abspath(os.sep)]
    return ok([_disk_entry(r) for r in roots])


@bp.get("/drives")
@require_login
def drives_endpoint():
    return list_drives()


@bp.get("/list")
@require_login
def list_dir():
    """列出某个目录下的子文件夹（用于保存路径浏览）；dir 为空时返回磁盘挂载点列表"""
    dir_path = (request.args.get("dir") or "").strip()
    if not dir_path:
        return list_drives()
    if not os.path.isabs(dir_path) or not os.path.isdir(dir_path):
        return fail("目录不存在或不可访问")
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
    parent = os.path.dirname(dir_path.rstrip("/\\")) or None
    return ok({"path": dir_path, "parent": parent, "folders": names})


@bp.post("/mkdir")
@require_login
def make_dir():
    """在指定父目录下新建文件夹（保存路径不存在时自定义创建）"""
    body = request.get_json(silent=True) or {}
    parent = (body.get("parent") or "").strip()
    name = sanitize_filename(body.get("name") or "")
    if not parent or not os.path.isabs(parent) or not os.path.isdir(parent):
        return fail("父目录无效或不存在")
    if not name:
        return fail("请输入文件夹名称")
    target = os.path.join(parent, name)
    if os.path.exists(target):
        return fail("同名文件夹已存在")
    try:
        os.makedirs(target)
    except OSError as e:
        return fail(f"创建文件夹失败：{e}")
    return ok({"path": target, "name": name})
