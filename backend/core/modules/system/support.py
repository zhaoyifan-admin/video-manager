"""P1 共享工具：分页、密码策略、权限缓存失效、主角色同步。

约束：
1. 所有 SQL 参数化，字段白名单由调用方显式提供，禁止拼接请求里的列名；
2. 多表写入使用 db.get_conn() 显式事务，避免中途失败留下半套关联数据；
3. 权限相关数据变更后递增 sys_config.permission_version，使各进程缓存失效。
"""
import re
from datetime import datetime, timedelta

from flask import request

import db
from auth import hash_password, verify_password
from ... import cache


class TxConnection:
    """PyMySQL 原生连接的事务包装器：提供 execute/fetchone/fetchall/lastrowid。

    只用于 P1 多表写入，不改变 db.get_conn() 本身，避免影响视频子系统既有
    「with conn.cursor() as cur」写法。
    """

    def __init__(self, conn):
        self._conn = conn
        self._cursor = None
        self.lastrowid = None

    def execute(self, sql, args=None):
        if self._cursor is not None:
            self._cursor.close()
        self._cursor = self._conn.cursor()
        self._cursor.execute(sql, args or ())
        self.lastrowid = self._cursor.lastrowid
        return self

    def fetchone(self):
        return self._cursor.fetchone() if self._cursor is not None else None

    def fetchall(self):
        return self._cursor.fetchall() if self._cursor is not None else []

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._cursor is not None:
            self._cursor.close()
        self._conn.close()


def get_conn():
    """取得 P1 事务连接（原生 PyMySQL 连接 + cursor 语义包装）。"""
    return TxConnection(db.get_conn())


# 主角色优先级：与 auth.py 的 ROLE_LEVELS 保持一致，写多角色时同步 users.role 快照。
ROLE_PRIORITY = {"admin": 3, "manager": 2, "reviewer": 2, "user": 1}
VALID_ROLES = tuple(ROLE_PRIORITY)


def primary_role(codes):
    """从多角色集合中取主角色快照：admin > manager/reviewer > user。"""
    codes = [code for code in (codes or []) if code in ROLE_PRIORITY]
    if not codes:
        return "user"
    return sorted(codes, key=lambda code: (-ROLE_PRIORITY[code], code))[0]


def page_args():
    """读取分页参数；pageSize 上限 200，避免一次拉取整表。"""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(200, max(1, int(request.args.get("pageSize", 10))))
    except (TypeError, ValueError):
        size = 10
    return page, size


def like(value):
    """构造 LIKE 参数；空串返回 None，由调用方决定是否加条件。"""
    value = (value or "").strip()
    return f"%{value}%" if value else None


def pwd_policy():
    """从 sys_config.security 读取密码策略，改配置即时生效。"""
    rows = db.query(
        "SELECT config_key, config_value FROM sys_config WHERE config_group = 'security'"
    ) or []
    cfg = {row["config_key"]: row["config_value"] for row in rows}

    def number(key, default):
        try:
            return int(cfg.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "minLength": number("pwd_min_length", 8),
        "requireComplex": cfg.get("pwd_require_complex", "1") == "1",
        "historyLimit": number("pwd_history_limit", 3),
        "lockThreshold": number("pwd_lock_threshold", 5),
        "lockMinutes": number("pwd_lock_minutes", 15),
        "expireDays": number("pwd_expire_days", 90),
    }


def validate_password(password, user_id=None, conn=None):
    """校验密码策略：长度、复杂度、历史不可复用。通过返回 None，否则返回错误文案。"""
    policy = pwd_policy()
    text = str(password or "")
    if len(text) < policy["minLength"]:
        return f"密码至少 {policy['minLength']} 位"
    if policy["requireComplex"] and not (
        re.search(r"[A-Za-z]", text) and re.search(r"\d", text)
    ):
        return "密码需同时包含字母和数字"
    limit = policy["historyLimit"]
    if user_id and limit > 0:
        sql = (
            "SELECT password_hash FROM sys_password_history WHERE user_id = %s "
            "ORDER BY changed_at DESC, id DESC LIMIT %s"
        )
        rows = (conn.execute(sql, (user_id, limit)).fetchall() if conn is not None
                else db.query(sql, (user_id, limit)))
        for row in rows or []:
            if verify_password(row["password_hash"], text):
                return "密码不能与最近使用的密码相同"
    return None


def write_password_history(conn, user_id, raw_password):
    """写入密码历史并清理超出策略条数的旧记录；调用方负责事务。"""
    policy = pwd_policy()
    conn.execute(
        "INSERT INTO sys_password_history (user_id, password_hash) VALUES (%s, %s)",
        (user_id, hash_password(raw_password)),
    )
    conn.execute(
        "DELETE FROM sys_password_history WHERE user_id = %s AND id NOT IN ("
        "  SELECT id FROM (SELECT id FROM sys_password_history WHERE user_id = %s "
        "  ORDER BY changed_at DESC, id DESC LIMIT %s) t)",
        (user_id, user_id, max(0, policy["historyLimit"])),
    )


def bump_permission_version(conn=None):
    """权限数据变更后递增版本号并清空本进程缓存。"""
    sql = (
        "UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1 "
        "WHERE config_key = 'permission_version'"
    )
    if conn is not None:
        conn.execute(sql)
    else:
        db.execute(sql)
    cache.invalidate_prefix("permissions:")
    cache.invalidate_prefix("menus:")


def ensure_role_codes(conn, codes):
    """校验角色编码都存在且启用；返回 sys_role 行列表。"""
    codes = list(dict.fromkeys(codes or []))
    if not codes:
        return []
    marks = ",".join(["%s"] * len(codes))
    rows = conn.execute(
        f"SELECT id, role_code, built_in FROM sys_role WHERE status = 1 AND role_code IN ({marks})",
        codes,
    ).fetchall()
    found = {row["role_code"] for row in rows}
    missing = [code for code in codes if code not in found]
    if missing:
        raise ValueError(f"角色不存在或已停用：{', '.join(missing)}")
    return rows


def ensure_dept(conn, dept_id):
    """校验部门存在且启用；dept_id=0 允许（未分配）。"""
    if not dept_id:
        return None
    row = conn.execute(
        "SELECT id, dept_name FROM sys_dept WHERE id = %s AND enabled_flag = 1", (dept_id,)
    ).fetchone()
    if not row:
        raise ValueError("部门不存在或已停用")
    return row


def sync_user_roles(conn, user_id, codes):
    """重建用户-角色关联并同步 users.role 主角色快照。"""
    roles = ensure_role_codes(conn, codes)
    conn.execute("DELETE FROM sys_user_role WHERE user_id = %s", (user_id,))
    for role in roles:
        conn.execute(
            "INSERT INTO sys_user_role (user_id, role_id) VALUES (%s, %s)",
            (user_id, role["id"]),
        )
    conn.execute(
        "UPDATE users SET role = %s WHERE id = %s",
        (primary_role([row["role_code"] for row in roles]), user_id),
    )
    return roles


def sync_user_posts(conn, user_id, post_ids):
    """重建用户-岗位关联。"""
    ids = list(dict.fromkeys(int(pid) for pid in (post_ids or []) if str(pid).isdigit()))
    conn.execute("DELETE FROM sys_user_post WHERE user_id = %s", (user_id,))
    if not ids:
        return
    marks = ",".join(["%s"] * len(ids))
    exists = conn.execute(
        f"SELECT id FROM sys_post WHERE enabled_flag = 1 AND id IN ({marks})", ids
    ).fetchall()
    valid = [row["id"] for row in exists]
    if len(valid) != len(ids):
        raise ValueError("岗位不存在或已停用")
    for pid in valid:
        conn.execute(
            "INSERT INTO sys_user_post (user_id, post_id) VALUES (%s, %s)", (user_id, pid)
        )


def is_locked(profile):
    """账号是否处于锁定期。"""
    if not profile or not profile.get("locked_until"):
        return False
    try:
        return datetime.strptime(str(profile["locked_until"]), "%Y-%m-%d %H:%M:%S") > datetime.now()
    except (TypeError, ValueError):
        return False


def lock_window():
    """锁定截止时间（字符串，MySQL DATETIME 兼容格式）。"""
    return (datetime.now() + timedelta(minutes=pwd_policy()["lockMinutes"])).strftime("%Y-%m-%d %H:%M:%S")
