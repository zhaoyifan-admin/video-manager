"""标签接口：/api/tags"""
from flask import Blueprint, request

from auth import require_login

import db
from responses import ok, fail

bp = Blueprint("tags", __name__, url_prefix="/api/tags")


@bp.get("")
@require_login
def list_tags():
    rows = db.query("SELECT id, name FROM tags ORDER BY name ASC")
    return ok(rows)


@bp.post("")
@require_login
def create_tag():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail("标签名不能为空")
    if len(name) > 50:
        return fail("标签名过长（最多 50 个字符）")
    existing = db.query("SELECT id, name FROM tags WHERE name = %s", (name,), one=True)
    if existing:
        return ok(existing)  # 幂等：已存在直接返回
    tag_id = db.execute("INSERT INTO tags (name) VALUES (%s)", (name,))["lastrowid"]
    return ok({"id": tag_id, "name": name})


@bp.delete("/<int:tag_id>")
@require_login
def delete_tag(tag_id):
    row = db.query("SELECT id FROM tags WHERE id = %s", (tag_id,), one=True)
    if not row:
        return fail("标签不存在", 404)
    db.execute("DELETE FROM tags WHERE id = %s", (tag_id,))  # 关联表由外键级联清理
    return ok()
