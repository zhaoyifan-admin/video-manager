"""审核中心：从视频子系统搬移的视频审核动作、全局流水与单视频时间线。

权限改用 RBAC：video:audit:list（查看列表/流水）、video:audit:review（审核动作）。
视频侧保留 GET /api/videos/<id>/audit-logs 供「审核结果」页使用，本模块提供
管理视角的等价接口（放宽到审核角色），两者写同一张 video_audit_logs，互不冲突。

manager 只能审核平级及以下用户的视频（ROLE_LEVELS）这一业务规则保持不变。
"""
from flask import Blueprint, g, request

import db
from auth import ROLE_LEVELS, require_login
from responses import fail, ok
from audit_logs import ACTION_TEXT, add_log, serialize_log
from core.security import has_permission, require_perm

bp = Blueprint("video_audit", __name__)

_SELECT = """
    SELECT v.id, v.title, v.file_path, v.description, v.type_id, v.view_count,
           v.is_public, v.audit_status, v.audit_reason, v.user_id AS owner_id,
           v.created_at, v.updated_at,
           tp.name AS type_name, u.username AS owner_name,
           (SELECT l.action FROM video_audit_logs l
            WHERE l.video_id = v.id ORDER BY l.id DESC LIMIT 1) AS last_action
    FROM videos v
    LEFT JOIN types tp ON tp.id = v.type_id
    LEFT JOIN users u ON u.id = v.user_id
"""

_STATUS_TEXT = {0: "待审核", 1: "已通过", 2: "已驳回"}


@bp.get("/audit/videos")
@require_login
@require_perm("video:audit:list")
def list_audit_videos():
    """审核列表：超管/审核员看全部；管理员只看平级及以下用户。"""
    keyword = (request.args.get("keyword") or "").strip()
    audit_status = request.args.get("auditStatus", type=int)
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 10, type=int) or 10, 1), 100)

    conditions, args = [], []
    if g.user["role"] == "manager":
        conditions.append("v.user_id IN (SELECT id FROM users WHERE role IN ('manager','reviewer','user'))")
    if keyword:
        like = f"%{keyword}%"
        conditions.append("(v.title LIKE %s OR v.description LIKE %s OR u.username LIKE %s)")
        args.extend([like, like, like])
    if audit_status in (0, 1, 2):
        conditions.append("v.audit_status = %s")
        args.append(audit_status)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.query(f"SELECT COUNT(*) c FROM videos v LEFT JOIN users u ON u.id = v.user_id {where}",
                     args, one=True)["c"]
    rows = db.query(
        f"{_SELECT} {where} ORDER BY FIELD(v.audit_status, 0, 2, 1), v.updated_at DESC, v.id DESC "
        "LIMIT %s OFFSET %s", args + [page_size, (page - 1) * page_size],
    )
    items = [{
        "id": r["id"], "title": r["title"], "filePath": r["file_path"],
        "ownerId": r["owner_id"], "ownerName": r["owner_name"],
        "typeName": r["type_name"], "isPublic": bool(r["is_public"]),
        "auditStatus": r["audit_status"], "auditReason": r["audit_reason"] or "",
        "lastAction": r["last_action"] or "", "viewCount": r["view_count"],
        "createdAt": str(r["created_at"]),
    } for r in rows]
    return ok({"items": items, "total": total, "page": page, "pageSize": page_size})


@bp.post("/audit/videos/<int:video_id>/review")
@require_login
@require_perm("video:audit:review")
def review_video(video_id):
    """审核视频：status 1 通过 / 2 驳回（驳回必填理由并收回公开）。"""
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in (1, 2):
        return fail("审核状态无效（1 通过 / 2 驳回）")
    reason = (data.get("reason") or "").strip()
    if status == 2:
        if not reason:
            return fail("请填写驳回理由，上传用户需要知道未通过的原因")
        if len(reason) > 500:
            return fail("驳回理由过长（最多 500 个字符）")

    row = db.query(
        "SELECT v.id, v.audit_status, u.role AS owner_role "
        "FROM videos v JOIN users u ON u.id = v.user_id WHERE v.id = %s",
        (video_id,), one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    if g.user["role"] == "manager" and ROLE_LEVELS.get(row["owner_role"], 1) > ROLE_LEVELS["manager"]:
        return fail("管理员只能审核平级及以下用户的视频", 403)

    old_status = row["audit_status"]
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            if status == 2:
                cur.execute(
                    "UPDATE videos SET audit_status = 2, audit_reason = %s, is_public = 0 WHERE id = %s",
                    (reason, video_id),
                )
            else:
                cur.execute(
                    "UPDATE videos SET audit_status = 1, audit_reason = '' WHERE id = %s", (video_id,)
                )
            add_log(
                conn, video_id, "reject" if status == 2 else "approve",
                old_status, status, g.user,
                reason if status == 2 else "审核通过，允许在影库中展示",
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"auditStatus": status, "auditReason": reason if status == 2 else ""})


@bp.get("/audit/logs")
@require_login
@require_perm("video:audit:list")
def list_audit_logs():
    """全局审核流水：关键词（影片/上传者/审核人/理由）+ 动作筛选。"""
    keyword = (request.args.get("keyword") or "").strip()
    action = (request.args.get("action") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 10, type=int) or 10, 1), 100)

    conditions, args = [], []
    if keyword:
        like = f"%{keyword}%"
        conditions.append("(v.title LIKE %s OR u.username LIKE %s OR l.operator_name LIKE %s OR l.reason LIKE %s)")
        args.extend([like, like, like, like])
    if action:
        if action not in ACTION_TEXT:
            return fail("审核动作筛选值无效")
        conditions.append("l.action = %s")
        args.append(action)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    from_sql = (
        "FROM video_audit_logs l LEFT JOIN videos v ON v.id = l.video_id "
        "LEFT JOIN users u ON u.id = v.user_id"
    )
    total = db.query(f"SELECT COUNT(*) c {from_sql} {where}", args, one=True)["c"]
    rows = db.query(
        f"SELECT l.*, v.title AS video_title, u.username AS owner_name {from_sql} {where} "
        "ORDER BY l.id DESC LIMIT %s OFFSET %s", args + [page_size, (page - 1) * page_size],
    )
    return ok({
        "items": [{**serialize_log(r), "videoTitle": r["video_title"] or "（视频已删除）",
                   "ownerName": r["owner_name"] or ""} for r in rows],
        "total": total, "page": page, "pageSize": page_size,
        "actionOptions": [{"value": k, "label": v} for k, v in ACTION_TEXT.items()],
    })


@bp.get("/audit/videos/<int:video_id>/logs")
@require_login
@require_perm("video:audit:list")
def video_timeline(video_id):
    """管理视角的单视频审核时间线（含驳回理由历史）。"""
    if not db.query("SELECT id FROM videos WHERE id = %s", (video_id,), one=True):
        return fail("视频不存在", 404)
    rows = db.query(
        "SELECT * FROM video_audit_logs WHERE video_id = %s ORDER BY id DESC", (video_id,)
    )
    return ok({"items": [serialize_log(r) for r in rows]})
