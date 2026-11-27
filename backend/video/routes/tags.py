"""标签接口：/api/tags

视频侧仅保留日常功能：
- GET  /api/tags         视频表单用：审核角色看全部，普通用户看已发布 + 自己提交的条目；
- GET  /api/tags/visible 首页标签栏：严格按会话角色裁定可见集合；
- POST /api/tags         普通用户提交新标签，进入待审核。

标签的审核、发布 / 下架、改名、删除、审核留痕已移至主系统控制台
（/api/video-admin/taxonomy/tag），视频侧不再提供管理接口。
"""
from flask import Blueprint, g, request

import db
from auth import can_audit, is_super_admin, require_login
from responses import ok, fail
from tag_audit_logs import add_log

bp = Blueprint("tags", __name__, url_prefix="/api/tags")


def _serialize(row, viewer_id, admin_view):
    """序列化标签（保留最小字段集，管理字段仅对审核角色或创建者可见）。"""
    data = {"id": row["id"], "name": row["name"], "auditStatus": row["audit_status"]}
    is_mine = row["created_by"] == viewer_id
    data["isMine"] = is_mine
    data["isPublished"] = bool(row["is_published"])
    if admin_view:
        data["auditReason"] = row["audit_reason"]
        data["createdBy"] = row["created_by"]
        data["createdByName"] = row.get("created_by_name") or ""
    elif is_mine:
        data["createdBy"] = viewer_id
        data["auditReason"] = row["audit_reason"]
    return data


def _fetch_row(tag_id):
    return db.query(
        "SELECT t.*, u.username AS created_by_name "
        "FROM tags t LEFT JOIN users u ON u.id = t.created_by WHERE t.id = %s",
        (tag_id,),
        one=True,
    )


@bp.get("")
@require_login
def list_tags():
    """标签列表：审核角色看全部（含待审/驳回与创建者），其他用户看已发布 + 自己提交的"""
    admin_view = can_audit(g.user)
    if admin_view:
        rows = db.query(
            "SELECT t.*, u.username AS created_by_name FROM tags t "
            "LEFT JOIN users u ON u.id = t.created_by ORDER BY t.name ASC"
        )
    else:
        rows = db.query(
            "SELECT t.* FROM tags t WHERE t.is_published = 1 OR t.created_by = %s ORDER BY t.name ASC",
            (g.user["id"],),
        )
    return ok([_serialize(r, g.user["id"], admin_view) for r in rows])


def _visible_badge(row):
    """展示视图的状态角标文案：已发布为空，其余标注非公开状态"""
    if row["audit_status"] == 0:
        return "待审核"
    if row["audit_status"] == 2:
        return "已驳回"
    return "" if row["is_published"] else "未发布"


@bp.get("/visible")
@require_login
def visible_tags():
    """标签栏可见集合（展示视图）：可见性完全由后端按会话角色裁定。

    - 超管（role=admin）：全部标签，附 badge（未发布 / 待审核 / 已驳回）供预览；
    - 其他角色：严格只返回 is_published=1 的标签，连自己提交的未发布标签也不返回。
    仅返回展示所需的最小字段集，不携带驳回理由、创建者等管理信息。
    """
    if is_super_admin(g.user):
        rows = db.query(
            "SELECT id, name, is_published, audit_status FROM tags ORDER BY name ASC"
        )
    else:
        rows = db.query(
            "SELECT id, name, is_published, audit_status FROM tags "
            "WHERE is_published = 1 ORDER BY name ASC"
        )
    return ok([
        {
            "id": r["id"],
            "name": r["name"],
            "isPublished": bool(r["is_published"]),
            "auditStatus": r["audit_status"],
            "badge": _visible_badge(r),
        }
        for r in rows
    ])


@bp.post("")
@require_login
def create_tag():
    """新建标签：普通用户进入待审核；管理员可选 isPublished 直接发布。

    改名 / 下架 / 删除 / 审核等管理动作已移至主系统控制台。
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail("标签名不能为空")
    if len(name) > 50:
        return fail("标签名过长（最多 50 个字符）")
    existing = db.query(
        "SELECT id, name, audit_status FROM tags WHERE name = %s", (name,), one=True
    )
    if existing:
        # 同名且已通过：直接返回（幂等）
        if existing["audit_status"] == 1:
            return ok(_serialize(_fetch_row(existing["id"]), g.user["id"], can_audit(g.user)))
        # 同名但待审 / 已驳回：禁止重复提交，避免名称被占用无法重新提交
        return fail(f"标签「{name}」已存在，正在审核或已被驳回，请勿重复提交")

    if is_super_admin(g.user):
        publish = bool(data.get("isPublished"))
        audit_status = 1 if publish else 0
        tag_id = db.execute(
            "INSERT INTO tags (name, is_published, audit_status, created_by) VALUES (%s, %s, %s, %s)",
            (name, 1 if publish else 0, audit_status, g.user["id"]),
        )["lastrowid"]
        add_log(
            tag_id, "auto_approve" if publish else "submit",
            None, audit_status, g.user["id"], g.user["username"],
        )
    else:
        tag_id = db.execute(
            "INSERT INTO tags (name, is_published, audit_status, created_by) VALUES (%s, 0, 0, %s)",
            (name, g.user["id"]),
        )["lastrowid"]
        add_log(tag_id, "submit", None, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(tag_id), g.user["id"], can_audit(g.user)))
