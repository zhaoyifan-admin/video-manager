"""认证接口：注册 / 登录 / 退出 / 当前用户 / 角色管理（/api/auth）"""
import re

from flask import Blueprint, g, request

import config
import db
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


def _public(user):
    return {"id": user["id"], "username": user["username"], "role": user.get("role", "user")}


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
    result = db.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
    if result["rowcount"] == 0:
        return fail("用户不存在", 404)
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
    return ok({"id": result["lastrowid"], "username": username, "role": role})
