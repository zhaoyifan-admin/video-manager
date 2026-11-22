"""管理员操作审计查询：/api/admin-logs（仅超级管理员）"""
from flask import Blueprint, request

import db
from admin_audit_logs import ACTION_TEXT, serialize_log
from auth import require_admin, require_login
from responses import ok, fail

bp = Blueprint("admin_logs", __name__, url_prefix="/api/admin-logs")


@bp.get("")
@require_login
@require_admin
def list_admin_logs():
    """按时间倒序查看敏感管理动作，支持关键词、动作、对象类型与时间范围筛选"""
    keyword = (request.args.get("keyword") or "").strip()
    action = (request.args.get("action") or "").strip()
    target_type = (request.args.get("targetType") or "").strip()
    days = request.args.get("days", 0, type=int) or 0
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 15, type=int) or 15, 1), 100)

    conditions, args = ["TRUE"], []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            "(l.target_name LIKE %s OR l.operator_name LIKE %s OR l.detail LIKE %s)"
        )
        args.extend([like, like, like])
    if action:
        if action not in ACTION_TEXT:
            return fail("动作筛选值无效")
        conditions.append("l.action = %s")
        args.append(action)
    if target_type:
        conditions.append("l.target_type = %s")
        args.append(target_type)
    if days > 0:
        conditions.append("l.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)")
        args.append(min(days, 365))
    where_sql = f"WHERE {' AND '.join(conditions)}"

    total = db.query(
        f"SELECT COUNT(*) AS total FROM admin_audit_logs l {where_sql}", args, one=True
    )["total"]
    rows = db.query(
        f"SELECT l.* FROM admin_audit_logs l {where_sql} "
        "ORDER BY l.id DESC LIMIT %s OFFSET %s",
        [*args, page_size, (page - 1) * page_size],
    )
    return ok({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "actionOptions": [{"value": k, "label": v} for k, v in ACTION_TEXT.items()],
        "items": [serialize_log(r) for r in rows],
    })
