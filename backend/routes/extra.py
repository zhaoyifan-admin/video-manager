"""扩展接口：观看进度 / 审核通知 / 存储体检 / 路径重定位 / 合集 / 管理员看板（/api）

与 videos.py 分开，保持核心业务文件聚焦。
"""
from flask import Blueprint, g, request

import db
from auth import manageable_sql, require_admin, require_login, visible_sql
from responses import ok, fail
from storage import media_roots, resolve_video_path, validate_media_path

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


# ---------- 存储体检与路径重定位 ----------
@bp.get("/videos/integrity")
@require_login
def integrity():
    """检查有权管理的视频源文件是否还在（外接硬盘未挂载 / 文件被移走）"""
    mg_sql, mg_args = manageable_sql(g.user)
    rows = db.query(
        f"SELECT id, title, file_path FROM videos WHERE {mg_sql}", mg_args
    )
    missing = []
    for r in rows:
        if r["file_path"] and r["file_path"].lower().startswith(("http://", "https://")):
            continue
        if not r["file_path"] or not resolve_video_path(r["file_path"]):
            missing.append({"id": r["id"], "title": r["title"], "filePath": r["file_path"]})
    return ok({
        "total": len(rows),
        "missing": missing,
        "roots": media_roots(),
    })


@bp.post("/videos/relocate")
@require_login
def relocate():
    """批量把 filePath 的旧前缀换成新前缀（换硬盘 / 改盘符 / 换机器时用）。
    只替换字符串，不视为内容变更，因此不触发重新审核。"""
    data = request.get_json(silent=True) or {}
    old_prefix = (data.get("oldPrefix") or "").strip()
    new_prefix = (data.get("newPrefix") or "").strip()
    if not old_prefix or not new_prefix or old_prefix == new_prefix:
        return fail("请填写不同的旧前缀与新前缀")
    _, err = validate_media_path(new_prefix.rstrip("/\\") + "/sample.mp4")
    if err:
        return fail(f"新前缀无效：{err}")

    dry_run = bool(data.get("dryRun"))
    mg_sql, mg_args = manageable_sql(g.user)
    rows = db.query(
        f"SELECT id, file_path FROM videos WHERE {mg_sql}", mg_args
    )
    updated, invalid = 0, []
    for r in rows:
        path = r["file_path"] or ""
        if not path.startswith(old_prefix):
            continue
        new_path = new_prefix + path[len(old_prefix):]
        stored, path_error = validate_media_path(new_path)
        if path_error:
            invalid.append({"title": path, "msg": path_error})
            continue
        if not dry_run:
            db.execute("UPDATE videos SET file_path = %s WHERE id = %s", (stored, r["id"]))
        updated += 1
    return ok({"updated": updated, "invalid": invalid, "dryRun": dry_run})


# ---------- 合集 ----------
@bp.get("/collections")
@require_login
def list_collections():
    rows = db.query(
        "SELECT c.id, c.name, c.description, c.created_at, "
        "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
        "FROM collections c ORDER BY c.name"
    )
    return ok({"items": [{
        "id": r["id"], "name": r["name"], "description": r["description"],
        "videoCount": r["video_count"],
    } for r in rows]})


@bp.post("/collections")
@require_login
def create_collection():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > 100:
        return fail("合集名称需 1-100 个字符")
    if db.query("SELECT id FROM collections WHERE name = %s", (name,), one=True):
        return fail("同名合集已存在")
    result = db.execute(
        "INSERT INTO collections (name, description) VALUES (%s, %s)",
        (name, (data.get("description") or "").strip()[:500]),
    )
    return ok({"id": result["lastrowid"]})


@bp.delete("/collections/<int:collection_id>")
@require_login
@require_admin
def delete_collection(collection_id):
    result = db.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
    if result["rowcount"] == 0:
        return fail("合集不存在", 404)
    return ok()


# ---------- 管理员看板 ----------
@bp.get("/admin/overview")
@require_login
@require_admin
def overview():
    """总量 / 审核分布 / 近 7 天新增 / 平均审核时长 / 热门视频"""
    counts = db.query(
        "SELECT COUNT(*) AS total, "
        "SUM(audit_status = 0) AS pending, SUM(audit_status = 1) AS approved, "
        "SUM(audit_status = 2) AS rejected, SUM(is_public = 1) AS public, "
        "COALESCE(SUM(view_count), 0) AS views "
        "FROM videos", one=True,
    )
    users = db.query("SELECT COUNT(*) AS c FROM users", one=True)["c"]
    favorites = db.query("SELECT COUNT(*) AS c FROM video_favorites", one=True)["c"]
    weekly = db.query(
        "SELECT COUNT(*) AS c FROM videos WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
        one=True,
    )["c"]
    avg_hours = db.query(
        "SELECT AVG(TIMESTAMPDIFF(HOUR, s.created_at, a.created_at)) AS h "
        "FROM video_audit_logs s JOIN video_audit_logs a ON a.video_id = s.video_id "
        "WHERE s.action = 'submit' AND a.action = 'approve' AND a.id > s.id",
        one=True,
    )["h"]
    hot = db.query(
        "SELECT id, title, view_count, "
        "(SELECT COUNT(*) FROM video_favorites f WHERE f.video_id = videos.id) AS favorite_count "
        "FROM videos ORDER BY (view_count + (SELECT COUNT(*) FROM video_favorites f "
        "WHERE f.video_id = videos.id) * 5) DESC, id DESC LIMIT 5"
    )
    return ok({
        "videos": {k: int(v or 0) for k, v in counts.items()},
        "users": users,
        "favorites": favorites,
        "addedLast7Days": weekly,
        "avgAuditHours": round(float(avg_hours), 1) if avg_hours is not None else None,
        "hot": [{
            "id": r["id"], "title": r["title"],
            "viewCount": r["view_count"], "favoriteCount": r["favorite_count"],
        } for r in hot],
    })
