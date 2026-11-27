"""岗位管理：CRUD。岗位与用户多对多，删除前校验引用。"""
from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from .support import get_conn
from .support import  page_args

bp = Blueprint("system_posts", __name__)


def _post(row):
    return {
        "id": row["id"], "code": row["post_code"], "name": row["post_name"],
        "sortNo": row["sort_no"], "enabled": bool(row["enabled_flag"]),
        "remark": row.get("remark") or "", "userCount": row.get("user_count", 0),
    }


@bp.get("")
@require_login
@require_perm("system:post:list")
def list_posts():
    page, size = page_args()
    keyword = (request.args.get("keyword") or "").strip()
    where = "WHERE (p.post_code LIKE %s OR p.post_name LIKE %s)" if keyword else ""
    args = [f"%{keyword}%", f"%{keyword}%"] if keyword else []
    total = db.query(f"SELECT COUNT(*) c FROM sys_post p {where}", args, one=True)["c"]
    rows = db.query(
        "SELECT p.*, (SELECT COUNT(*) FROM sys_user_post up WHERE up.post_id = p.id) user_count "
        f"FROM sys_post p {where} ORDER BY p.sort_no, p.id LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_post(row) for row in rows], "total": total,
               "page": page, "pageSize": size})


@bp.post("")
@require_login
@require_perm("system:post:create")
def create_post():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return fail("岗位编码与名称不能为空")
    if db.query("SELECT id FROM sys_post WHERE post_code = %s", (code,), one=True):
        return fail("岗位编码已存在")
    result = db.execute(
        "INSERT INTO sys_post (post_code, post_name, sort_no, enabled_flag, remark) "
        "VALUES (%s, %s, %s, %s, %s)",
        (code, name, int(data.get("sortNo") or 0), 1 if data.get("enabled", True) else 0,
         str(data.get("remark") or "")),
    )
    return ok({"id": result["lastrowid"]})


@bp.put("/<int:post_id>")
@require_login
@require_perm("system:post:update")
def update_post(post_id):
    data = request.get_json(silent=True) or {}
    existing = db.query("SELECT * FROM sys_post WHERE id = %s", (post_id,), one=True)
    if not existing:
        return fail("岗位不存在", 404)
    code = str(data.get("code") or existing["post_code"]).strip()
    if db.query("SELECT id FROM sys_post WHERE post_code = %s AND id <> %s", (code, post_id), one=True):
        return fail("岗位编码已存在")
    db.execute(
        "UPDATE sys_post SET post_code = %s, post_name = %s, sort_no = %s, enabled_flag = %s, "
        "remark = %s WHERE id = %s",
        (code, str(data.get("name") or existing["post_name"]).strip(),
         int(data.get("sortNo") or existing["sort_no"]),
         1 if data.get("enabled", True) else 0,
         str(data.get("remark") or existing["remark"]), post_id),
    )
    return ok({"id": post_id})


@bp.delete("/<int:post_id>")
@require_login
@require_perm("system:post:delete")
def delete_post(post_id):
    if db.query("SELECT post_id FROM sys_user_post WHERE post_id = %s LIMIT 1", (post_id,), one=True):
        return fail("岗位下仍有用户，请先调整用户岗位")
    db.execute("DELETE FROM sys_post WHERE id = %s", (post_id,))
    return ok({"id": post_id})
