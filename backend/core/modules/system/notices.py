"""P2 通知公告：管理端 CRUD / 发布 / 撤回，用户端已读回执与未读数。

可见性统一由状态 + 时间决定：状态 PUBLISHED、publish_at 已到、且未被撤回。
定时发布采用惰性发布（查询时把到点的 SCHEDULED 转为 PUBLISHED），
单进程/多进程都幂等，无需后台线程；撤回只改状态，不清空已读回执。
"""
from datetime import datetime

from flask import Blueprint, g, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from .support import page_args

bp = Blueprint("system_notices", __name__)

NOTICE_TYPES = ("NOTICE", "ANNOUNCEMENT")
STATUSES = ("DRAFT", "SCHEDULED", "PUBLISHED", "WITHDRAWN")
VISIBLE_SQL = (
    "n.status = 'PUBLISHED' AND (n.publish_at IS NULL OR n.publish_at <= NOW()) "
    "AND (n.withdraw_at IS NULL OR n.withdraw_at > NOW())"
)


def _datetime(value):
    """兼容 datetime-local（YYYY-MM-DDTHH:mm）与 MySQL DATETIME 字符串。"""
    text = str(value or "").strip()
    if not text or text.lower() in ("null", "none"):
        return None
    text = text.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError("时间格式应为 YYYY-MM-DD HH:mm 或 YYYY-MM-DD HH:mm:ss")


def _lazy_publish():
    """到点的定时公告在任意读取入口自动转正式发布，条件更新天然幂等。"""
    db.execute(
        "UPDATE sys_notice SET status = 'PUBLISHED' "
        "WHERE status = 'SCHEDULED' AND publish_at IS NOT NULL AND publish_at <= NOW()"
    )


def _row(row):
    return {
        "id": row["id"], "title": row["title"], "contentMd": row["content_md"] or "",
        "noticeType": row["notice_type"], "publishAt": row["publish_at"],
        "withdrawAt": row["withdraw_at"], "status": row["status"],
        "publisherName": row.get("publisher_name") or "",
        "readCount": row.get("read_count", 0),
    }


def _get_notice(notice_id):
    return db.query("SELECT * FROM sys_notice WHERE id = %s", (notice_id,), one=True)


# ---------------- 管理端 ----------------

@bp.get("/notices")
@require_login
@require_perm("system:notice:list")
def list_notices():
    _lazy_publish()
    page, size = page_args()
    keyword = (request.args.get("keyword") or "").strip()
    notice_type = (request.args.get("noticeType") or "").strip()
    status = (request.args.get("status") or "").strip()
    where, args = [], []
    if keyword:
        where.append("n.title LIKE %s")
        args.append(f"%{keyword}%")
    if notice_type in NOTICE_TYPES:
        where.append("n.notice_type = %s")
        args.append(notice_type)
    if status in STATUSES:
        where.append("n.status = %s")
        args.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.query(f"SELECT COUNT(*) c FROM sys_notice n {clause}", args, one=True)["c"]
    rows = db.query(
        "SELECT n.*, u.username publisher_name, "
        "(SELECT COUNT(*) FROM sys_notice_receipt r WHERE r.notice_id = n.id) read_count "
        f"FROM sys_notice n LEFT JOIN users u ON u.id = n.publisher_id {clause} "
        "ORDER BY COALESCE(n.publish_at, n.created_at) DESC, n.id DESC "
        "LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_row(row) for row in rows], "total": total,
               "page": page, "pageSize": size})


@bp.post("/notices")
@require_login
@require_perm("system:notice:create")
def create_notice():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    content = str(data.get("contentMd") or "").strip()
    notice_type = str(data.get("noticeType") or "NOTICE").strip()
    if not title or not content:
        return fail("标题与正文不能为空")
    if notice_type not in NOTICE_TYPES:
        return fail("公告类型不合法")
    try:
        publish_at = _datetime(data.get("publishAt"))
        withdraw_at = _datetime(data.get("withdrawAt"))
    except ValueError as exc:
        return fail(str(exc))
    status = str(data.get("status") or "DRAFT").strip()
    if status not in STATUSES:
        return fail("公告状态不合法")
    if status == "SCHEDULED" and not publish_at:
        return fail("定时发布必须指定发布时间")
    if status == "PUBLISHED":
        publish_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "DRAFT":
        # 草稿即使填了 publishAt 也不进入轮询，必须显式发布。
        status = "DRAFT"
    result = db.execute(
        "INSERT INTO sys_notice (title, content_md, notice_type, publish_at, withdraw_at, "
        "publisher_id, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (title, content, notice_type, publish_at, withdraw_at,
         g.user["id"], status),
    )
    return ok({"id": result["lastrowid"]})


@bp.put("/notices/<int:notice_id>")
@require_login
@require_perm("system:notice:update")
def update_notice(notice_id):
    data = request.get_json(silent=True) or {}
    existing = _get_notice(notice_id)
    if not existing:
        return fail("公告不存在", 404)
    if existing["status"] == "WITHDRAWN":
        return fail("已撤回的公告不可编辑")
    title = str(data.get("title") or existing["title"]).strip()
    content = str(data.get("contentMd") or existing["content_md"]).strip()
    notice_type = str(data.get("noticeType") or existing["notice_type"]).strip()
    if not title or not content or notice_type not in NOTICE_TYPES:
        return fail("标题、正文或公告类型不合法")
    try:
        publish_at = _datetime(data.get("publishAt", existing["publish_at"]))
        withdraw_at = _datetime(data.get("withdrawAt", existing["withdraw_at"]))
    except ValueError as exc:
        return fail(str(exc))
    if existing["status"] == "SCHEDULED" and not publish_at:
        return fail("定时发布必须保留发布时间")
    db.execute(
        "UPDATE sys_notice SET title = %s, content_md = %s, notice_type = %s, "
        "publish_at = %s, withdraw_at = %s WHERE id = %s",
        (title, content, notice_type, publish_at, withdraw_at, notice_id),
    )
    return ok({"id": notice_id})


@bp.delete("/notices/<int:notice_id>")
@require_login
@require_perm("system:notice:delete")
def delete_notice(notice_id):
    if not _get_notice(notice_id):
        return fail("公告不存在", 404)
    db.execute("DELETE FROM sys_notice WHERE id = %s", (notice_id,))
    return ok({"id": notice_id})


@bp.post("/notices/<int:notice_id>/publish")
@require_login
@require_perm("system:notice:publish")
def publish_notice(notice_id):
    existing = _get_notice(notice_id)
    if not existing:
        return fail("公告不存在", 404)
    if existing["status"] == "WITHDRAWN":
        return fail("已撤回的公告不可再次发布")
    db.execute(
        "UPDATE sys_notice SET status = 'PUBLISHED', publish_at = NOW(), withdraw_at = NULL "
        "WHERE id = %s",
        (notice_id,),
    )
    return ok({"id": notice_id, "status": "PUBLISHED"})


@bp.post("/notices/<int:notice_id>/withdraw")
@require_login
@require_perm("system:notice:withdraw")
def withdraw_notice(notice_id):
    if not _get_notice(notice_id):
        return fail("公告不存在", 404)
    db.execute(
        "UPDATE sys_notice SET status = 'WITHDRAWN', withdraw_at = NOW() WHERE id = %s",
        (notice_id,),
    )
    return ok({"id": notice_id, "status": "WITHDRAWN"})


# ---------------- 用户端 ----------------

@bp.get("/notices/mine")
@require_login
@require_perm("system:notice:read")
def my_notices():
    _lazy_publish()
    page, size = page_args()
    user_id = g.user["id"]
    total = db.query(
        f"SELECT COUNT(*) c FROM sys_notice n WHERE {VISIBLE_SQL}", one=True
    )["c"]
    rows = db.query(
        "SELECT n.*, u.username publisher_name, "
        "CASE WHEN r.read_at IS NULL THEN 0 ELSE 1 END AS read_flag "
        "FROM sys_notice n LEFT JOIN users u ON u.id = n.publisher_id "
        "LEFT JOIN sys_notice_receipt r ON r.notice_id = n.id AND r.user_id = %s "
        f"WHERE {VISIBLE_SQL} ORDER BY n.publish_at DESC, n.id DESC LIMIT %s OFFSET %s",
        [user_id, size, (page - 1) * size],
    )
    items = [{**_row(row), "read": bool(row["read_flag"])} for row in rows]
    return ok({"items": items, "total": total, "page": page, "pageSize": size})


@bp.get("/notices/unread-count")
@require_login
@require_perm("system:notice:read")
def unread_count():
    _lazy_publish()
    row = db.query(
        "SELECT COUNT(*) c FROM sys_notice n "
        "LEFT JOIN sys_notice_receipt r ON r.notice_id = n.id AND r.user_id = %s "
        f"WHERE {VISIBLE_SQL} AND r.read_at IS NULL",
        (g.user["id"],), one=True,
    )
    return ok({"count": row["c"]})


@bp.post("/notices/<int:notice_id>/read")
@require_login
@require_perm("system:notice:read")
def mark_read(notice_id):
    _lazy_publish()
    visible = db.query(
        f"SELECT n.id FROM sys_notice n WHERE n.id = %s AND {VISIBLE_SQL}",
        (notice_id,), one=True,
    )
    if not visible:
        return fail("公告不存在或已撤回", 404)
    db.execute(
        "INSERT INTO sys_notice_receipt (notice_id, user_id, read_at) VALUES (%s, %s, NOW()) "
        "ON DUPLICATE KEY UPDATE read_at = read_at",
        (notice_id, g.user["id"]),
    )
    return ok({"id": notice_id, "read": True})
