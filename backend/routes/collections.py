"""合集接口：/api/collections

合集审核流程与 tags / types 完全一致（复用 can_audit 权限）：
- 普通用户可提交新合集，进入「待审核」，默认不发布；
- 审核角色对待审合集通过 / 驳回（驳回必填理由）；
- 被驳回的合集，创建者或超级管理员可「重新提交」；
- 所有审核动作写入 collection_audit_logs（只追加、可追溯）。

可见性：普通用户只看「已发布」合集 + 自己提交的合集（含状态）；审核角色看全部。
列表响应保持 {items: [...]} 契约，供视频筛选下拉与分类工作台共用。
"""
from flask import Blueprint, g, request

import db
from admin_audit_logs import record
from auth import can_audit, is_super_admin, require_admin, require_auditor, require_login
from collection_audit_logs import add_log, serialize_log
from responses import ok, fail

bp = Blueprint("collections", __name__, url_prefix="/api/collections")


def _serialize(row, viewer_id, admin_view):
    """序列化合集：所有用户可见 id/name/description/状态/isMine；
    审核角色额外看到创建者与驳回理由，普通用户仅对自己提交的条目可见。"""
    data = {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "videoCount": row.get("video_count") or 0,
        "auditStatus": row["audit_status"],
        "isMine": row["created_by"] == viewer_id,
        "isPublished": bool(row["is_published"]),
    }
    if admin_view:
        data["auditReason"] = row["audit_reason"]
        data["createdBy"] = row["created_by"]
        data["createdByName"] = row.get("created_by_name") or ""
    elif data["isMine"]:
        data["createdBy"] = viewer_id
        data["auditReason"] = row["audit_reason"]
    return data


def _fetch_row(collection_id):
    return db.query(
        "SELECT c.*, u.username AS created_by_name, "
        "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
        "FROM collections c LEFT JOIN users u ON u.id = c.created_by WHERE c.id = %s",
        (collection_id,),
        one=True,
    )


@bp.get("")
@require_login
def list_collections():
    """合集列表：审核角色看全部；其他用户看已发布 + 自己提交的"""
    admin_view = can_audit(g.user)
    if admin_view:
        rows = db.query(
            "SELECT c.*, u.username AS created_by_name, "
            "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
            "FROM collections c LEFT JOIN users u ON u.id = c.created_by ORDER BY c.name ASC"
        )
    else:
        rows = db.query(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
            "FROM collections c WHERE c.is_published = 1 OR c.created_by = %s ORDER BY c.name ASC",
            (g.user["id"],),
        )
    return ok({"items": [_serialize(r, g.user["id"], admin_view) for r in rows]})


@bp.post("")
@require_login
def create_collection():
    """新建合集：超管可直接发布（免审通过）或留作未发布，普通用户进入待审核"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > 100:
        return fail("合集名称需 1-100 个字符")
    description = (data.get("description") or "").strip()[:500]
    existing = db.query(
        "SELECT id, name, audit_status FROM collections WHERE name = %s", (name,), one=True
    )
    if existing:
        if existing["audit_status"] == 1:
            return ok(_serialize(_fetch_row(existing["id"]), g.user["id"], can_audit(g.user)))
        return fail(f"合集「{name}」已存在，正在审核或已被驳回，请勿重复提交")

    if is_super_admin(g.user):
        publish = bool(data.get("isPublished"))
        audit_status = 1 if publish else 0
        cid = db.execute(
            "INSERT INTO collections (name, description, is_published, audit_status, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, description, 1 if publish else 0, audit_status, g.user["id"]),
        )["lastrowid"]
        add_log(cid, "auto_approve" if publish else "submit", None, audit_status,
                g.user["id"], g.user["username"])
    else:
        cid = db.execute(
            "INSERT INTO collections (name, description, is_published, audit_status, created_by) "
            "VALUES (%s, %s, 0, 0, %s)",
            (name, description, g.user["id"]),
        )["lastrowid"]
        add_log(cid, "submit", None, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(cid), g.user["id"], can_audit(g.user)))


@bp.put("/<int:collection_id>")
@require_login
@require_admin
def update_collection(collection_id):
    """修改合集（仅超管）：改名 / 改简介 / 发布 / 下架，字段可选。

    发布时若此前未通过，同步置为「已通过」（免审通过）。"""
    row = db.query(
        "SELECT id, name, description, is_published, audit_status FROM collections WHERE id = %s",
        (collection_id,), one=True,
    )
    if not row:
        return fail("合集不存在", 404)
    data = request.get_json(silent=True) or {}
    updates, args = [], []
    auto_approved = False
    name = (data.get("name") or "").strip()
    if name and name != row["name"]:
        if len(name) > 100:
            return fail("合集名称过长（最多 100 个字符）")
        dup = db.query(
            "SELECT id FROM collections WHERE name = %s AND id != %s", (name, collection_id), one=True
        )
        if dup:
            return fail(f"合集「{name}」已存在")
        updates.append("name = %s")
        args.append(name)
    if "description" in data:
        updates.append("description = %s")
        args.append((data.get("description") or "").strip()[:500])
    if "isPublished" in data:
        new_pub = 1 if data["isPublished"] else 0
        if new_pub != row["is_published"]:
            updates.append("is_published = %s")
            args.append(new_pub)
            if new_pub == 1 and row["audit_status"] != 1:
                updates.append("audit_status = %s")
                args.append(1)
                auto_approved = True
    if not updates:
        return fail("没有需要修改的内容")
    args.append(collection_id)
    db.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id = %s", args)
    if auto_approved:
        add_log(collection_id, "auto_approve", row["audit_status"], 1,
                g.user["id"], g.user["username"])
    if "isPublished" in data and any("is_published" in u for u in updates):
        record(g.user, "toggle_publish", "collection", collection_id, name or row["name"],
               "发布" if data["isPublished"] else "下架")
    return ok(_serialize(_fetch_row(collection_id), g.user["id"], True))


@bp.post("/<int:collection_id>/review")
@require_login
@require_auditor
def review_collection(collection_id):
    """审核合集：approve 通过 / reject 驳回（必填理由）"""
    row = db.query(
        "SELECT id, name, is_published, audit_status FROM collections WHERE id = %s",
        (collection_id,), one=True,
    )
    if not row:
        return fail("合集不存在", 404)
    action = (request.get_json(silent=True) or {}).get("action")
    if action not in ("approve", "reject"):
        return fail("审核动作无效")
    from_status = row["audit_status"]
    if action == "approve":
        if from_status == 1:
            return fail("该合集已通过，无需重复审核")
        db.execute(
            "UPDATE collections SET audit_status = 1, is_published = 1, audit_reason = '' WHERE id = %s",
            (collection_id,),
        )
        add_log(collection_id, "approve", from_status, 1, g.user["id"], g.user["username"])
        msg = "已通过审核，合集已发布"
    else:
        reason = ((request.get_json(silent=True) or {}).get("reason") or "").strip()
        if not reason:
            return fail("请填写驳回理由，创建者需要知道未通过的原因")
        db.execute(
            "UPDATE collections SET audit_status = 2, is_published = 0, audit_reason = %s WHERE id = %s",
            (reason, collection_id),
        )
        add_log(collection_id, "reject", from_status, 2, g.user["id"], g.user["username"], reason)
        msg = "已驳回，理由已通知合集创建者"
    return ok({"collection": _serialize(_fetch_row(collection_id), g.user["id"], True), "msg": msg})


@bp.post("/<int:collection_id>/resubmit")
@require_login
def resubmit_collection(collection_id):
    """重新提交被驳回的合集（创建者本人或超管）"""
    row = db.query(
        "SELECT id, name, audit_status, created_by FROM collections WHERE id = %s",
        (collection_id,), one=True,
    )
    if not row:
        return fail("合集不存在", 404)
    if not (is_super_admin(g.user) or row["created_by"] == g.user["id"]):
        return fail("仅创建者或超级管理员可重新提交", 403)
    if row["audit_status"] != 2:
        return fail("仅被驳回的合集可重新提交")
    db.execute(
        "UPDATE collections SET audit_status = 0, is_published = 0, audit_reason = '' WHERE id = %s",
        (collection_id,),
    )
    add_log(collection_id, "resubmit", 2, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(collection_id), g.user["id"], can_audit(g.user)))


@bp.delete("/<int:collection_id>")
@require_login
def delete_collection(collection_id):
    """删除合集：超管可删任意；创建者仅可删自己「待审核 / 已驳回」的合集。

    videos.collection_id 有外键 ON DELETE SET NULL，影片本身不受影响。"""
    row = db.query(
        "SELECT id, name, audit_status, created_by FROM collections WHERE id = %s",
        (collection_id,), one=True,
    )
    if not row:
        return fail("合集不存在", 404)
    if not (
        is_super_admin(g.user)
        or (row["created_by"] == g.user["id"] and row["audit_status"] != 1)
    ):
        return fail("仅超级管理员可删除已发布合集，或创建者可删除自己待审核 / 已驳回的合集", 403)
    db.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
    record(g.user, "delete_collection", "collection", collection_id, row["name"])
    return ok()


@bp.get("/<int:collection_id>/logs")
@require_login
def collection_logs(collection_id):
    """单条合集的审核留痕（创建者或审核角色可查）"""
    row = db.query("SELECT id, created_by FROM collections WHERE id = %s", (collection_id,), one=True)
    if not row:
        return fail("合集不存在", 404)
    if not (can_audit(g.user) or row["created_by"] == g.user["id"]):
        return fail("无权查看该合集的审核记录", 403)
    rows = db.query(
        "SELECT * FROM collection_audit_logs WHERE collection_id = %s ORDER BY id ASC",
        (collection_id,),
    )
    return ok([serialize_log(r) for r in rows])
