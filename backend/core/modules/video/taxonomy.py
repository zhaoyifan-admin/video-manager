"""分类管理（标签 / 影视类型 / 合集）：从视频子系统搬移的审核工作台接口。

三张表结构同构（name / is_published / audit_status / created_by / audit_reason），
用一份参数化处理器覆盖 CRUD + 审核 + 重新提交 + 留痕，避免三份重复实现。
权限改用 RBAC 权限码：video:taxonomy:list / :manage / :review。
"""
from flask import Blueprint, g, request

import db
from admin_audit_logs import record
from auth import require_login
from responses import fail, ok
from core.security import require_perm

bp = Blueprint("video_taxonomy", __name__)

# 资源配置：表名、展示名、留痕辅助模块、长度上限、是否有简介
RESOURCES = {
    "tag": {
        "table": "tags", "label": "标签", "max_len": 50, "desc": False,
        "log_mod": "tag_audit_logs", "log_fk": "tag_id",
        "action": "tag", "perm_ns": "tag",
    },
    "type": {
        "table": "types", "label": "影视类型", "max_len": 50, "desc": False,
        "log_mod": "type_audit_logs", "log_fk": "type_id",
        "action": "type", "perm_ns": "type",
    },
    "collection": {
        "table": "collections", "label": "合集", "max_len": 100, "desc": True,
        "log_mod": "collection_audit_logs", "log_fk": "collection_id",
        "action": "collection", "perm_ns": "collection",
    },
}


def _conf(resource):
    conf = RESOURCES.get(resource)
    if not conf:
        return None, fail("分类资源无效")
    return conf, None


def _logs(conf):
    """惰性导入留痕辅助模块，避免模块名冲突。"""
    import importlib
    return importlib.import_module(conf["log_mod"])


def _serialize(row, viewer_id, conf, admin_view):
    data = {
        "id": row["id"], "name": row["name"],
        "auditStatus": row["audit_status"],
        "isMine": row["created_by"] == viewer_id,
        "isPublished": bool(row["is_published"]),
    }
    if conf["desc"]:
        data["description"] = row.get("description") or ""
        data["videoCount"] = row.get("video_count") or 0
    if admin_view:
        data["auditReason"] = row["audit_reason"]
        data["createdBy"] = row["created_by"]
        data["createdByName"] = row.get("created_by_name") or ""
    elif data["isMine"]:
        data["createdBy"] = viewer_id
        data["auditReason"] = row["audit_reason"]
    return data


def _fetch(conf, row_id):
    extra = ""
    if conf["desc"]:
        extra = ", (SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
    alias = "c" if conf["desc"] else "t"
    return db.query(
        f"SELECT {alias}.*, u.username AS created_by_name {extra} "
        f"FROM {conf['table']} {alias} LEFT JOIN users u ON u.id = {alias}.created_by "
        f"WHERE {alias}.id = %s", (row_id,), one=True,
    )


def _is_super(user):
    """超管沿用 users.role 快照，免审/任意删除语义不变。"""
    return bool(user) and user.get("role") == "admin"


# 管理工作台列表：RBAC 可读者看全部
@bp.get("/taxonomy/<resource>")
@require_login
@require_perm("video:taxonomy:list")
def list_taxonomy(resource):
    conf, error = _conf(resource)
    if error:
        return error
    alias = "c" if conf["desc"] else "t"
    extra = ""
    if conf["desc"]:
        extra = ", (SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
    rows = db.query(
        f"SELECT {alias}.*, u.username AS created_by_name {extra} "
        f"FROM {conf['table']} {alias} LEFT JOIN users u ON u.id = {alias}.created_by "
        f"ORDER BY {alias}.name ASC"
    )
    return ok({"items": [_serialize(r, g.user["id"], conf, True) for r in rows]})


@bp.post("/taxonomy/<resource>")
@require_login
@require_perm("video:taxonomy:manage")
def create_taxonomy(resource):
    conf, error = _conf(resource)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > conf["max_len"]:
        return fail(f"{conf['label']}名称需 1-{conf['max_len']} 个字符")
    exists = db.query(
        f"SELECT id, audit_status FROM {conf['table']} WHERE name = %s", (name,), one=True
    )
    if exists:
        if exists["audit_status"] == 1:
            return ok(_serialize(_fetch(conf, exists["id"]), g.user["id"], conf, True))
        return fail(f"{conf['label']}「{name}」已存在，正在审核或已被驳回，请勿重复提交")

    publish = bool(data.get("isPublished")) and _is_super(g.user)
    desc = (data.get("description") or "").strip()[:500] if conf["desc"] else ""
    if conf["desc"]:
        new_id = db.execute(
            f"INSERT INTO {conf['table']} (name, description, is_published, audit_status, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, desc, 1 if publish else 0, 1 if publish else 0, g.user["id"]),
        )["lastrowid"]
    else:
        new_id = db.execute(
            f"INSERT INTO {conf['table']} (name, is_published, audit_status, created_by) "
            "VALUES (%s, %s, %s, %s)",
            (name, 1 if publish else 0, 1 if publish else 0, g.user["id"]),
        )["lastrowid"]
    _logs(conf).add_log(
        new_id, "auto_approve" if publish else "submit", None, 1 if publish else 0,
        g.user["id"], g.user["username"],
    )
    return ok(_serialize(_fetch(conf, new_id), g.user["id"], conf, True))


@bp.put("/taxonomy/<resource>/<int:row_id>")
@require_login
@require_perm("video:taxonomy:manage")
def update_taxonomy(resource, row_id):
    conf, error = _conf(resource)
    if error:
        return error
    row = db.query(f"SELECT * FROM {conf['table']} WHERE id = %s", (row_id,), one=True)
    if not row:
        return fail(f"{conf['label']}不存在", 404)
    data = request.get_json(silent=True) or {}
    updates, args, auto_approved = [], [], False
    name = (data.get("name") or "").strip()
    if name and name != row["name"]:
        if len(name) > conf["max_len"]:
            return fail(f"{conf['label']}名称过长（最多 {conf['max_len']} 个字符）")
        if db.query(f"SELECT id FROM {conf['table']} WHERE name = %s AND id != %s",
                    (name, row_id), one=True):
            return fail(f"{conf['label']}「{name}」已存在")
        updates.append("name = %s")
        args.append(name)
    if conf["desc"] and "description" in data:
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
    args.append(row_id)
    db.execute(f"UPDATE {conf['table']} SET {', '.join(updates)} WHERE id = %s", args)
    if auto_approved:
        _logs(conf).add_log(row_id, "auto_approve", row["audit_status"], 1,
                            g.user["id"], g.user["username"])
    if any("is_published" in u for u in updates):
        record(g.user, "toggle_publish", conf["action"], row_id, name or row["name"],
               "发布" if data.get("isPublished") else "下架")
    elif any("name" in u for u in updates):
        record(g.user, "rename", conf["action"], row_id, name, f"{row['name']} → {name}")
    return ok(_serialize(_fetch(conf, row_id), g.user["id"], conf, True))


@bp.post("/taxonomy/<resource>/<int:row_id>/review")
@require_login
@require_perm("video:taxonomy:review")
def review_taxonomy(resource, row_id):
    conf, error = _conf(resource)
    if error:
        return error
    row = db.query(f"SELECT * FROM {conf['table']} WHERE id = %s", (row_id,), one=True)
    if not row:
        return fail(f"{conf['label']}不存在", 404)
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("approve", "reject"):
        return fail("审核动作无效")
    from_status = row["audit_status"]
    if action == "approve":
        if from_status == 1:
            return fail("该条目已通过，无需重复审核")
        db.execute(
            f"UPDATE {conf['table']} SET audit_status = 1, is_published = 1, audit_reason = '' WHERE id = %s",
            (row_id,),
        )
        _logs(conf).add_log(row_id, "approve", from_status, 1, g.user["id"], g.user["username"])
        msg = "已通过审核并发布"
    else:
        reason = (data.get("reason") or "").strip()
        if not reason:
            return fail("请填写驳回理由，创建者需要知道未通过的原因")
        db.execute(
            f"UPDATE {conf['table']} SET audit_status = 2, is_published = 0, audit_reason = %s WHERE id = %s",
            (reason, row_id),
        )
        _logs(conf).add_log(row_id, "reject", from_status, 2,
                            g.user["id"], g.user["username"], reason)
        msg = "已驳回，理由已通知创建者"
    return ok({"item": _serialize(_fetch(conf, row_id), g.user["id"], conf, True), "msg": msg})


@bp.post("/taxonomy/<resource>/<int:row_id>/resubmit")
@require_login
@require_perm("video:taxonomy:manage")
def resubmit_taxonomy(resource, row_id):
    conf, error = _conf(resource)
    if error:
        return error
    row = db.query(f"SELECT * FROM {conf['table']} WHERE id = %s", (row_id,), one=True)
    if not row:
        return fail(f"{conf['label']}不存在", 404)
    if not (_is_super(g.user) or row["created_by"] == g.user["id"]):
        return fail("仅创建者或管理员可重新提交", 403)
    if row["audit_status"] != 2:
        return fail("仅被驳回的条目可重新提交")
    db.execute(
        f"UPDATE {conf['table']} SET audit_status = 0, is_published = 0, audit_reason = '' WHERE id = %s",
        (row_id,),
    )
    _logs(conf).add_log(row_id, "resubmit", 2, 0, g.user["id"], g.user["username"])
    return ok(_serialize(_fetch(conf, row_id), g.user["id"], conf, True))


@bp.delete("/taxonomy/<resource>/<int:row_id>")
@require_login
@require_perm("video:taxonomy:manage")
def delete_taxonomy(resource, row_id):
    conf, error = _conf(resource)
    if error:
        return error
    row = db.query(f"SELECT id, name, audit_status, created_by FROM {conf['table']} WHERE id = %s",
                   (row_id,), one=True)
    if not row:
        return fail(f"{conf['label']}不存在", 404)
    if not (_is_super(g.user) or (row["created_by"] == g.user["id"] and row["audit_status"] != 1)):
        return fail("仅管理员可删除已发布条目，或创建者可删除自己待审核/已驳回的条目", 403)
    db.execute(f"DELETE FROM {conf['table']} WHERE id = %s", (row_id,))
    record(g.user, f"delete_{conf['action']}", conf["action"], row_id, row["name"])
    return ok()


@bp.get("/taxonomy/<resource>/<int:row_id>/logs")
@require_login
@require_perm("video:taxonomy:list")
def taxonomy_logs(resource, row_id):
    conf, error = _conf(resource)
    if error:
        return error
    row = db.query(f"SELECT id, created_by FROM {conf['table']} WHERE id = %s", (row_id,), one=True)
    if not row:
        return fail(f"{conf['label']}不存在", 404)
    rows = db.query(
        f"SELECT * FROM {conf['log_mod']} WHERE {conf['log_fk']} = %s ORDER BY id ASC", (row_id,)
    )
    return ok({"items": [_logs(conf).serialize_log(r) for r in rows]})
