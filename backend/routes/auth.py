"""认证接口：注册 / 登录 / 退出 / 当前用户 / 角色管理 / 修改密码 / 头像（/api/auth）"""
import os
import re
import uuid

from flask import Blueprint, g, request, send_file

import config
import db
from admin_audit_logs import record
from auth import (
    clear_login,
    current_user,
    hash_password,
    is_super_admin,
    require_admin,
    require_login,
    set_login,
    verify_password,
)
from responses import ok, fail

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# 用户名：2-50 位，中文 / 字母 / 数字 / 下划线
USERNAME_RE = re.compile(r"^[\w\u4e00-\u9fa5]{2,50}$")

# 头像允许的文件类型与体积上限（本地私人服务，限制到 5MB 即可）
ALLOWED_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AVATAR_MAX_BYTES = 5 * 1024 * 1024
ROLE_TEXT = {
    "user": "普通用户", "reviewer": "审核员", "manager": "管理员", "admin": "超级管理员",
}
_AVATAR_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _public(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "avatar": user.get("avatar") or "",
    }


def _avatars_root():
    """头像目录的绝对路径（uploads/avatars），不存在则创建"""
    root = os.path.realpath(os.path.join(config.BASE_DIR, "uploads", "avatars"))
    os.makedirs(root, exist_ok=True)
    return root


def _safe_avatar_path(rel_path):
    """把相对路径解析成头像目录内的绝对路径；越界或非法返回 None（防目录穿越）"""
    if not rel_path:
        return None
    full = os.path.realpath(os.path.join(config.BASE_DIR, rel_path))
    root = _avatars_root()
    if full == root or full.startswith(root + os.sep):
        return full
    return None


def _check_username(username):
    """用户名占用检测：返回 (可用, 提示语)。注册实时提示与提交校验共用。"""
    if not USERNAME_RE.match(username):
        return False, "用户名需 2-50 位，仅限中文、字母、数字、下划线"
    if db.query("SELECT id FROM users WHERE username = %s", (username,), one=True):
        return False, "该用户名已被注册"
    return True, "该用户名可用"


@bp.get("/config")
def client_config():
    """前端启动时读取的公开配置：注册开关、单用户配额"""
    return ok({
        "registrationEnabled": bool(getattr(config, "REGISTRATION_ENABLED", True)),
        "maxVideosPerUser": int(getattr(config, "MAX_VIDEOS_PER_USER", 0) or 0),
    })


@bp.get("/check-username")
def check_username():
    """注册用户名实时防重检测（输入框失焦/防抖调用）"""
    if not getattr(config, "REGISTRATION_ENABLED", True):
        return ok({"available": False, "message": "本站已关闭新用户注册"})
    username = (request.args.get("username") or "").strip()
    available, message = _check_username(username)
    return ok({"available": available, "message": message})


@bp.post("/register")
def register():
    if not getattr(config, "REGISTRATION_ENABLED", True):
        return fail("本站已关闭新用户注册，请联系管理员")
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = str(data.get("password") or "")
    available, message = _check_username(username)
    if not available:
        return fail(message)
    if len(password) < 6:
        return fail("密码至少 6 位")
    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hash_password(password)),
        )
    except Exception:
        # 并发注册同名撞 UNIQUE 索引：按防重失败处理，避免 500
        return fail("该用户名已被注册")
    user = db.query("SELECT id, username FROM users WHERE username = %s", (username,), one=True)
    set_login(user["id"])  # 注册即登录
    return ok(_public(user))


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = str(data.get("password") or "")
    user = db.query(
        "SELECT id, username, role, password_hash FROM users WHERE username = %s",
        (username,),
        one=True,
    )
    if not user or not verify_password(user["password_hash"], password):
        return fail("用户名或密码错误")
    set_login(user["id"])
    return ok(_public(user))


@bp.post("/logout")
@require_login
def logout():
    # 退出时清空本人「继续观看」续播进度，下次登录不再残留上次进度
    try:
        db.execute("DELETE FROM watch_history WHERE user_id = %s", (g.user["id"],))
    except Exception:
        # 续播表异常不影响正常退出
        pass
    clear_login()
    return ok()


@bp.get("/me")
def me():
    user = current_user()
    if not user:
        return fail("未登录", 401)
    return ok(_public(user))


@bp.post("/change-password")
@require_login
def change_password():
    """修改本人登录密码：校验当前密码正确且新密码合规后更新哈希"""
    data = request.get_json(silent=True) or {}
    old_pwd = str(data.get("oldPassword") or "")
    new_pwd = str(data.get("newPassword") or "")
    if not old_pwd:
        return fail("请输入当前密码")
    if len(new_pwd) < 6:
        return fail("新密码至少 6 位")
    row = db.query(
        "SELECT password_hash FROM users WHERE id = %s", (g.user["id"],), one=True
    )
    if not row or not verify_password(row["password_hash"], old_pwd):
        return fail("当前密码不正确")
    db.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(new_pwd), g.user["id"]),
    )
    return ok({"msg": "密码已修改"})


@bp.post("/avatar")
@require_login
def upload_avatar():
    """上传本人头像：仅接受图片类型，存入 uploads/avatars，并清理旧头像文件避免堆积"""
    file = request.files.get("file")
    if not file or not file.filename:
        return fail("请选择要上传的头像图片")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTS:
        return fail("仅支持 png / jpg / jpeg / gif / webp 格式的头像")
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > AVATAR_MAX_BYTES:
        return fail("头像文件过大（请控制在 5MB 以内）")
    name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(_avatars_root(), name)
    file.save(dest)
    # 先取旧头像路径，更新字段后再删除旧文件（保证失败也不丢当前头像）
    old = db.query("SELECT avatar FROM users WHERE id = %s", (g.user["id"],), one=True)
    old_rel = old["avatar"] if old else None
    db.execute(
        "UPDATE users SET avatar = %s WHERE id = %s",
        (f"uploads/avatars/{name}", g.user["id"]),
    )
    if old_rel:
        old_full = _safe_avatar_path(old_rel)
        if old_full and os.path.isfile(old_full):
            try:
                os.remove(old_full)
            except OSError:
                pass
    return ok({"avatar": f"uploads/avatars/{name}"})


@bp.get("/avatar")
@require_login
def get_avatar():
    """按登录态流式返回本人头像图片；未设置或文件缺失返回 404（前端回退首字母）"""
    row = db.query("SELECT avatar FROM users WHERE id = %s", (g.user["id"],), one=True)
    rel = row["avatar"] if row else None
    full = _safe_avatar_path(rel)
    if not full or not os.path.isfile(full):
        return fail("未设置头像", 404)
    mime = _AVATAR_MIME.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
    return send_file(full, mimetype=mime, conditional=True)


@bp.get("/users")
@require_login
@require_admin
def list_users():
    """超管查看账号列表与各账号的视频数量（用于分配审核员角色）"""
    rows = db.query(
        "SELECT u.id, u.username, u.role, u.created_at, "
        "(SELECT COUNT(*) FROM videos v WHERE v.user_id = u.id) AS video_count "
        "FROM users u ORDER BY u.id"
    )
    return ok({"items": [{
        "id": r["id"],
        "username": r["username"],
        "role": r["role"],
        "videoCount": r["video_count"],
        "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
    } for r in rows]})


@bp.post("/users/<int:user_id>/role")
@require_login
@require_admin
def change_role(user_id):
    """设置账号角色：user 普通用户 / reviewer 独立审核员 / manager 管理员 / admin 超级管理员"""
    role = (request.get_json(silent=True) or {}).get("role")
    if role not in ("user", "reviewer", "manager", "admin"):
        return fail("角色无效（user / reviewer / manager / admin）")
    if user_id == g.user["id"] and role != "admin":
        return fail("不能降低自己的管理员权限")
    before = db.query(
        "SELECT username, role FROM users WHERE id = %s", (user_id,), one=True
    )
    if not before:
        return fail("用户不存在", 404)
    db.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
    record(g.user, "change_role", "user", user_id, before["username"],
           f"{ROLE_TEXT.get(before['role'], before['role'])} → {ROLE_TEXT.get(role, role)}")
    return ok({"role": role})


@bp.post("/users")
@require_login
@require_admin
def create_user():
    """超管直接创建账号：关闭注册后仍可由管理员统一分配账号"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = str(data.get("password") or "")
    role = data.get("role") or "user"
    if not USERNAME_RE.match(username):
        return fail("用户名需 2-50 位，仅限中文、字母、数字、下划线")
    if len(password) < 6:
        return fail("密码至少 6 位")
    if role not in ("user", "reviewer", "manager", "admin"):
        return fail("角色无效（user / reviewer / manager / admin）")
    if db.query("SELECT id FROM users WHERE username = %s", (username,), one=True):
        return fail("该用户名已被注册")
    result = db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, hash_password(password), role),
    )
    record(g.user, "create_user", "user", result["lastrowid"], username,
           f"初始角色：{ROLE_TEXT.get(role, role)}")
    return ok({"id": result["lastrowid"], "username": username, "role": role})
