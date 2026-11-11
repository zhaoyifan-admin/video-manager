"""审核留痕查询接口：/api/audit-logs（超管与独立审核员的全局流水）"""
from flask import Blueprint, request

import db
from audit_logs import ACTION_TEXT, serialize_log
from auth import require_auditor, require_login
from responses import ok, fail

bp = Blueprint("audit_logs", __name__, url_prefix="/api/audit-logs")

_FROM_SQL = """
    FROM video_audit_logs l
    LEFT JOIN videos v ON v.id = l.video_id
    LEFT JOIN users u ON u.id = v.user_id
"""


@bp.get("")
@require_login
@require_auditor
def list_audit_logs():
    """按时间倒序查看全部审核动作，支持关键词（影片/上传者/审核人/理由）与动作筛选"""
    keyword = (request.args.get("keyword") or "").strip()
    action = (request.args.get("action") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 12, type=int) or 12, 1), 100)

    conditions, args = ["TRUE"], []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            "(v.title LIKE %s OR u.username LIKE %s OR l.operator_name LIKE %s OR l.reason LIKE %s)"
        )
        args.extend([like, like, like, like])
    if action:
        if action not in ACTION_TEXT:
            return fail("审核动作筛选值无效")
        conditions.append("l.action = %s")
        args.append(action)
    where_sql = f"WHERE {' AND '.join(conditions)}"

    total = db.query(f"SELECT COUNT(*) AS total {_FROM_SQL} {where_sql}", args, one=True)["total"]
    rows = db.query(
        "SELECT l.*, v.title AS video_title, u.username AS owner_name "
        f"{_FROM_SQL} {where_sql} ORDER BY l.id DESC LIMIT %s OFFSET %s",
        [*args, page_size, (page - 1) * page_size],
    )
    return ok({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [serialize_log(r) for r in rows],
    })
