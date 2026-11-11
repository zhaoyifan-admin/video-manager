"""认证接口：注册 / 登录 / 退出 / 当前用户（/api/auth）"""
import re

from flask import Blueprint, request

import db
from auth import (
    clear_login,
    current_user,
    hash_password,
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


@bp.get("/check-username")
def check_username():
    """注册用户名实时防重检测（输入框失焦/防抖调用）"""
    username = (request.args.get("username") or "").strip()
    available, message = _check_username(username)
    return ok({"available": available, "message": message})


@bp.post("/register")
def register():
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
def logout():
    clear_login()
    return ok()


@bp.get("/me")
def me():
    user = current_user()
    if not user:
        return fail("未登录", 401)
    return ok(_public(user))
