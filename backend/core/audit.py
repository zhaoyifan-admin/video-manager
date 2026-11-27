"""审计写入与数据范围生成（P3）。

设计约束：
1. 审计失败不能影响主流程：record_* 内部吞掉异常，只记录到应用日志；
2. 敏感字段（密码 / 令牌 / 密钥）递归脱敏后才落库；
3. 数据范围只生成参数化 SQL 片段与参数列表，禁止插值请求输入；
4. 视频公开可见规则仍由 auth.visible_sql 独立保留，本模块不触碰视频子系统。
"""
import json
import time
from flask import g, has_app_context, request

import db

# 命中即脱敏（大小写不敏感，支持 camelCase 与 snake_case）。
SENSITIVE_KEYS = {
    "password", "passwordhash", "oldpassword", "newpassword", "pwd", "oldpwd", "newpwd",
    "token", "accesstoken", "refreshtoken", "secret", "clientsecret", "apikey",
    "password_hash", "confirm_password", "confirmpassword",
}
MASK = "***"

# 多角色取最宽范围：ALL > DEPT_TREE > DEPT/CUSTOM > SELF。
SCOPE_RANK = {"SELF": 1, "DEPT": 2, "CUSTOM": 2, "DEPT_TREE": 3, "ALL": 4}


def mask_payload(value):
    """递归脱敏：dict 的敏感 key 置为 ***，list 逐项处理，其他原样返回。"""
    if isinstance(value, dict):
        return {
            key: (MASK if str(key).lower().replace("_", "") in
                  {k.replace("_", "") for k in SENSITIVE_KEYS}
                  else mask_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_payload(item) for item in value]
    return value


def _dump(value, limit=4000):
    """安全序列化为 JSON 字符串；超长截断，避免把整个请求体塞进日志。"""
    try:
        text = json.dumps(mask_payload(value), ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001 - 审计容错
        text = str(value)[:limit]
    return text[:limit]


def _actor():
    if not has_app_context():
        return None
    return g.get("user")


def _login_ip():
    if not has_app_context():
        return ""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def record_login(user_id=0, account="", success=True, fail_reason=""):
    """登录审计：成功与失败都记，失败且账号不存在时 user_id=0。"""
    try:
        db.execute(
            "INSERT INTO sys_login_log "
            "(user_id, account_snapshot, login_ip, result_flag, fail_reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (int(user_id or 0), str(account or "")[:128], _login_ip(),
             1 if success else 0, str(fail_reason or "")[:128]),
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响登录
        pass


def record_operate(module, action, success=True, target=None):
    """操作审计：由平台 after_request 统一调用，快照自动脱敏。"""
    try:
        user = _actor() or {}
        if target is None and has_app_context():
            target = request.get_json(silent=True)
        started = g.get("_audit_start") if has_app_context() else None
        cost_ms = int((time.monotonic() - started) * 1000) if started else 0
        snapshot = {
            "id": user.get("id", 0),
            "username": user.get("username", ""),
            "role": user.get("role", ""),
        }
        path = request.path if has_app_context() else ""
        method = request.method if has_app_context() else ""
        db.execute(
            "INSERT INTO sys_operate_log "
            "(operator_id, operator_snapshot, module_code, action_code, target_snapshot, "
            "request_path, success_flag, cost_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (int(user.get("id") or 0), _dump(snapshot, 255), str(module)[:64],
             str(action)[:64], _dump(target), f"{method} {path}"[:300],
             1 if success else 0, min(cost_ms, 60000)),
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响业务响应
        pass


def record_exception(exc):
    """异常审计：只存类型与摘要，不落完整堆栈。"""
    try:
        user = _actor() or {}
        path = request.path if has_app_context() else ""
        method = request.method if has_app_context() else ""
        db.execute(
            "INSERT INTO sys_exception_log "
            "(user_id, request_path, exception_type, message_digest) "
            "VALUES (%s, %s, %s, %s)",
            (int(user.get("id") or 0), f"{method} {path}"[:300],
             type(exc).__name__[:128], str(exc)[:500]),
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响错误响应
        pass


def _user_roles(user):
    """角色编码集合；直接走 sys_user_role，缺表时回退 users.role 快照。"""
    try:
        rows = db.query(
            "SELECT r.role_code FROM sys_user_role ur "
            "JOIN sys_role r ON r.id = ur.role_id "
            "WHERE ur.user_id = %s AND r.status = 1",
            (user["id"],),
        ) or []
    except Exception:  # noqa: BLE001 - 缺表兼容
        rows = []
    return [row["role_code"] for row in rows] or [user.get("role") or "user"]


def effective_scope(user):
    """当前用户最宽的数据范围编码；内置角色未配置时按 users.role 兜底。"""
    if not user:
        return "SELF"
    codes = _user_roles(user)
    try:
        marks = ",".join(["%s"] * len(codes))
        rows = db.query(
            f"SELECT role_code, data_scope FROM sys_role "
            f"WHERE status = 1 AND role_code IN ({marks})", codes,
        ) or []
    except Exception:  # noqa: BLE001 - 缺表兼容
        rows = []
    scopes = [row["data_scope"] for row in rows if row["data_scope"] in SCOPE_RANK]
    if not scopes:
        legacy = user.get("role") or "user"
        return "ALL" if legacy == "admin" else ("DEPT_TREE" if legacy == "manager" else "SELF")
    return max(scopes, key=lambda code: SCOPE_RANK[code])


def _dept_of(user_id):
    row = db.query(
        "SELECT dept_id FROM sys_user_profile WHERE user_id = %s", (user_id,), one=True
    )
    return int(row["dept_id"]) if row and row["dept_id"] else 0


def scope_clause(user, owner_field="user_id", table_alias=""):
    """返回 (SQL 片段, 参数列表)，供列表接口参数化拼接。

    owner_field 必须由调用方显式传入白名单字段，禁止来自请求参数。
    """
    if not user:
        return "FALSE", []
    scope = effective_scope(user)
    alias = f"{table_alias}." if table_alias else ""
    owner = f"{alias}{owner_field}"

    if scope == "ALL":
        return "TRUE", []
    if scope == "SELF":
        return f"{owner} = %s", [user["id"]]

    dept_id = _dept_of(user["id"])
    if not dept_id:
        # 未分配部门：DEPT / DEPT_TREE / CUSTOM 都退化为仅本人，避免越权放大。
        return f"{owner} = %s", [user["id"]]

    if scope == "DEPT":
        return (
            f"{owner} IN (SELECT user_id FROM sys_user_profile WHERE dept_id = %s)",
            [dept_id],
        )

    if scope == "DEPT_TREE":
        row = db.query(
            "SELECT ancestor_path FROM sys_dept WHERE id = %s", (dept_id,), one=True
        )
        base = (row or {}).get("ancestor_path") or "/"
        pattern = f"{base}{dept_id}/%"
        return (
            f"{owner} IN (SELECT p.user_id FROM sys_user_profile p "
            f"JOIN sys_dept d ON d.id = p.dept_id "
            f"WHERE d.id = %s OR d.ancestor_path LIKE %s)",
            [dept_id, pattern],
        )

    # CUSTOM：sys_role_dept 限定的部门集合；未配置部门时退化为仅本人。
    codes = _user_roles(user)
    try:
        marks = ",".join(["%s"] * len(codes))
        role_rows = db.query(
            f"SELECT id FROM sys_role WHERE status = 1 AND role_code IN ({marks})", codes
        ) or []
        role_ids = [row["id"] for row in role_rows]
    except Exception:  # noqa: BLE001 - 缺表兼容
        role_ids = []
    if not role_ids:
        return f"{owner} = %s", [user["id"]]
    marks = ",".join(["%s"] * len(role_ids))
    return (
        f"{owner} IN (SELECT user_id FROM sys_user_profile WHERE dept_id IN "
        f"(SELECT dept_id FROM sys_role_dept WHERE role_id IN ({marks})))",
        role_ids,
    )
