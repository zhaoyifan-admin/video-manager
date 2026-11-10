"""影视类型接口：/api/types"""
from flask import Blueprint, request

from auth import require_login

import db
from responses import ok, fail

bp = Blueprint("types", __name__, url_prefix="/api/types")


@bp.get("")
@require_login
def list_types():
    rows = db.query("SELECT id, name FROM types ORDER BY id DESC")
    return ok(rows)


@bp.post("")
@require_login
def create_type():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail("类型名不能为空")
    if len(name) > 50:
        return fail("类型名过长（最多 50 个字符）")
    existing = db.query("SELECT id, name FROM types WHERE name = %s", (name,), one=True)
    if existing:
        return ok(existing)  # 幂等：已存在直接返回
    type_id = db.execute("INSERT INTO types (name) VALUES (%s)", (name,))["lastrowid"]
    return ok({"id": type_id, "name": name})


@bp.delete("/<int:type_id>")
@require_login
def delete_type(type_id):
    row = db.query("SELECT id FROM types WHERE id = %s", (type_id,), one=True)
    if not row:
        return fail("类型不存在", 404)
    db.execute("DELETE FROM types WHERE id = %s", (type_id,))  # 视频的 type_id 由外键置空
    return ok()
