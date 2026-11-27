"""影视类型接口：/api/types

视频侧仅保留日常功能：
- GET  /api/types  视频表单下拉：审核角色看全部，普通用户看已发布 + 自己提交的条目；
- POST /api/types  普通用户提交新类型，进入待审核。

类型的审核、发布 / 下架、改名、删除、审核留痕已移至主系统控制台
（/api/video-admin/taxonomy/type），视频侧不再提供管理接口。
"""
from flask import Blueprint, g, request

import db
from auth import can_audit, is_super_admin, require_login
from responses import ok, fail
from type_audit_logs import add_log

bp = Blueprint("types", __name__, url_prefix="/api/types")


def _serialize(row, viewer_id, admin_view):
    """序列化类型（保留最小字段集，管理字段仅对审核角色或创建者可见）。"""
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


def _fetch_row(type_id):
    return db.query(
        "SELECT t.*, u.username AS created_by_name "
        "FROM types t LEFT JOIN users u ON u.id = t.created_by WHERE t.id = %s",
        (type_id,),
        one=True,
    )


@bp.get("")
@require_login
def list_types():
    """类型列表：审核角色看全部（含待审/驳回与创建者），其他用户看已发布 + 自己提交的"""
    admin_view = can_audit(g.user)
    if admin_view:
        rows = db.query(
            "SELECT t.*, u.username AS created_by_name FROM types t "
            "LEFT JOIN users u ON u.id = t.created_by ORDER BY t.name ASC"
        )
    else:
        rows = db.query(
            "SELECT t.* FROM types t WHERE t.is_published = 1 OR t.created_by = %s ORDER BY t.name ASC",
            (g.user["id"],),
        )
    return ok([_serialize(r, g.user["id"], admin_view) for r in rows])


@bp.post("")
@require_login
def create_type():
    """新建类型：普通用户进入待审核；管理员可选 isPublished 直接发布。

    改名 / 下架 / 删除 / 审核等管理动作已移至主系统控制台。
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail("类型名不能为空")
    if len(name) > 50:
        return fail("类型名过长（最多 50 个字符）")
    existing = db.query(
        "SELECT id, name, audit_status FROM types WHERE name = %s", (name,), one=True
    )
    if existing:
        if existing["audit_status"] == 1:
            return ok(_serialize(_fetch_row(existing["id"]), g.user["id"], can_audit(g.user)))
        return fail(f"类型「{name}」已存在，正在审核或已被驳回，请勿重复提交")

    if is_super_admin(g.user):
        publish = bool(data.get("isPublished"))
        audit_status = 1 if publish else 0
        type_id = db.execute(
            "INSERT INTO types (name, is_published, audit_status, created_by) VALUES (%s, %s, %s, %s)",
            (name, 1 if publish else 0, audit_status, g.user["id"]),
        )["lastrowid"]
        add_log(
            type_id, "auto_approve" if publish else "submit",
            None, audit_status, g.user["id"], g.user["username"],
        )
    else:
        type_id = db.execute(
            "INSERT INTO types (name, is_published, audit_status, created_by) VALUES (%s, 0, 0, %s)",
            (name, g.user["id"]),
        )["lastrowid"]
        add_log(type_id, "submit", None, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(type_id), g.user["id"], can_audit(g.user)))
