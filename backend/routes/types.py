"""影视类型接口：/api/types

类型审核流程（复用视频审核权限 can_audit：admin / manager / reviewer）：
- 普通用户可提交新类型，进入「待审核」，默认不发布；
- 审核角色对待审类型通过 / 驳回（驳回必填理由）；
- 被驳回的类型，创建者或管理员可「重新提交」再次进入待审核；
- 所有审核动作写入 type_audit_logs（只追加、可追溯）。

可见性：普通用户只看「已发布」的类型 + 自己提交的类型（含状态）；审核角色看全部。
"""
from flask import Blueprint, g, request

import db
from auth import (
    can_audit,
    is_super_admin,
    require_admin,
    require_auditor,
    require_login,
)
from responses import ok, fail
from type_audit_logs import STATUS_TEXT, add_log, serialize_log

bp = Blueprint("types", __name__, url_prefix="/api/types")


def _serialize(row, viewer_id, admin_view):
    """序列化类型。

    - 所有用户都能看到 id / name / auditStatus / isPublished / isMine；
    - 审核角色额外看到驳回理由与创建者姓名；
    - 普通用户仅对自己提交的类型看到创建者与驳回理由（前端据此判断
      「重新提交 / 审核记录 / 删除」按钮是否可用）。"""
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
    """新建类型。

    - 管理员：可直接发布（免审通过）或留作未发布；
    - 普通用户：进入待审核（audit_status=0，未发布），等待管理员审核。"""
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
        # 同名且已通过：直接返回（幂等）
        if existing["audit_status"] == 1:
            return ok(_serialize(_fetch_row(existing["id"]), g.user["id"], can_audit(g.user)))
        # 同名但待审 / 已驳回：禁止重复提交，避免名称被占用无法重新提交
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


@bp.put("/<int:type_id>")
@require_login
@require_admin
def update_type(type_id):
    """修改类型（仅管理员）：改名 / 发布 / 下架，字段可选。

    发布（isPublished=true）时若此前未通过，则同步置为「已通过」（免审通过）。"""
    row = db.query(
        "SELECT id, name, is_published, audit_status FROM types WHERE id = %s", (type_id,), one=True
    )
    if not row:
        return fail("类型不存在", 404)
    data = request.get_json(silent=True) or {}
    updates, args = [], []
    auto_approved = False  # 本次发布是否顺带免审通过
    name = (data.get("name") or "").strip()
    if name and name != row["name"]:
        if len(name) > 50:
            return fail("类型名过长（最多 50 个字符）")
        dup = db.query("SELECT id FROM types WHERE name = %s AND id != %s", (name, type_id), one=True)
        if dup:
            return fail(f"类型「{name}」已存在")
        updates.append("name = %s")
        args.append(name)
    if "isPublished" in data:
        new_pub = 1 if data["isPublished"] else 0
        if new_pub != row["is_published"]:
            updates.append("is_published = %s")
            args.append(new_pub)
            # 发布且此前未通过 → 同步置为已通过（免审通过），保证 is_published=1 ⇒ audit_status=1
            if new_pub == 1 and row["audit_status"] != 1:
                updates.append("audit_status = %s")
                args.append(1)
                auto_approved = True
    if not updates:
        return fail("没有需要修改的内容")
    args.append(type_id)
    db.execute(f"UPDATE types SET {', '.join(updates)} WHERE id = %s", args)
    # 留痕放在 UPDATE 成功之后，避免写入与实际状态不一致的孤立记录
    if auto_approved:
        add_log(type_id, "auto_approve", row["audit_status"], 1, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(type_id), g.user["id"], True))


@bp.post("/<int:type_id>/review")
@require_login
@require_auditor
def review_type(type_id):
    """审核类型（复用视频审核权限）：approve 通过 / reject 驳回（必填理由）"""
    row = db.query(
        "SELECT id, name, is_published, audit_status, created_by FROM types WHERE id = %s", (type_id,), one=True
    )
    if not row:
        return fail("类型不存在", 404)
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("approve", "reject"):
        return fail("审核动作无效")
    from_status = row["audit_status"]
    if action == "approve":
        if from_status == 1:
            return fail("该类型已通过，无需重复审核")
        db.execute(
            "UPDATE types SET audit_status = 1, is_published = 1, audit_reason = '' WHERE id = %s",
            (type_id,),
        )
        add_log(type_id, "approve", from_status, 1, g.user["id"], g.user["username"])
        msg = "已通过审核，类型已发布"
    else:
        reason = (data.get("reason") or "").strip()
        if not reason:
            return fail("请填写驳回理由，创建者需要知道未通过的原因")
        db.execute(
            "UPDATE types SET audit_status = 2, is_published = 0, audit_reason = %s WHERE id = %s",
            (reason, type_id),
        )
        add_log(type_id, "reject", from_status, 2, g.user["id"], g.user["username"], reason)
        msg = "已驳回，理由已通知类型创建者"
    return ok({"type": _serialize(_fetch_row(type_id), g.user["id"], True), "msg": msg})


@bp.post("/<int:type_id>/resubmit")
@require_login
def resubmit_type(type_id):
    """重新提交被驳回的类型（创建者本人或管理员）"""
    row = db.query(
        "SELECT id, name, is_published, audit_status, created_by FROM types WHERE id = %s", (type_id,), one=True
    )
    if not row:
        return fail("类型不存在", 404)
    if not (is_super_admin(g.user) or row["created_by"] == g.user["id"]):
        return fail("仅创建者或管理员可重新提交", 403)
    if row["audit_status"] != 2:
        return fail("仅被驳回的类型可重新提交")
    db.execute(
        "UPDATE types SET audit_status = 0, is_published = 0, audit_reason = '' WHERE id = %s",
        (type_id,),
    )
    add_log(type_id, "resubmit", 2, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch_row(type_id), g.user["id"], can_audit(g.user)))


@bp.delete("/<int:type_id>")
@require_login
def delete_type(type_id):
    """删除类型。

    - 管理员：可删除任意类型；
    - 创建者：仅可删除自己「待审核 / 已驳回」的类型（已发布的类型需管理员处理）。"""
    row = db.query(
        "SELECT id, name, audit_status, created_by FROM types WHERE id = %s", (type_id,), one=True
    )
    if not row:
        return fail("类型不存在", 404)
    if not (
        is_super_admin(g.user)
        or (row["created_by"] == g.user["id"] and row["audit_status"] != 1)
    ):
        return fail("仅管理员可删除已发布类型，或创建者可删除自己待审核 / 已驳回的类型", 403)
    db.execute("DELETE FROM types WHERE id = %s", (type_id,))  # 视频的 type_id 由外键置空
    return ok()


@bp.get("/<int:type_id>/logs")
@require_login
def type_logs(type_id):
    """单条类型的审核留痕（创建者或审核角色可查），用于展示完整审核轨迹"""
    row = db.query("SELECT id, created_by FROM types WHERE id = %s", (type_id,), one=True)
    if not row:
        return fail("类型不存在", 404)
    if not (can_audit(g.user) or row["created_by"] == g.user["id"]):
        return fail("无权查看该类型的审核记录", 403)
    rows = db.query(
        "SELECT * FROM type_audit_logs WHERE type_id = %s ORDER BY id ASC", (type_id,)
    )
    return ok([serialize_log(r) for r in rows])
