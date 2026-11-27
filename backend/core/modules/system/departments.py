"""部门管理：树形 CRUD + ancestor_path 维护。

ancestor_path 形如 /1/3/，用 LIKE '/1/3/%' 可一次性查出所有后代部门（P3 数据范围消费）。
"""
from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from .support import get_conn
from .support import  page_args

bp = Blueprint("system_departments", __name__)


def _dept(row):
    return {
        "id": row["id"], "code": row["dept_code"], "parentId": row["parent_id"] or 0,
        "ancestorPath": row["ancestor_path"], "name": row["dept_name"],
        "leaderUserId": row["leader_user_id"] or 0, "sortNo": row["sort_no"],
        "enabled": bool(row["enabled_flag"]), "userCount": row.get("user_count", 0),
        "children": [],
    }


def _tree(rows):
    nodes = {row["id"]: _dept(row) for row in rows}
    roots = []
    for row in rows:
        node = nodes[row["id"]]
        parent = nodes.get(row["parent_id"])
        if parent and parent["id"] != node["id"]:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def _path(conn, parent_id):
    """由父部门推导新部门的 ancestor_path。"""
    if not parent_id:
        return "/"
    parent = conn.execute("SELECT ancestor_path FROM sys_dept WHERE id = %s", (parent_id,)).fetchone()
    if not parent:
        raise ValueError("父部门不存在")
    return f"{parent['ancestor_path']}{parent_id}/"


@bp.get("")
@require_login
@require_perm("system:dept:list")
def list_departments():
    rows = db.query(
        "SELECT d.*, (SELECT COUNT(*) FROM sys_user_profile p WHERE p.dept_id = d.id) user_count "
        "FROM sys_dept d ORDER BY d.sort_no, d.id"
    )
    return ok({"items": _tree(rows)})


@bp.post("")
@require_login
@require_perm("system:dept:create")
def create_department():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return fail("部门编码与名称不能为空")
    if db.query("SELECT id FROM sys_dept WHERE dept_code = %s", (code,), one=True):
        return fail("部门编码已存在")
    conn = get_conn()
    try:
        path = _path(conn, int(data.get("parentId") or 0))
        result = conn.execute(
            "INSERT INTO sys_dept (dept_code, parent_id, ancestor_path, dept_name, leader_user_id, "
            "sort_no, enabled_flag) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (code, int(data.get("parentId") or 0), path, name,
             int(data.get("leaderUserId") or 0), int(data.get("sortNo") or 0),
             1 if data.get("enabled", True) else 0),
        )
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": result.lastrowid})


def _descendant_ids(conn, dept_id):
    """含自身的所有后代 ID。"""
    row = conn.execute("SELECT ancestor_path FROM sys_dept WHERE id = %s", (dept_id,)).fetchone()
    if not row:
        return []
    path = f"{row['ancestor_path']}{dept_id}/%"
    return [r["id"] for r in conn.execute(
        "SELECT id FROM sys_dept WHERE ancestor_path LIKE %s", (path,)
    ).fetchall()]


@bp.put("/<int:dept_id>")
@require_login
@require_perm("system:dept:update")
def update_department(dept_id):
    data = request.get_json(silent=True) or {}
    existing = db.query("SELECT * FROM sys_dept WHERE id = %s", (dept_id,), one=True)
    if not existing:
        return fail("部门不存在", 404)
    parent_id = int(data.get("parentId") or 0)
    check_conn = get_conn()
    try:
        descendants = _descendant_ids(check_conn, dept_id)
    finally:
        check_conn.close()
    if parent_id == dept_id or parent_id in descendants:
        return fail("父部门不能是自己或后代部门")
    code = str(data.get("code") or existing["dept_code"]).strip()
    if db.query("SELECT id FROM sys_dept WHERE dept_code = %s AND id <> %s", (code, dept_id), one=True):
        return fail("部门编码已存在")
    conn = get_conn()
    try:
        path = _path(conn, parent_id)
        conn.execute(
            "UPDATE sys_dept SET dept_code = %s, parent_id = %s, dept_name = %s, "
            "leader_user_id = %s, sort_no = %s, enabled_flag = %s WHERE id = %s",
            (code, parent_id, str(data.get("name") or existing["dept_name"]).strip(),
             int(data.get("leaderUserId") or existing["leader_user_id"]),
             int(data.get("sortNo") or existing["sort_no"]),
             1 if data.get("enabled", True) else 0, dept_id),
        )
        # 父链变化后同步刷新所有后代的 ancestor_path。
        descendants = _descendant_ids(conn, dept_id)
        old_prefix = f"{existing['ancestor_path']}{dept_id}/"
        new_prefix = f"{path}{dept_id}/"
        for child in descendants:
            row = conn.execute("SELECT ancestor_path FROM sys_dept WHERE id = %s", (child,)).fetchone()
            if row and row["ancestor_path"].startswith(old_prefix):
                updated = new_prefix + row["ancestor_path"][len(old_prefix):]
                conn.execute("UPDATE sys_dept SET ancestor_path = %s WHERE id = %s", (updated, child))
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": dept_id})


@bp.delete("/<int:dept_id>")
@require_login
@require_perm("system:dept:delete")
def delete_department(dept_id):
    conn = get_conn()
    try:
        if conn.execute("SELECT id FROM sys_dept WHERE parent_id = %s LIMIT 1", (dept_id,)).fetchone():
            return fail("存在子部门，请先删除子项")
        if conn.execute("SELECT user_id FROM sys_user_profile WHERE dept_id = %s LIMIT 1",
                        (dept_id,)).fetchone():
            return fail("部门下仍有用户，请先调整用户部门")
        conn.execute("DELETE FROM sys_role_dept WHERE dept_id = %s", (dept_id,))
        conn.execute("DELETE FROM sys_dept WHERE id = %s", (dept_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": dept_id})
