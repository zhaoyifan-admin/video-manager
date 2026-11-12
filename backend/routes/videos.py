"""视频业务接口：列表 / 详情 / 增删改 / 收藏 / 批量导入（/api/videos）
所有接口均要求登录，且只能操作当前用户自己的视频数据。
"""
import os
from datetime import date

from flask import Blueprint, g, request

import config
import db
from audit_logs import add_log, serialize_log
from auth import (
    LOWER_ROLES_SQL, ROLE_LEVELS, can_audit, is_super_admin, manageable_sql,
    require_admin, require_auditor, require_login, visible_sql,
)
from responses import ok, fail
from storage import (
    ALLOWED_SUBTITLE_EXTS, delete_source_file, resolve_video_path,
    validate_asset_path, validate_media_path,
)
from thumbnails import remove_thumb, schedule_generation

bp = Blueprint("videos", __name__, url_prefix="/api/videos")

# 关联查询公共字段（列表与详情共用；owner 为视频归属用户）
_SELECT_VIDEO = """
    SELECT v.id, v.title, v.file_path, v.subtitle_path, v.collection_id,
           v.description, v.type_id, v.view_count,
           v.is_public, v.audit_status, v.audit_reason, v.user_id AS owner_id,
           v.created_at, v.updated_at,
           (SELECT COUNT(*) FROM video_favorites f WHERE f.video_id = v.id) AS favorite_count,
           GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR '||') AS tag_names,
           tp.name AS type_name, u.username AS owner_name, c.name AS collection_name,
           (SELECT l.action FROM video_audit_logs l
            WHERE l.video_id = v.id ORDER BY l.id DESC LIMIT 1) AS last_action
    FROM videos v
    LEFT JOIN video_tags vt ON vt.video_id = v.id
    LEFT JOIN tags t ON t.id = vt.tag_id
    LEFT JOIN types tp ON tp.id = v.type_id
    LEFT JOIN collections c ON c.id = v.collection_id
    LEFT JOIN users u ON u.id = v.user_id
"""


def serialize_video(row):
    tag_names = row["tag_names"].split("||") if row.get("tag_names") else []
    return {
        "id": row["id"],
        "title": row["title"],
        "filePath": row["file_path"],
        "subtitlePath": row.get("subtitle_path") or "",
        "collectionId": row.get("collection_id"),
        "collectionName": row.get("collection_name") or "",
        "typeId": row.get("type_id"),
        "typeName": row.get("type_name"),
        # 是否收藏由 attach_favorites 按当前用户填充；收藏量是全库累计人数
        "isFavorite": False,
        "favoriteCount": row.get("favorite_count") or 0,
        "viewCount": row.get("view_count") or 0,
        "isPublic": bool(row.get("is_public")),
        "auditStatus": row.get("audit_status"),
        "auditReason": row.get("audit_reason") or "",
        # 最近一次审核动作：管理员上传的视频为 auto_approve（免审通过），界面可据此区分
        "lastAction": row.get("last_action") or "",
        "ownerId": row.get("owner_id"),
        "ownerName": row.get("owner_name"),
        "description": row["description"],
        "tags": tag_names,
        "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }


def attach_favorites(items):
    """给已序列化的视频填充「当前用户是否已收藏」。
    收藏是按用户存的，同一视频对不同用户的 isFavorite 可以不同"""
    if not items:
        return items
    ids = [x["id"] for x in items]
    placeholders = ",".join(["%s"] * len(ids))
    rows = db.query(
        f"SELECT video_id FROM video_favorites WHERE user_id = %s AND video_id IN ({placeholders})",
        (g.user["id"], *ids),
    )
    fav_ids = {r["video_id"] for r in rows}
    for item in items:
        item["isFavorite"] = item["id"] in fav_ids
    return items


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
    # 路径安全边界：只允许已登记媒体目录内的视频文件，挡住任意本机文件读写
    stored_path, path_error = validate_media_path(file_path)
    if path_error:
        return None, None, None, None, None, path_error
    file_path = stored_path
    for name in tag_names:
        if len(name) > 50:
            return None, None, None, None, None, f"标签「{name}」过长（最多 50 个字符）"
        if "|" in name:
            return None, None, None, None, None, "标签名不能包含竖线 |（该字符为内部分隔符）"
    tag_names = list(dict.fromkeys(tag_names))  # 去重且保持顺序
    return title, file_path, description, tag_names, type_id, None


def _validate_extras(data):
    """校验字幕路径与合集，返回 (subtitle_path, collection_id, 错误信息)"""
    subtitle, err = validate_asset_path(
        data.get("subtitlePath") or "", ALLOWED_SUBTITLE_EXTS, "字幕"
    )
    if err:
        return None, None, err
    raw = data.get("collectionId")
    if raw in (None, "", 0, "0"):
        return subtitle, None, None
    try:
        collection_id = int(raw)
    except (TypeError, ValueError):
        return None, None, "合集 ID 无效"
    if not db.query("SELECT id FROM collections WHERE id = %s", (collection_id,), one=True):
        return None, None, "合集不存在"
    return subtitle, collection_id, None


def _check_quota(extra=1):
    """单用户视频数配额；返回错误信息或 None"""
    limit = int(getattr(config, "MAX_VIDEOS_PER_USER", 0) or 0)
    if limit <= 0:
        return None
    count = db.query(
        "SELECT COUNT(*) AS c FROM videos WHERE user_id = %s", (g.user["id"],), one=True
    )["c"]
    if count + extra > limit:
        return f"已达单用户视频上限（{limit} 条），请联系管理员"
    return None


def _schedule_thumb(video_id, file_path):
    """入库后后台预生成封面，避免首屏同步跑 ffmpeg"""
    path = resolve_video_path(file_path)
    if path:
        schedule_generation(video_id, path)


def save_video_tags(conn, video_id, tag_names, allow_create=False):
    """重建视频的标签关联：先清空旧关联，再逐个匹配标签。

    标签统一由管理员管理发布：普通用户提交的未知 / 未发布标签静默忽略；
    allow_create=True（超管）时未知标签直接创建并发布，已存在的不论发布与否都可挂。"""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM video_tags WHERE video_id = %s", (video_id,))
        for name in tag_names:
            if allow_create:
                cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
            else:
                cur.execute(
                    "SELECT id FROM tags WHERE name = %s AND is_published = 1", (name,)
                )
            row = cur.fetchone()
            tag_id = row["id"] if row else None
            if tag_id is None:
                if not allow_create:
                    continue  # 不存在的标签由管理员在标签管理中创建，这里静默忽略
                cur.execute("INSERT INTO tags (name, is_published) VALUES (%s, 1)", (name,))
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
    audit_status = request.args.get("auditStatus", type=int)  # 审核筛选：0 待审核 / 1 已通过 / 2 已驳回
    scope = (request.args.get("scope") or "gallery").strip()  # gallery 主影库 / audit 审核中心 / mine 我的提交
    sort = (request.args.get("sort") or "updated").strip()  # updated/created/hot/views/title
    owner_id = request.args.get("ownerId", type=int)
    collection_id = request.args.get("collectionId", type=int)
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = min(max(request.args.get("pageSize", 10, type=int) or 10, 1), 100)

    # 按查询范围确定可见条件
    if scope == "gallery":
        # 主影库：只展示已通过审核的可见视频（未过审的不进影库）
        base_sql, base_args = visible_sql(g.user)
        conditions, args = [base_sql, "v.audit_status = 1"], base_args
    elif scope == "audit":
        # 审核中心：超管/审核员查看所有用户、所有状态；管理员只看平级及以下用户
        if not can_audit(g.user):
            return fail("需要审核权限", 403)
        if g.user["role"] == "manager":
            conditions, args = [f"v.user_id IN (SELECT id FROM users WHERE role IN {LOWER_ROLES_SQL})"], []
        else:
            conditions, args = ["TRUE"], []
    elif scope == "mine":
        # 我的提交：本人所有状态（含待审/驳回，用于查看驳回理由并重新上传）
        conditions, args = ["v.user_id = %s"], [g.user["id"]]
    else:
        return fail("查询范围无效")

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
        # 我的收藏：按当前登录用户的收藏记录筛选（不再是视频上的全局开关）
        conditions.append("v.id IN (SELECT video_id FROM video_favorites WHERE user_id = %s)")
        args.append(g.user["id"])
    if audit_status in (0, 1, 2):
        conditions.append("v.audit_status = %s")
        args.append(audit_status)
    if owner_id:
        conditions.append("v.user_id = %s")
        args.append(owner_id)
    if collection_id:
        conditions.append("v.collection_id = %s")
        args.append(collection_id)
    where_sql = f"WHERE {' AND '.join(conditions)}"

    total = db.query(
        f"SELECT COUNT(*) AS total FROM videos v {where_sql}", args, one=True
    )["total"]

    order_sql = {
        "updated": "v.updated_at DESC, v.id DESC",
        "created": "v.created_at DESC, v.id DESC",
        "hot": "(v.view_count + favorite_count * 5) DESC, v.updated_at DESC, v.id DESC",
        "views": "v.view_count DESC, v.id DESC",
        "title": "v.title ASC, v.id DESC",
    }.get(sort, "v.updated_at DESC, v.id DESC")

    sql = f"""
        {_SELECT_VIDEO}
        {where_sql}
        GROUP BY v.id
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
    """
    rows = db.query(sql, [*args, page_size, (page - 1) * page_size])
    return ok({
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": attach_favorites([serialize_video(r) for r in rows]),
    })


@bp.get("/featured")
@require_login
def featured_videos():
    """大图轮播数据：当前用户可见且已过审的视频，按热度倒序最多 9 条。
    热度 = 播放次数 + 收藏人数 × 5；热度相同（尤其全为 0 的新库）时按最近更新兜底"""
    limit = min(max(request.args.get("limit", 9, type=int) or 9, 1), 9)
    vis_sql, vis_args = visible_sql(g.user)
    sql = f"""
        {_SELECT_VIDEO}
        WHERE ({vis_sql}) AND v.audit_status = 1
        GROUP BY v.id
        ORDER BY (v.view_count + favorite_count * 5) DESC, v.updated_at DESC, v.id DESC
        LIMIT %s
    """
    rows = db.query(sql, [*vis_args, limit])
    return ok({"items": attach_favorites([serialize_video(r) for r in rows])})


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
    return ok(attach_favorites([serialize_video(row)])[0])


@bp.post("")
@require_login
def create_video():
    data = request.get_json(silent=True) or {}
    title, file_path, description, tag_names, type_id, error = validate_video(data)
    if error:
        return fail(error)
    subtitle, collection_id, error = _validate_extras(data)
    if error:
        return fail(error)
    error = _check_quota()
    if error:
        return fail(error)

    # 管理员自己入库的视频直接通过审核，普通用户入库进入待审核；
    # 未过审一律私有，只有已通过审核才允许按表单意愿设为公开
    status = 1 if is_super_admin(g.user) else 0
    is_public = 1 if (status == 1 and bool(data.get("isPublic"))) else 0

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (user_id, title, file_path, subtitle_path, collection_id, "
                "description, type_id, audit_status, is_public) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (g.user["id"], title, file_path, subtitle, collection_id,
                 description, type_id, status, is_public),
            )
            video_id = cur.lastrowid
        save_video_tags(conn, video_id, tag_names, allow_create=is_super_admin(g.user))
        # 留痕：管理员上传免审通过（auto_approve），普通用户上传进入待审核（submit）
        if status == 1:
            add_log(conn, video_id, "auto_approve", None, 1, g.user, "管理员上传，无需审核直接通过")
        else:
            add_log(conn, video_id, "submit", None, 0, g.user, "上传视频，提交管理员审核")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _schedule_thumb(video_id, file_path)
    return ok({"id": video_id, "auditStatus": status})


@bp.put("/<int:video_id>")
@require_login
def update_video(video_id):
    """编辑视频：仅本人或超级管理员可操作。
    本人的「已驳回」视频保存后自动重新进入待审核并清空驳回理由（重新上传/修正后重新送审）"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT id, user_id, file_path, subtitle_path, audit_status, is_public, audit_reason "
        f"FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权操作", 404)

    data = request.get_json(silent=True) or {}
    title, file_path, description, tag_names, type_id, error = validate_video(data)
    if error:
        return fail(error)
    subtitle, collection_id, error = _validate_extras(data)
    if error:
        return fail(error)

    # 安全关键：内容变更与资料变更必须分开处理。
    # 换了源文件（或字幕）就等于换了一部片，无论当前是否「已通过」，都必须重新送审，
    # 否则可以先上传合规片过审并公开，再把路径改成任意内容绕过审核。
    old_stored, _ = validate_media_path(row["file_path"])
    content_changed = (
        file_path != (old_stored or row["file_path"])
        or subtitle != (row["subtitle_path"] or "")
    )
    rejected_resubmit = row["audit_status"] == 2 and row["user_id"] == g.user["id"]
    resubmit = content_changed or rejected_resubmit
    new_status = 0 if resubmit else row["audit_status"]

    # 公开状态：未过审一律私有；已过审时按表单勾选决定；请求未带 isPublic 则保持原值
    if resubmit or new_status != 1:
        new_public = 0
    elif "isPublic" in data:
        new_public = 1 if bool(data.get("isPublic")) else 0
    else:
        new_public = row["is_public"]

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET title = %s, file_path = %s, subtitle_path = %s, "
                "collection_id = %s, description = %s, type_id = %s, "
                "audit_status = %s, is_public = %s, audit_reason = %s WHERE id = %s",
                (
                    title, file_path, subtitle, collection_id, description, type_id,
                    new_status, new_public, "" if resubmit else row["audit_reason"], video_id,
                ),
            )
        save_video_tags(conn, video_id, tag_names, allow_create=is_super_admin(g.user))
        # 留痕：状态确实发生变化时才记一条，避免「待审核→待审核」的噪声
        if resubmit and row["audit_status"] != 0:
            add_log(
                conn, video_id, "resubmit", row["audit_status"], 0, g.user,
                "更换视频文件后重新提交审核" if content_changed else "按驳回理由修改后重新提交审核",
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if content_changed:
        remove_thumb(video_id)  # 换片后旧封面失效
        _schedule_thumb(video_id, file_path)
    return ok({"resubmitted": resubmit, "auditStatus": new_status, "isPublic": bool(new_public)})


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

    file_deleted, file_missing = delete_source_file(row["file_path"])
    remove_thumb(video_id)  # 同步清理缩略图缓存（存在与否不影响删除结果）
    # fileDeleted: 文件是否已物理删除；fileMissing: 文件本就不存在（仅清理记录）
    # 两者皆 False = 文件存在但删不掉（被占用/白名单外），前端会提示用户手动处理
    return ok({"fileDeleted": file_deleted, "fileMissing": file_missing})


@bp.post("/<int:video_id>/favorite")
@require_login
def favorite_video(video_id):
    """切换当前用户的收藏（可见的视频即可收藏：本人的 / 公开的）。
    收藏按用户存放，多个用户收藏同一视频互不影响"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT id FROM videos WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)

    exists = db.query(
        "SELECT 1 FROM video_favorites WHERE user_id = %s AND video_id = %s",
        (g.user["id"], video_id),
        one=True,
    )
    if exists:
        db.execute(
            "DELETE FROM video_favorites WHERE user_id = %s AND video_id = %s",
            (g.user["id"], video_id),
        )
        is_favorite = False
    else:
        db.execute(
            "INSERT IGNORE INTO video_favorites (user_id, video_id) VALUES (%s, %s)",
            (g.user["id"], video_id),
        )
        is_favorite = True
    count = db.query(
        "SELECT COUNT(*) AS c FROM video_favorites WHERE video_id = %s", (video_id,), one=True
    )["c"]
    return ok({"isFavorite": is_favorite, "favoriteCount": count})


@bp.post("/<int:video_id>/view")
@require_login
def record_view(video_id):
    """打开播放页时记一次点击/播放（可见的视频才可计数）"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT id FROM videos WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    # 同一用户 + 同一视频 + 同一天只累计一次，刷新页面不会把热度刷上去
    inserted = db.execute(
        "INSERT IGNORE INTO video_view_daily (user_id, video_id, view_date) VALUES (%s, %s, %s)",
        (g.user["id"], video_id, date.today()),
    )
    counted = inserted["rowcount"] > 0
    if counted:
        # 显式保持 updated_at 原值，避免播放计数把「最近更新」排序打乱
        db.execute(
            "UPDATE videos SET view_count = view_count + 1, updated_at = updated_at WHERE id = %s",
            (video_id,),
        )
    count = db.query("SELECT view_count FROM videos WHERE id = %s", (video_id,), one=True)["view_count"]
    return ok({"viewCount": count, "counted": counted})


@bp.post("/<int:video_id>/public")
@require_login
def toggle_public(video_id):
    """切换公开状态：设为公开后所有用户可观看（仅本人或超级管理员）。
    前置校验：视频必须已通过审核才允许公开"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT is_public, audit_status FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权操作", 404)
    new_val = 0 if row["is_public"] else 1
    if new_val == 1 and row["audit_status"] != 1:
        return fail("视频尚未通过审核，不能设为公开")
    db.execute("UPDATE videos SET is_public = %s WHERE id = %s", (new_val, video_id))
    return ok({"isPublic": bool(new_val)})


@bp.post("/<int:video_id>/audit")
@require_login
@require_auditor
def audit_video(video_id):
    """管理员审核视频：status 1 通过 / 2 驳回。
    通过：清空驳回理由，视频进入主影库，公开与否由归属者自行设置；
    驳回：必须填写理由（展示给上传用户），并自动收回公开"""
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
        (video_id,),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    # 管理员（manager）只能审核平级及以下用户的视频，超管的视频仅超管/审核员可审
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
                    "UPDATE videos SET audit_status = 1, audit_reason = '' WHERE id = %s",
                    (video_id,),
                )
            # 状态变更与留痕同一事务：记录审核人、变更前后状态、驳回理由
            add_log(
                conn, video_id,
                "reject" if status == 2 else "approve",
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


@bp.get("/<int:video_id>/audit-logs")
@require_login
def video_audit_logs(video_id):
    """单条视频的完整审核时间线：仅归属者本人或超级管理员可查（含驳回理由历史）"""
    mg_sql, mg_args = manageable_sql(g.user)
    row = db.query(
        f"SELECT id FROM videos WHERE id = %s AND {mg_sql}",
        (video_id, *mg_args),
        one=True,
    )
    if not row:
        return fail("视频不存在或无权查看", 404)
    rows = db.query(
        "SELECT * FROM video_audit_logs WHERE video_id = %s ORDER BY id DESC",
        (video_id,),
    )
    return ok({"items": [serialize_log(r) for r in rows]})


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
    error = _check_quota(len(items))
    if error:
        return fail(error)

    success_count, failed, created = 0, [], []
    admin_import = is_super_admin(g.user)  # 管理员导入免审，普通用户导入逐条进入待审核
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
                stored_path, path_error = validate_media_path(file_path)
                if path_error:
                    failed.append({"index": idx, "msg": path_error})
                    continue
                file_path = stored_path

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
                        "INSERT INTO videos (user_id, title, file_path, description, type_id, audit_status) VALUES (%s, %s, %s, %s, %s, %s)",
                        (g.user["id"], title, file_path, description, type_id, 1 if admin_import else 0),
                    )
                    video_id = cur.lastrowid
                except Exception as exc:
                    failed.append({"index": idx, "msg": f"写入失败：{exc}"})
                    continue

                tag_names = list(dict.fromkeys(
                    str(t).strip()[:50] for t in (item.get("tags") or []) if str(t).strip()
                ))[:20]
                for name in tag_names:
                    # 标签由管理员统一管理：普通用户只挂已发布标签（未知/未发布静默忽略），管理员可顺手建新标签
                    if admin_import:
                        cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
                    else:
                        cur.execute(
                            "SELECT id FROM tags WHERE name = %s AND is_published = 1", (name,)
                        )
                    row = cur.fetchone()
                    tag_id = row["id"] if row else None
                    if tag_id is None:
                        if not admin_import:
                            continue
                        cur.execute(
                            "INSERT INTO tags (name, is_published) VALUES (%s, 1)", (name,)
                        )
                        tag_id = cur.lastrowid
                    cur.execute(
                        "INSERT IGNORE INTO video_tags (video_id, tag_id) VALUES (%s, %s)",
                        (video_id, tag_id),
                    )
                # 留痕：批量导入的每一条视频同样记录来源，避免审核历史出现断档
                if admin_import:
                    add_log(conn, video_id, "auto_approve", None, 1, g.user, "管理员批量导入，无需审核直接通过")
                else:
                    add_log(conn, video_id, "submit", None, 0, g.user, "批量导入视频，提交管理员审核")
                created.append((video_id, file_path))
                success_count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for vid, path in created:
        _schedule_thumb(vid, path)
    return ok({"success": success_count, "failed": failed})
