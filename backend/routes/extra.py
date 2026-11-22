"""扩展接口：观看进度 / 审核通知 / 存储体检 / 路径重定位 / 管理员看板（/api）

与 videos.py 分开，保持核心业务文件聚焦。
合集已独立为 routes/collections.py（接入审核模型），管理员操作审计见 routes/admin_logs.py。
"""
import os
from datetime import date, timedelta

from flask import Blueprint, g, request

import db
from admin_audit_logs import record
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
    if not dry_run and updated:
        record(g.user, "relocate_videos", "path", None, f"{old_prefix} → {new_prefix}",
               f"更新 {updated} 条记录")
    return ok({"updated": updated, "invalid": invalid, "dryRun": dry_run})


# 说明：合集已接入审核模型，相关接口迁移至 routes/collections.py（独立蓝图），
# 此处不再重复注册 /api/collections 路由，避免同名规则冲突。

# ---------- 管理员看板 ----------
# ---------- 看板增强：观看趋势 / 热门标签 / 存储增长 ----------
def _day_series(days):
    """生成含今天在内的连续日期序列（补零，前端不必再对齐空档）"""
    today = date.today()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _view_trend(days=14):
    """近 N 天每日去重播放量（video_view_daily 一用户一视频一天只记一次）"""
    series = _day_series(days)
    rows = db.query(
        "SELECT view_date AS d, COUNT(*) AS c FROM video_view_daily "
        "WHERE view_date >= %s GROUP BY view_date",
        (series[0],),
    )
    by_day = {r["d"]: int(r["c"]) for r in rows}
    return [{"date": d.strftime("%m-%d"), "fullDate": d.isoformat(),
             "views": by_day.get(d, 0)} for d in series]


def _hot_tags(limit=8):
    """已发布标签按关联影片数排序，附带这些影片的累计播放量"""
    rows = db.query(
        "SELECT t.id, t.name, COUNT(vt.video_id) AS video_count, "
        "COALESCE(SUM(v.view_count), 0) AS total_views "
        "FROM tags t JOIN video_tags vt ON vt.tag_id = t.id "
        "JOIN videos v ON v.id = vt.video_id "
        "WHERE t.is_published = 1 GROUP BY t.id, t.name "
        "ORDER BY video_count DESC, total_views DESC LIMIT %s",
        (limit,),
    )
    return [{"id": r["id"], "name": r["name"],
             "videoCount": int(r["video_count"]), "totalViews": int(r["total_views"] or 0)}
            for r in rows]


def _storage_growth(days=30):
    """近 N 天「按入库日归属」的存储增长曲线。

    口径：每条影片的实际源文件大小计入其 created_at 当天；外链与磁盘上已找不到
    的文件不计字节（仍计入影片数），仅在 unmeasured 中给出数量，避免曲线虚高。
    """
    series = _day_series(days)
    rows = db.query("SELECT file_path, DATE(created_at) AS d FROM videos")
    base = {"videos": 0, "bytes": 0}
    buckets = {}
    unmeasured = 0
    for r in rows:
        path = r["file_path"] or ""
        size = 0
        if path and not path.lower().startswith(("http://", "https://")):
            full = resolve_video_path(path)
            if full and os.path.isfile(full):
                try:
                    size = os.path.getsize(full)
                except OSError:
                    unmeasured += 1
            else:
                unmeasured += 1
        d = r["d"]
        if d < series[0]:
            base["videos"] += 1
            base["bytes"] += size
        else:
            bucket = buckets.setdefault(d, {"videos": 0, "bytes": 0})
            bucket["videos"] += 1
            bucket["bytes"] += size

    cum_v, cum_b = base["videos"], base["bytes"]
    points = []
    for d in series:
        bucket = buckets.get(d, {"videos": 0, "bytes": 0})
        cum_v += bucket["videos"]
        cum_b += bucket["bytes"]
        points.append({
            "date": d.strftime("%m-%d"), "fullDate": d.isoformat(),
            "addedVideos": bucket["videos"], "addedBytes": bucket["bytes"],
            "cumulativeVideos": cum_v, "cumulativeBytes": cum_b,
        })
    return {
        "points": points,
        "totalVideos": cum_v,
        "totalBytes": cum_b,
        "unmeasured": unmeasured,
    }


@bp.get("/admin/overview")
@require_login
@require_admin
def overview():
    """总量 / 审核分布 / 平均审核时长 / 热门视频 + 观看趋势 / 热门标签 / 存储增长"""
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
        "viewTrend": _view_trend(14),
        "hotTags": _hot_tags(8),
        "storageGrowth": _storage_growth(30),
    })
