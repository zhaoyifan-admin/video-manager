"""扩展接口：观看进度 / 审核结果通知（/api）。

存储体检、路径重定位、管理员看板已移至主系统控制台（/api/video-admin/admin），
视频子系统仅保留与本人日常观看相关的接口。
"""
from flask import Blueprint, g, request

import db
from auth import require_login, visible_sql
from responses import ok, fail

bp = Blueprint("extra", __name__, url_prefix="/api")


def _visible_video(video_id):
    vis_sql, vis_args = visible_sql(g.user)
    return db.query(
        f"SELECT id FROM videos v WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args), one=True,
    )


# ---------- 观看进度 / 续播 ----------
@bp.get("/videos/<int:video_id>/progress")
@require_login
def get_progress(video_id):
    if not _visible_video(video_id):
        return fail("视频不存在", 404)
    row = db.query(
        "SELECT position_seconds, duration_seconds, updated_at FROM watch_history "
        "WHERE user_id = %s AND video_id = %s",
        (g.user["id"], video_id), one=True,
    )
    return ok({
        "position": row["position_seconds"] if row else 0,
        "duration": row["duration_seconds"] if row else 0,
        "updatedAt": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row else "",
    })


@bp.post("/videos/<int:video_id>/progress")
@require_login
def save_progress(video_id):
    """播放页定期上报进度；看到 95% 以上视为看完，进度归零便于下次重看"""
    if not _visible_video(video_id):
        return fail("视频不存在", 404)
    data = request.get_json(silent=True) or {}
    try:
        position = max(0, float(data.get("position") or 0))
        duration = max(0, float(data.get("duration") or 0))
    except (TypeError, ValueError):
        return fail("进度参数无效")
    if duration > 0 and position / duration >= 0.95:
        position = 0
    db.execute(
        "INSERT INTO watch_history (user_id, video_id, position_seconds, duration_seconds) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE position_seconds = VALUES(position_seconds), "
        "duration_seconds = VALUES(duration_seconds)",
        (g.user["id"], video_id, position, duration),
    )
    return ok({"position": position})


@bp.get("/watch-history")
@require_login
def recent_watch():
    """当前用户最近观看（用于「继续观看」）"""
    rows = db.query(
        "SELECT v.id, v.title, w.position_seconds, w.duration_seconds, w.updated_at "
        "FROM watch_history w JOIN videos v ON v.id = w.video_id "
        "WHERE w.user_id = %s AND w.position_seconds > 0 "
        "ORDER BY w.updated_at DESC LIMIT 20",
        (g.user["id"],),
    )
    return ok({"items": [{
        "id": r["id"], "title": r["title"],
        "position": r["position_seconds"], "duration": r["duration_seconds"],
        "updatedAt": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
    } for r in rows]})


# ---------- 审核结果通知 ----------
@bp.get("/notifications/unread-count")
@require_login
def unread_count():
    """本人被驳回且未读的记录数（导航角标）"""
    row = db.query(
        "SELECT COUNT(*) AS c FROM video_audit_logs l "
        "JOIN videos v ON v.id = l.video_id "
        "WHERE v.user_id = %s AND l.action = 'reject' AND l.read_at IS NULL",
        (g.user["id"],), one=True,
    )
    return ok({"count": row["c"]})


@bp.get("/notifications")
@require_login
def notifications():
    rows = db.query(
        "SELECT l.id, l.video_id, l.reason, l.operator_name, l.created_at, l.read_at, v.title "
        "FROM video_audit_logs l JOIN videos v ON v.id = l.video_id "
        "WHERE v.user_id = %s AND l.action = 'reject' "
        "ORDER BY l.id DESC LIMIT 100",
        (g.user["id"],),
    )
    return ok({"items": [{
        "id": r["id"], "videoId": r["video_id"], "title": r["title"],
        "reason": r["reason"], "operatorName": r["operator_name"],
        "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        "read": r["read_at"] is not None,
    } for r in rows]})


@bp.post("/notifications/read")
@require_login
def mark_notifications_read():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    sql = (
        "UPDATE video_audit_logs l JOIN videos v ON v.id = l.video_id "
        "SET l.read_at = NOW() "
        "WHERE v.user_id = %s AND l.action = 'reject' AND l.read_at IS NULL"
    )
    args = [g.user["id"]]
    if isinstance(ids, list) and ids:
        ids = [int(x) for x in ids if str(x).isdigit()]
        if not ids:
            return ok({"updated": 0})
        sql += f" AND l.id IN ({','.join(['%s'] * len(ids))})"
        args.extend(ids)
    result = db.execute(sql, args)
    return ok({"updated": result["rowcount"]})
