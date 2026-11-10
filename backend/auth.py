"""认证工具：密码哈希、会话登录态、登录校验装饰器"""
from functools import wraps

from flask import g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

import db

SESSION_KEY = "user_id"


def hash_password(password):
    """生成密码哈希（pbkdf2，自动加盐）"""
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """校验密码与哈希是否匹配"""
    return check_password_hash(password_hash, password)


def set_login(user_id):
    """写入登录态（cookie 签名会话）"""
    session[SESSION_KEY] = user_id
    session.permanent = True  # 配合 PERMANENT_SESSION_LIFETIME 长效保持


def clear_login():
    """清除登录态"""
    session.pop(SESSION_KEY, None)


def current_user():
    """返回当前登录用户（dict：id/username/role/created_at），未登录返回 None"""
    uid = session.get(SESSION_KEY)
    if not uid:
        return None
    return db.query(
        "SELECT id, username, role, created_at FROM users WHERE id = %s", (uid,), one=True
    )


def is_super_admin(user):
    """判断是否超级管理员（role = 'admin'，可查看/管理所有用户的视频）"""
    return bool(user) and user.get("role") == "admin"


def visible_sql(user):
    """「可观看」SQL 条件片段：本人视频 OR 公开视频 OR 超管可见全部。
    列名不带表前缀（videos 是唯一含 user_id / is_public 列的表，多表关联查询中同样无歧义）"""
    if is_super_admin(user):
        return "TRUE", []
    return "(user_id = %s OR is_public = 1)", [user["id"]]


def manageable_sql(user):
    """「可管理」SQL 条件片段（编辑/删除/公开设置）：本人视频 OR 超管全部"""
    if is_super_admin(user):
        return "TRUE", []
    return "user_id = %s", [user["id"]]


def require_login(fn):
    """视图装饰器：未登录返回 401；登录后通过 g.user 注入当前用户"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"code": 1, "msg": "未登录或登录已过期"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper
