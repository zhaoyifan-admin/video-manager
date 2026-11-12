"""标签接口：/api/tags

标签由超级管理员统一增删改并发布；普通用户（含审核员）只能查询已发布的标签用于选择。
"""
from flask import Blueprint, g, request

from auth import is_super_admin, require_login

import db
from responses import ok, fail

bp = Blueprint("tags", __name__, url_prefix="/api/tags")


def _serialize(row, admin_view):
    """普通用户只需要 id/name；管理员额外拿到发布状态"""
    data = {"id": row["id"], "name": row["name"]}
    if admin_view:
        data["isPublished"] = bool(row["is_published"])
    return data


@bp.get("")
@require_login
def list_tags():
    """标签列表：管理员看全部（含未发布），其他用户只看已发布的"""
    admin_view = is_super_admin(g.user)
    sql = "SELECT id, name, is_published FROM tags"
    if not admin_view:
        sql += " WHERE is_published = 1"
    sql += " ORDER BY name ASC"
    rows = db.query(sql)
    return ok([_serialize(r, admin_view) for r in rows])


@bp.post("")
@require_login
def create_tag():
    """新建标签（仅管理员），默认未发布，可在标签管理里发布"""
    if not is_super_admin(g.user):
        return fail("仅超级管理员可管理标签", 403)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail("标签名不能为空")
    if len(name) > 50:
        return fail("标签名过长（最多 50 个字符）")
    existing = db.query("SELECT id, name, is_published FROM tags WHERE name = %s", (name,), one=True)
    if existing:
        return ok(_serialize(existing, True))  # 幂等：已存在直接返回
    tag_id = db.execute(
        "INSERT INTO tags (name, is_published) VALUES (%s, %s)",
        (name, 1 if data.get("isPublished") else 0),
    )["lastrowid"]
    return ok({"id": tag_id, "name": name, "isPublished": bool(data.get("isPublished"))})


@bp.put("/<int:tag_id>")
@require_login
def update_tag(tag_id):
    """修改标签（仅管理员）：改名 / 发布 / 下架，字段可选"""
    if not is_super_admin(g.user):
        return fail("仅超级管理员可管理标签", 403)
    row = db.query("SELECT id, name FROM tags WHERE id = %s", (tag_id,), one=True)
    if not row:
        return fail("标签不存在", 404)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    updates, args = [], []
    if name:
        if len(name) > 50:
            return fail("标签名过长（最多 50 个字符）")
        dup = db.query("SELECT id FROM tags WHERE name = %s AND id != %s", (name, tag_id), one=True)
        if dup:
            return fail(f"标签「{name}」已存在")
        updates.append("name = %s")
        args.append(name)
    if "isPublished" in data:
        updates.append("is_published = %s")
        args.append(1 if data["isPublished"] else 0)
    if not updates:
        return fail("没有需要修改的内容")
    args.append(tag_id)
    db.execute(f"UPDATE tags SET {', '.join(updates)} WHERE id = %s", args)
    updated = db.query("SELECT id, name, is_published FROM tags WHERE id = %s", (tag_id,), one=True)
    return ok(_serialize(updated, True))


@bp.delete("/<int:tag_id>")
@require_login
def delete_tag(tag_id):
    """删除标签（仅管理员）；视频关联由外键级联清理"""
    if not is_super_admin(g.user):
        return fail("仅超级管理员可管理标签", 403)
    row = db.query("SELECT id FROM tags WHERE id = %s", (tag_id,), one=True)
    if not row:
        return fail("标签不存在", 404)
    db.execute("DELETE FROM tags WHERE id = %s", (tag_id,))  # 关联表由外键级联清理
    return ok()
