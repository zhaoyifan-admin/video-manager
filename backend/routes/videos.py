"""视频业务接口：列表 / 详情 / 增删改 / 收藏 / 批量导入（/api/videos）
所有接口均要求登录，且只能操作当前用户自己的视频数据。
"""
import os

from flask import Blueprint, g, request

import db
from auth import is_super_admin, manageable_sql, require_login, visible_sql
from responses import ok, fail
from storage import delete_source_file
from thumbnails import remove_thumb

bp = Blueprint("videos", __name__, url_prefix="/api/videos")

# 关联查询公共字段（列表与详情共用；owner 为视频归属用户）
_SELECT_VIDEO = """
    SELECT v.id, v.title, v.file_path, v.description, v.type_id, v.is_favorite,
           v.is_public, v.user_id AS owner_id, v.created_at, v.updated_at,
           GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR '||') AS tag_names,
           tp.name AS type_name, u.username AS owner_name
    FROM videos v
    LEFT JOIN video_tags vt ON vt.video_id = v.id
    LEFT JOIN tags t ON t.id = vt.tag_id
    LEFT JOIN types tp ON tp.id = v.type_id
    LEFT JOIN users u ON u.id = v.user_id
"""


def serialize_video(row):
    tag_names = row["tag_names"].split("||") if row.get("tag_names") else []
    return {
        "id": row["id"],
        "title": row["title"],
        "filePath": row["file_path"],
        "typeId": row.get("type_id"),
        "typeName": row.get("type_name"),
        "isFavorite": bool(row.get("is_favorite")),
        "isPublic": bool(row.get("is_public")),
        "ownerId": row.get("owner_id"),
        "ownerName": row.get("owner_name"),
        "description": row["description"],
        "tags": tag_names,
        "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }


def validate_video(data):
    """校验请求体，返回 (title, file_path, description, tag_names, type_id, 错误信息)"""
    title = (data.get("title") or "").strip()
    file_path = (data.get("filePath") or "").strip()
    description = (data.get("description") or "").strip()
    tag_names = [str(t).strip() for t in (data.get("tags") or []) if str(t).strip()]
    type_id = data.get("typeId")
    if type_id is not None:
        type_id = int(type_id)
        if not db.query("SELECT id FROM types WHERE id = %s", (type_id,), one=True):
            return None, None, None, None, None, "影视类型不存在"

    if not title:
        return None, None, None, None, None, "视频标题不能为空"
    if len(title) > 200:
        return None, None, None, None, None, "标题过长（最多 200 个字符）"
    if len(file_path) > 500:
        return None, None, None, None, None, "文件路径过长（最多 500 个字符）"
    if len(description) > 1000:
        return None, None, None, None, None, "备注过长（最多 1000 个字符）"
    for name in tag_names:
        if len(name) > 50:
            return None, None, None, None, None, f"标签「{name}」过长（最多 50 个字符）"
    tag_names = list(dict.fromkeys(tag_names))  # 去重且保持顺序
    return title, file_path, description, tag_names, type_id, None


def save_video_tags(conn, video_id, tag_names):
    """重建视频的标签关联：先清空旧关联，再逐个 get_or_create 标签"""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM video_tags WHERE video_id = %s", (video_id,))
        for name in tag_names:
            cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
            row = cur.fetchone()
            tag_id = row["id"] if row else None
            if tag_id is None:
                cur.execute("INSERT INTO tags (name) VALUES (%s)", (name,))
                tag_id = cur.lastrowid
            cur.execute(
                "INSERT IGNORE INTO video_tags (video_id, tag_id) VALUES (%s, %s)",
                (video_id, tag_id),
            )


@bp.get("")
@require_login
def list_videos():
    keyword = (request.args.get("keyword") or "").strip()
    tag_id = request.args.get("tagId", type=int)
    type_id = request.args.get("typeId", type=int)
    favorite = request.args.get("favorite", 0, type=int)
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 10, type=int) or 10, 1), 100)

    # 可见范围：普通用户看自己的 + 公开视频，超级管理员看全部
    base_sql, base_args = visible_sql(g.user)
    conditions, args = [base_sql], base_args
    if keyword:
        like = f"%{keyword}%"
        conditions.append("(v.title LIKE %s OR v.file_path LIKE %s OR v.description LIKE %s)")
        args.extend([like, like, like])
    if tag_id:
        conditions.append("v.id IN (SELECT video_id FROM video_tags WHERE tag_id = %s)")
        args.append(tag_id)
    if type_id:
        conditions.append("v.type_id = %s")
        args.append(type_id)
    if favorite:
        conditions.append("v.is_favorite = 1")
    where_sql = f"WHERE {' AND '.join(conditions)}"

    total = db.query(
        f"SELECT COUNT(*) AS total FROM videos v {where_sql}", args, one=True
    )["total"]

    sql = f"""
        {_SELECT_VIDEO}
        {where_sql}
        GROUP BY v.id
        ORDER BY v.updated_at DESC, v.id DESC
        LIMIT %s OFFSET %s
    """
    rows = db.query(sql, [*args, page_size, (page - 1) * page_size])
    return ok({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [serialize_video(r) for r in rows],
    })


@bp.get("/<int:video_id>")
@require_login
def get_video_detail(video_id):
    """单个视频详情（播放页使用），本人的 / 公开的 / 超管可看"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"{_SELECT_VIDEO} WHERE v.id = %s AND {vis_sql} GROUP BY v.id",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    return ok(serialize_video(row))


@bp.post("")
@require_login
def create_video():
    data = request.get_json(silent=True) or {}
    title, file_path, description, tag_names, type_id, error = validate_video(data)
    if error:
        return fail(error)

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (user_id, title, file_path, description, type_id) VALUES (%s, %s, %s, %s, %s)",
                (g.user["id"], title, file_path, description, type_id),
            )
            video_id = cur.lastrowid
        save_video_tags(conn, video_id, tag_names)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": video_id})


@bp.put("/<int:video_id>")
@require_login
def update_video(video_id):
    """编辑视频：仅本人或超级管理员可操作"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT id FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权操作", 404)

    data = request.get_json(silent=True) or {}
    title, file_path, description, tag_names, type_id, error = validate_video(data)
    if error:
        return fail(error)

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET title = %s, file_path = %s, description = %s, type_id = %s WHERE id = %s",
                (title, file_path, description, type_id, video_id),
            )
        save_video_tags(conn, video_id, tag_names)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok()


@bp.delete("/<int:video_id>")
@require_login
def delete_video(video_id):
    """删除视频：数据库记录 + 磁盘源文件 + 缩略图缓存一并清理（仅本人或超级管理员）"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT file_path FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权操作", 404)
    result = db.execute("DELETE FROM videos WHERE id = %s", (video_id,))
    if result["rowcount"] == 0:
        return fail("视频不存在", 404)

    file_deleted = delete_source_file(row["file_path"])
    remove_thumb(video_id)  # 同步清理缩略图缓存（存在与否不影响删除结果）
    return ok({"fileDeleted": file_deleted})


@bp.post("/<int:video_id>/favorite")
@require_login
def favorite_video(video_id):
    """切换收藏状态（可见的视频即可收藏：本人的 / 公开的）"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT is_favorite FROM videos WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    new_val = 0 if row["is_favorite"] else 1
    db.execute("UPDATE videos SET is_favorite = %s WHERE id = %s", (new_val, video_id))
    return ok({"isFavorite": bool(new_val)})


@bp.post("/<int:video_id>/public")
@require_login
def toggle_public(video_id):
    """切换公开状态：设为公开后所有用户可观看（仅本人或超级管理员）"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT is_public FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权操作", 404)
    new_val = 0 if row["is_public"] else 1
    db.execute("UPDATE videos SET is_public = %s WHERE id = %s", (new_val, video_id))
    return ok({"isPublic": bool(new_val)})


@bp.post("/batch")
@require_login
def batch_import_videos():
    """批量导入：逐条校验写入（归属当前用户），单条失败不影响其余；类型/标签按名称 get_or_create"""
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return fail("请提供要导入的视频列表")
    if len(items) > 500:
        return fail("单次最多导入 500 条")

    success_count, failed = 0, []
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    failed.append({"index": idx, "msg": "格式错误"})
                    continue
                file_path = str(item.get("filePath") or "").strip()
                if not file_path:
                    failed.append({"index": idx, "msg": "缺少文件路径"})
                    continue
                if len(file_path) > 500:
                    failed.append({"index": idx, "msg": "文件路径过长（最多 500 个字符）"})
                    continue

                title = str(item.get("title") or "").strip()
                if not title:
                    # 标题缺省时取路径的文件名部分（去扩展名）
                    title = os.path.splitext(os.path.basename(file_path))[0] or "未命名视频"
                if len(title) > 200:
                    failed.append({"index": idx, "msg": "标题过长（最多 200 个字符）"})
                    continue

                type_name = str(item.get("typeName") or "").strip()[:50]
                type_id = None
                if type_name:
                    cur.execute("SELECT id FROM types WHERE name = %s", (type_name,))
                    row = cur.fetchone()
                    type_id = row["id"] if row else None
                    if type_id is None:
                        cur.execute("INSERT INTO types (name) VALUES (%s)", (type_name,))
                        type_id = cur.lastrowid

                description = str(item.get("description") or "").strip()[:1000]
                try:
                    cur.execute(
                        "INSERT INTO videos (user_id, title, file_path, description, type_id) VALUES (%s, %s, %s, %s, %s)",
                        (g.user["id"], title, file_path, description, type_id),
                    )
                    video_id = cur.lastrowid
                except Exception as exc:
                    failed.append({"index": idx, "msg": f"写入失败：{exc}"})
                    continue

                tag_names = list(dict.fromkeys(
                    str(t).strip()[:50] for t in (item.get("tags") or []) if str(t).strip()
                ))[:20]
                for name in tag_names:
                    cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
                    row = cur.fetchone()
                    tag_id = row["id"] if row else None
                    if tag_id is None:
                        cur.execute("INSERT INTO tags (name) VALUES (%s)", (name,))
                        tag_id = cur.lastrowid
                    cur.execute(
                        "INSERT IGNORE INTO video_tags (video_id, tag_id) VALUES (%s, %s)",
                        (video_id, tag_id),
                    )
                success_count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"success": success_count, "failed": failed})
