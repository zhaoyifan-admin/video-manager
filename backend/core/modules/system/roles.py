"""角色管理：CRUD + 菜单/按钮授权 + 用户分配。

写授权时统一递增 permission_version，确保多角色/按钮权限变更即时生效。
内置角色（built_in=1）不可删除，避免把视频子系统依赖的四个角色删空。
"""
from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from .support import get_conn
from .support import  bump_permission_version, page_args, VALID_ROLES

bp = Blueprint("system_roles", __name__)


def _role(row):
    return {
        "id": row["id"],
        "roleCode": row["role_code"],
        "roleName": row["role_name"],
        "dataScope": row["data_scope"],
        "sortNo": row["sort_no"],
        "enabled": bool(row["status"]),
        "builtIn": bool(row["built_in"]),
        "remark": row.get("remark") or "",
        "userCount": row.get("user_count", 0),
    }


@bp.get("")
@require_login
@require_perm("system:role:list")
def list_roles():
    page, size = page_args()
    keyword = (request.args.get("keyword") or "").strip()
    where = "WHERE (r.role_code LIKE %s OR r.role_name LIKE %s)" if keyword else ""
    args = [f"%{keyword}%", f"%{keyword}%"] if keyword else []
    total = db.query(f"SELECT COUNT(*) c FROM sys_role r {where}", args, one=True)["c"]
    rows = db.query(
        "SELECT r.*, (SELECT COUNT(*) FROM sys_user_role ur WHERE ur.role_id = r.id) user_count "
        f"FROM sys_role r {where} ORDER BY r.sort_no, r.id LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_role(row) for row in rows], "total": total,
               "page": page, "pageSize": size, "validRoles": list(VALID_ROLES)})


@bp.post("")
@require_login
@require_perm("system:role:create")
def create_role():
    data = request.get_json(silent=True) or {}
    code = str(data.get("roleCode") or "").strip()
    name = str(data.get("roleName") or "").strip()
    scope = str(data.get("dataScope") or "SELF")
    if not code or not name:
        return fail("角色编码与名称不能为空")
    if scope not in ("ALL", "DEPT", "DEPT_TREE", "SELF", "CUSTOM"):
        return fail("数据范围无效")
    if db.query("SELECT id FROM sys_role WHERE role_code = %s", (code,), one=True):
        return fail("角色编码已存在")
    result = db.execute(
        "INSERT INTO sys_role (role_code, role_name, data_scope, sort_no, status, remark) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (code, name, scope, int(data.get("sortNo") or 0), 1 if data.get("enabled", True) else 0,
         str(data.get("remark") or "")),
    )
    menu_ids = data.get("menuIds") or []
    if menu_ids:
        _replace_role_menus(result["lastrowid"], menu_ids)
    bump_permission_version()
    return ok({"id": result["lastrowid"]})


@bp.put("/<int:role_id>")
@require_login
@require_perm("system:role:update")
def update_role(role_id):
    data = request.get_json(silent=True) or {}
    row = db.query("SELECT * FROM sys_role WHERE id = %s", (role_id,), one=True)
    if not row:
        return fail("角色不存在", 404)
    if row["built_in"] and data.get("enabled") is False:
        return fail("内置角色不可停用")
    name = str(data.get("roleName") or row["role_name"]).strip()
    scope = str(data.get("dataScope") or row["data_scope"])
    if scope not in ("ALL", "DEPT", "DEPT_TREE", "SELF", "CUSTOM"):
        return fail("数据范围无效")
    db.execute(
        "UPDATE sys_role SET role_name = %s, data_scope = %s, sort_no = %s, status = %s, remark = %s "
        "WHERE id = %s",
        (name, scope, int(data.get("sortNo") or row["sort_no"]),
         1 if data.get("enabled", True) else 0, str(data.get("remark") or ""), role_id),
    )
    if "menuIds" in data:
        _replace_role_menus(role_id, data["menuIds"])
    bump_permission_version()
    return ok({"id": role_id})


@bp.delete("/<int:role_id>")
@require_login
@require_perm("system:role:delete")
def delete_role(role_id):
    row = db.query("SELECT built_in FROM sys_role WHERE id = %s", (role_id,), one=True)
    if not row:
        return fail("角色不存在", 404)
    if row["built_in"]:
        return fail("内置角色不可删除")
    db.execute("DELETE FROM sys_role WHERE id = %s", (role_id,))
    bump_permission_version()
    return ok({"id": role_id})


def _replace_role_menus(role_id, menu_ids):
    """重建角色-菜单授权；menu_ids 为空表示清空。"""
    ids = [int(value) for value in menu_ids if str(value).isdigit()]
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sys_role_menu WHERE role_id = %s", (role_id,))
        if ids:
            marks = ",".join(["%s"] * len(ids))
            valid = [row["id"] for row in conn.execute(
                f"SELECT id FROM sys_menu WHERE id IN ({marks})", ids
            ).fetchall()]
            for menu_id in valid:
                conn.execute(
                    "INSERT INTO sys_role_menu (role_id, menu_id) VALUES (%s, %s)",
                    (role_id, menu_id),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@bp.get("/<int:role_id>/menus")
@require_login
@require_perm("system:role:list")
def role_menus(role_id):
    rows = db.query(
        "SELECT m.id, m.menu_code, m.menu_type, m.title, m.parent_id, m.permission_code, "
        "CASE WHEN rm.role_id IS NULL THEN 0 ELSE 1 END AS granted "
        "FROM sys_menu m LEFT JOIN sys_role_menu rm "
        "ON rm.menu_id = m.id AND rm.role_id = %s "
        "ORDER BY m.sort_no, m.id", (role_id,),
    )
    return ok({"items": [{
        "id": row["id"], "code": row["menu_code"], "type": row["menu_type"],
        "title": row["title"], "parentId": row["parent_id"],
        "permission": row["permission_code"], "granted": bool(row["granted"]),
    } for row in rows]})


@bp.put("/<int:role_id>/menus")
@require_login
@require_perm("system:role:assign")
def assign_menus(role_id):
    if not db.query("SELECT id FROM sys_role WHERE id = %s", (role_id,), one=True):
        return fail("角色不存在", 404)
    _replace_role_menus(role_id, (request.get_json(silent=True) or {}).get("menuIds") or [])
    bump_permission_version()
    return ok({"roleId": role_id})


@bp.get("/<int:role_id>/depts")
@require_login
@require_perm("system:role:list")
def role_depts(role_id):
    rows = db.query(
        "SELECT d.id, d.dept_code, d.dept_name, d.parent_id, "
        "CASE WHEN rd.role_id IS NULL THEN 0 ELSE 1 END AS granted "
        "FROM sys_dept d LEFT JOIN sys_role_dept rd "
        "ON rd.dept_id = d.id AND rd.role_id = %s ORDER BY d.sort_no, d.id", (role_id,),
    )
    return ok({"items": [{
        "id": row["id"], "code": row["dept_code"], "name": row["dept_name"],
        "parentId": row["parent_id"], "granted": bool(row["granted"]),
    } for row in rows]})


@bp.put("/<int:role_id>/depts")
@require_login
@require_perm("system:role:assign")
def assign_depts(role_id):
    if not db.query("SELECT id FROM sys_role WHERE id = %s", (role_id,), one=True):
        return fail("角色不存在", 404)
    ids = [int(value) for value in ((request.get_json(silent=True) or {}).get("deptIds") or [])
           if str(value).isdigit()]
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sys_role_dept WHERE role_id = %s", (role_id,))
        if ids:
            marks = ",".join(["%s"] * len(ids))
            valid = [row["id"] for row in conn.execute(
                f"SELECT id FROM sys_dept WHERE id IN ({marks})", ids
            ).fetchall()]
            for dept_id in valid:
                conn.execute(
                    "INSERT INTO sys_role_dept (role_id, dept_id) VALUES (%s, %s)",
                    (role_id, dept_id),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"roleId": role_id})
