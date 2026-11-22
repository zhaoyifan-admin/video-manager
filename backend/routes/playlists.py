"""用户自建片单（个人片单）：与系统合集(collections，管理员单归属维度)完全隔离。

设计取舍：不复用 collections（videos.collection_id 单归属），改用独立的多对多表
playlists + playlist_videos，普通用户可自由创建/管理自己的片单，与管理页零冲突。

权限：通过 _mine() 校验 user_id == g.user.id 或超管；管理员仅能管理自己的片单，
不能动他人片单。加入片单的视频必须先通过 _visible_video()（复用 visible_sql）校验可见性。
"""
from flask import Blueprint, g, request

import db
from auth import is_super_admin, require_login, visible_sql
from responses import ok, fail

bp = Blueprint("playlists", __name__, url_prefix="/api")


def _mine(playlist_id):
    """校验片单归属：本人或超管。返回 row，无权/不存在返回 None。"""
    row = db.query("SELECT id, user_id, name FROM playlists WHERE id = %s", (playlist_id,), one=True)
    if not row:
        return None
    if row["user_id"] != g.user["id"] and not is_super_admin(g.user):
        return None
    return row


def _visible_video(video_id):
    """只能把当前用户可见（本人的 / 公开的）视频加入片单，复用 visible_sql 保证一致性。"""
    vis_sql, vis_args = visible_sql(g.user)
    return db.query(
        f"SELECT id FROM videos v WHERE id = %s AND {vis_sql}", (video_id, *vis_args), one=True
    )


def _serialize(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "videoCount": row.get("video_count") or 0,
        "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }


@bp.get("/playlists")
@require_login
def list_playlists():
    """列出当前用户自己的全部片单（不含视频明细，明细由前端按需拉取）。"""
    rows = db.query(
        "SELECT p.*, "
        "(SELECT COUNT(*) FROM playlist_videos pv WHERE pv.playlist_id = p.id) AS video_count "
        "FROM playlists p WHERE p.user_id = %s ORDER BY p.updated_at DESC, p.id DESC",
        (g.user["id"],),
    )
    return ok({"items": [_serialize(r) for r in rows]})


@bp.post("/playlists")
@require_login
def create_playlist():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return fail("片单名称不能为空")
    if len(name) > 50:
        return fail("片单名称过长（最多 50 个字符）")
    if len(description) > 500:
        return fail("片单简介过长（最多 500 个字符）")
    try:
        res = db.execute(
            "INSERT INTO playlists (user_id, name, description) VALUES (%s, %s, %s)",
            (g.user["id"], name, description),
        )
    except Exception:
        # uk_user_name 唯一键冲突：同一账号下片单名不可重复
        return fail("片单名称已存在（同一账号下不可重复）", 409)
    row = db.query("SELECT * FROM playlists WHERE id = %s", (res["lastrowid"],), one=True)
    return ok(_serialize(row))


@bp.put("/playlists/<int:playlist_id>")
@require_login
def update_playlist(playlist_id):
    row = _mine(playlist_id)
    if not row:
        return fail("片单不存在或无权操作", 404)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return fail("片单名称不能为空")
    if len(name) > 50:
        return fail("片单名称过长（最多 50 个字符）")
    if len(description) > 500:
        return fail("片单简介过长（最多 500 个字符）")
    try:
        db.execute(
            "UPDATE playlists SET name = %s, description = %s, updated_at = NOW() WHERE id = %s",
            (name, description, playlist_id),
        )
    except Exception:
        return fail("片单名称已存在（同一账号下不可重复）", 409)
    row = db.query("SELECT * FROM playlists WHERE id = %s", (playlist_id,), one=True)
    return ok(_serialize(row))


@bp.delete("/playlists/<int:playlist_id>")
@require_login
def delete_playlist(playlist_id):
    row = _mine(playlist_id)
    if not row:
        return fail("片单不存在或无权操作", 404)
    db.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
    return ok({"id": playlist_id})


@bp.post("/playlists/<int:playlist_id>/videos")
@require_login
def add_video(playlist_id):
    row = _mine(playlist_id)
    if not row:
        return fail("片单不存在或无权操作", 404)
    data = request.get_json(silent=True) or {}
    try:
        video_id = int(data.get("videoId"))
    except (TypeError, ValueError):
        return fail("缺少有效的 videoId")
    if not _visible_video(video_id):
        return fail("视频不存在或无权操作", 404)
    # 顺序号：先查当前片单最大 sort_order 再插入，规避 MySQL「同表子查询不能 UPDATE 同一张表」限制
    max_row = db.query(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS nx FROM playlist_videos WHERE playlist_id = %s",
        (playlist_id,), one=True,
    )
    db.execute(
        "INSERT IGNORE INTO playlist_videos (playlist_id, video_id, sort_order) VALUES (%s, %s, %s)",
        (playlist_id, video_id, max_row["nx"]),
    )
    db.execute("UPDATE playlists SET updated_at = NOW() WHERE id = %s", (playlist_id,))
    return ok({"playlistId": playlist_id, "videoId": video_id})


@bp.delete("/playlists/<int:playlist_id>/videos/<int:video_id>")
@require_login
def remove_video(playlist_id, video_id):
    row = _mine(playlist_id)
    if not row:
        return fail("片单不存在或无权操作", 404)
    db.execute(
        "DELETE FROM playlist_videos WHERE playlist_id = %s AND video_id = %s",
        (playlist_id, video_id),
    )
    db.execute("UPDATE playlists SET updated_at = NOW() WHERE id = %s", (playlist_id,))
    return ok({"playlistId": playlist_id, "videoId": video_id})


@bp.get("/playlists/for-video/<int:video_id>")
@require_login
def playlists_for_video(video_id):
    """返回当前用户的片单列表，并标注每个片单是否已包含该视频（用于「加入片单」弹窗勾选态）。"""
    rows = db.query(
        "SELECT p.id, p.name, "
        "(EXISTS (SELECT 1 FROM playlist_videos pv WHERE pv.playlist_id = p.id AND pv.video_id = %s)) AS added "
        "FROM playlists p WHERE p.user_id = %s ORDER BY p.updated_at DESC",
        (video_id, g.user["id"]),
    )
    return ok({
        "items": [{"id": r["id"], "name": r["name"], "added": bool(r["added"])} for r in rows]
    })
