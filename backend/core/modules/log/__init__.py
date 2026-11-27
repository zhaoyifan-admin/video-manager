"""日志审计查询接口：/api/logs/*（P3 引入）。

三个接口均要求登录 + 对应权限码，并叠加 @data_scope 数据范围：
  - 超管 / 审核员（ALL）：可见全部；
  - 管理员（DEPT_TREE）：可见本部门及后代部门操作者的日志；
  - 普通用户（SELF）：仅可见本人的日志。

写入侧统一脱敏，读取侧只做序列化，不再回传完整请求体或堆栈。
"""
from flask import Blueprint, request

import db
from auth import current_user, require_login
from responses import ok
from core.security import data_scope, require_perm

bp = Blueprint("log", __name__, url_prefix="/api/logs")


def _page_args():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(200, max(1, int(request.args.get("pageSize", 10))))
    except (TypeError, ValueError):
        size = 10
    return page, size


def _query(table, alias, owner_field, select, filters=None, order="id DESC"):
    """带数据范围的分页查询；g.scope_sql / g.scope_params 由 @data_scope 注入。

    filters 为 (查询参数名, SQL 列白名单) 列表，值统一走 LIKE 参数化。
    """
    from flask import g
    page, size = _page_args()
    conditions = [g.scope_sql]
    args = list(g.scope_params)
    for param, column in filters or []:
        value = (request.args.get(param) or "").strip()
        if value:
            conditions.append(f"{alias}.{column} LIKE %s")
            args.append(f"%{value}%")
    where = "WHERE " + " AND ".join(conditions)
    total = db.query(
        f"SELECT COUNT(*) c FROM {table} {alias} {where}", args, one=True
    )["c"]
    rows = db.query(
        f"SELECT {select} FROM {table} {alias} {where} ORDER BY {alias}.{order} "
        "LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return rows, total, page, size


@bp.get("/operations")
@require_login
@require_perm("log:operation:list")
@data_scope(owner_field="operator_id", table_alias="l")
def list_operations():
    rows, total, page, size = _query(
        "sys_operate_log", "l", "operator_id",
        "l.id, l.operator_id, l.operator_snapshot, l.module_code, l.action_code, "
        "l.target_snapshot, l.request_path, l.success_flag, l.cost_ms, l.created_at",
        filters=[("moduleCode", "module_code"), ("requestPath", "request_path")],
    )
    return ok({
        "items": [{
            "id": r["id"], "operatorId": r["operator_id"],
            "operator": _parse(r["operator_snapshot"]),
            "moduleCode": r["module_code"], "actionCode": r["action_code"],
            "target": _parse(r["target_snapshot"]), "requestPath": r["request_path"],
            "success": bool(r["success_flag"]), "costMs": r["cost_ms"],
            "createdAt": str(r["created_at"]),
        } for r in rows],
        "total": total, "page": page, "pageSize": size,
    })


@bp.get("/logins")
@require_login
@require_perm("log:login:list")
@data_scope(owner_field="user_id", table_alias="l")
def list_logins():
    rows, total, page, size = _query(
        "sys_login_log", "l", "user_id",
        "l.id, l.user_id, l.account_snapshot, l.login_ip, l.result_flag, "
        "l.fail_reason, l.created_at",
        filters=[("account", "account_snapshot")],
    )
    return ok({
        "items": [{
            "id": r["id"], "userId": r["user_id"],
            "account": r["account_snapshot"], "loginIp": r["login_ip"],
            "success": bool(r["result_flag"]), "failReason": r["fail_reason"],
            "createdAt": str(r["created_at"]),
        } for r in rows],
        "total": total, "page": page, "pageSize": size,
    })


@bp.get("/exceptions")
@require_login
@require_perm("log:exception:list")
@data_scope(owner_field="user_id", table_alias="l")
def list_exceptions():
    rows, total, page, size = _query(
        "sys_exception_log", "l", "user_id",
        "l.id, l.user_id, l.request_path, l.exception_type, l.message_digest, l.created_at",
        filters=[("exceptionType", "exception_type"), ("requestPath", "request_path")],
    )
    return ok({
        "items": [{
            "id": r["id"], "userId": r["user_id"], "requestPath": r["request_path"],
            "exceptionType": r["exception_type"], "messageDigest": r["message_digest"],
            "createdAt": str(r["created_at"]),
        } for r in rows],
        "total": total, "page": page, "pageSize": size,
    })


def _parse(text):
    """反序列化审计快照，失败时原样返回字符串。"""
    import json
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text
