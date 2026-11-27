"""站点管理：从视频子系统搬移的数据看板 / 存储体检 / 操作审计。

权限改用 RBAC：video:admin:view（看板/列表只读）、video:admin:manage（路径重定位）、
video:admin:log（操作审计流水）。超管在 RBAC 中持有全部权限码，行为等价。

账号与角色统一在平台 P1 用户管理（/api/system/users）维护：其写入经 sync_user_roles
同时落 sys_user_role 与 users.role 快照，避免两处写库导致权限不一致。这里不再提供用户管理接口。

看板与存储逻辑复用 backend/video 的 storage 辅助模块与相同 SQL，保持口径一致。
"""
import os
from datetime import date, timedelta

from flask import Blueprint, g, request

import db
from auth import require_login
from admin_audit_logs import ACTION_TEXT, TARGET_TEXT, record, serialize_log
from responses import fail, ok
from storage import media_roots, resolve_video_path, validate_media_path
from core.security import require_perm

bp = Blueprint("video_admin_site", __name__)


# ---------- 数据看板 ----------
def _day_series(days):
    today = date.today()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _view_trend(days=14):
    series = _day_series(days)
    rows = db.query(
        "SELECT view_date AS d, COUNT(*) AS c FROM video_view_daily "
        "WHERE view_date >= %s GROUP BY view_date", (series[0],),
    )
    by_day = {r["d"]: int(r["c"]) for r in rows}
    return [{"date": d.strftime("%m-%d"), "fullDate": d.isoformat(),
             "views": by_day.get(d, 0)} for d in series]


def _hot_tags(limit=8):
    rows = db.query(
        "SELECT t.id, t.name, COUNT(vt.video_id) AS video_count, "
        "COALESCE(SUM(v.view_count), 0) AS total_views "
        "FROM tags t JOIN video_tags vt ON vt.tag_id = t.id "
        "JOIN videos v ON v.id = vt.video_id "
        "WHERE t.is_published = 1 GROUP BY t.id, t.name "
        "ORDER BY video_count DESC, total_views DESC LIMIT %s", (limit,),
    )
    return [{"id": r["id"], "name": r["name"],
             "videoCount": int(r["video_count"]), "totalViews": int(r["total_views"] or 0)}
            for r in rows]


def _storage_growth(days=30):
    series = _day_series(days)
    start = series[0]
    rows = db.query(
        "SELECT DATE(created_at) AS d, COUNT(*) AS videos, "
        "SUM(CASE WHEN file_path IS NOT NULL AND file_path <> '' "
        "AND file_path NOT LIKE 'http://%%' AND file_path NOT LIKE 'https://%%' THEN 1 ELSE 0 END) AS measured "
        "FROM videos WHERE DATE(created_at) >= %s GROUP BY DATE(created_at)", (start,),
    )
    by_day = {r["d"]: r for r in rows}
    points, cum_bytes, cum_videos, unmeasured = [], 0, 0, 0
    for d in series:
        r = by_day.get(d)
        added_videos = int(r["videos"]) if r else 0
        added_bytes = 0
        if r:
            bucket = db.query(
                "SELECT file_path FROM videos WHERE DATE(created_at) = %s "
                "AND file_path IS NOT NULL AND file_path <> '' "
                "AND file_path NOT LIKE 'http://%%' AND file_path NOT LIKE 'https://%%'", (d,)
            )
            for item in bucket:
                resolved = resolve_video_path(item["file_path"])
                if resolved and os.path.isfile(resolved):
                    added_bytes += os.path.getsize(resolved)
                else:
                    unmeasured += 1
        cum_videos += added_videos
        cum_bytes += added_bytes
        points.append({
            "date": d.strftime("%m-%d"), "fullDate": d.isoformat(),
            "addedVideos": added_videos, "addedBytes": added_bytes,
            "cumulativeVideos": cum_videos, "cumulativeBytes": cum_bytes,
        })
    return {"points": points, "totalVideos": cum_videos, "totalBytes": cum_bytes,
            "unmeasured": unmeasured}


@bp.get("/admin/overview")
@require_login
@require_perm("video:admin:view")
def overview():
    counts = db.query(
        "SELECT COUNT(*) AS total, SUM(audit_status = 0) AS pending, "
        "SUM(audit_status = 1) AS approved, SUM(audit_status = 2) AS rejected, "
        "SUM(is_public = 1) AS public, COALESCE(SUM(view_count), 0) AS views FROM videos",
        one=True,
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
        "WHERE s.action = 'submit' AND a.action = 'approve' AND a.id > s.id", one=True,
    )["h"]
    hot = db.query(
        "SELECT id, title, view_count, "
        "(SELECT COUNT(*) FROM video_favorites f WHERE f.video_id = videos.id) AS favorite_count "
        "FROM videos ORDER BY (view_count + (SELECT COUNT(*) FROM video_favorites f "
        "WHERE f.video_id = videos.id) * 5) DESC, id DESC LIMIT 5"
    )
    return ok({
        "videos": {k: int(v or 0) for k, v in counts.items()},
        "users": users, "favorites": favorites, "addedLast7Days": weekly,
        "avgAuditHours": round(float(avg_hours), 1) if avg_hours is not None else None,
        "hot": [{"id": r["id"], "title": r["title"], "viewCount": r["view_count"],
                 "favoriteCount": r["favorite_count"]} for r in hot],
        "viewTrend": _view_trend(14), "hotTags": _hot_tags(8),
        "storageGrowth": _storage_growth(30),
    })


# ---------- 存储体检与路径重定位 ----------
@bp.get("/admin/integrity")
@require_login
@require_perm("video:admin:view")
def integrity():
    rows = db.query("SELECT id, title, file_path FROM videos")
    missing = []
    for r in rows:
        if r["file_path"] and r["file_path"].lower().startswith(("http://", "https://")):
            continue
        if not r["file_path"] or not resolve_video_path(r["file_path"]):
            missing.append({"id": r["id"], "title": r["title"], "filePath": r["file_path"]})
    return ok({"total": len(rows), "missing": missing, "roots": media_roots()})


@bp.post("/admin/relocate")
@require_login
@require_perm("video:admin:manage")
def relocate():
    data = request.get_json(silent=True) or {}
    old_prefix = (data.get("oldPrefix") or "").strip()
    new_prefix = (data.get("newPrefix") or "").strip()
    if not old_prefix or not new_prefix or old_prefix == new_prefix:
        return fail("请填写不同的旧前缀与新前缀")
    _, err = validate_media_path(new_prefix.rstrip("/\\") + "/sample.mp4")
    if err:
        return fail(f"新前缀无效：{err}")
    dry_run = bool(data.get("dryRun"))
    rows = db.query("SELECT id, file_path FROM videos")
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


# ---------- 操作审计 ----------
@bp.get("/admin/logs")
@require_login
@require_perm("video:admin:log")
def list_admin_logs():
    keyword = (request.args.get("keyword") or "").strip()
    action = (request.args.get("action") or "").strip()
    target_type = (request.args.get("targetType") or "").strip()
    days = request.args.get("days", 0, type=int) or 0
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 15, type=int) or 15, 1), 100)
    conditions, args = ["TRUE"], []
    if keyword:
        like = f"%{keyword}%"
        conditions.append("(l.target_name LIKE %s OR l.operator_name LIKE %s OR l.detail LIKE %s)")
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
    where = "WHERE " + " AND ".join(conditions)
    total = db.query(f"SELECT COUNT(*) c FROM admin_audit_logs l {where}", args, one=True)["c"]
    rows = db.query(
        f"SELECT l.* FROM admin_audit_logs l {where} ORDER BY l.id DESC LIMIT %s OFFSET %s",
        args + [page_size, (page - 1) * page_size],
    )
    return ok({
        "total": total, "page": page, "pageSize": page_size,
        "actionOptions": [{"value": k, "label": v} for k, v in ACTION_TEXT.items()],
        "targetOptions": [{"value": k, "label": v} for k, v in TARGET_TEXT.items()],
        "items": [serialize_log(r) for r in rows],
    })
