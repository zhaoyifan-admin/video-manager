"""菜单管理：树形 CRUD。

component_key 必须落在前端组件白名单内，禁止下发任意路径，避免后端被篡改后注入路由。
"""
from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from .support import get_conn
from .support import  bump_permission_version

bp = Blueprint("system_menus", __name__)

# 与 apps/platform/src/router/dynamic.ts 的 componentMap 保持一致。
COMPONENT_WHITELIST = {
    "", "SystemPlaceholder", "UserManagePage", "RoleManagePage", "MenuManagePage",
    "DeptManagePage", "PostManagePage", "DictManagePage", "ConfigManagePage",
    "NoticeManagePage", "NoticeCenterPage",
    "OperationLogPage", "LoginLogPage", "ExceptionLogPage",
    "VideoAuditPage", "TaxonomyManagePage", "VideoSiteManagePage",
}
MENU_TYPES = ("DIR", "MENU", "BUTTON")


def _menu(row):
    return {
        "id": row["id"], "code": row["menu_code"], "parentId": row["parent_id"] or 0,
        "type": row["menu_type"], "title": row["title"], "path": row["route_path"] or "",
        "componentKey": row["component_key"] or "", "redirectPath": row["redirect_path"] or "",
        "icon": row["icon_key"] or "", "permission": row["permission_code"] or "",
        "linkUrl": row["link_url"] or "", "visible": bool(row["visible_flag"]),
        "cache": bool(row["cache_flag"]), "sortNo": row["sort_no"],
        "enabled": bool(row["status"]), "buttons": [], "children": [],
    }


def _tree(rows):
    """BUTTON 行不进入菜单树，改为聚合到父菜单的 buttons 字段。

    这样菜单管理页只维护目录/菜单层级，按钮在弹窗底部以动态列表维护；
    BUTTON 行仍留在 sys_menu，角色授权（role_menus）继续按行勾选。
    """
    nodes = {}
    buttons_by_parent = {}
    for row in rows:
        if row["menu_type"] == "BUTTON":
            buttons_by_parent.setdefault(row["parent_id"], []).append({
                "id": row["id"], "code": row["permission_code"] or "",
                "desc": row["title"] or "",
            })
            continue
        nodes[row["id"]] = _menu(row)
    roots = []
    for row in rows:
        if row["menu_type"] == "BUTTON":
            continue
        node = nodes[row["id"]]
        node["buttons"] = buttons_by_parent.get(row["id"], [])
        parent = nodes.get(row["parent_id"] or 0)
        if parent and parent["id"] != node["id"]:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


# 管理列表单独挂 /tree：/api/system/menus 的 GET 已被 rbac 可见菜单树占用，
# 同路径会被前一个注册抢占，导致菜单管理页拿到的是简化结构。
@bp.get("/tree")
@require_login
@require_perm("system:menu:list")
def list_menus():
    rows = db.query("SELECT * FROM sys_menu ORDER BY sort_no, id")
    return ok({"items": _tree(rows), "componentWhitelist": sorted(COMPONENT_WHITELIST),
               "menuTypes": list(MENU_TYPES)})


def _validate(data, existing=None):
    menu_type = str(data.get("type") or (existing or {}).get("menu_type") or "MENU")
    if menu_type not in MENU_TYPES:
        return None, "菜单类型无效"
    component = str(data.get("componentKey") or (existing or {}).get("component_key") or "")
    if component and component not in COMPONENT_WHITELIST:
        return None, f"组件标识必须在白名单内：{', '.join(sorted(c for c in COMPONENT_WHITELIST if c))}"
    code = str(data.get("code") or (existing or {}).get("menu_code") or "").strip()
    if not code:
        return None, "菜单编码不能为空"
    permission = str(data.get("permission") or (existing or {}).get("permission_code") or "")
    if permission and not permission.count(":") >= 1:
        return None, "权限码格式应为 模块:动作，例如 system:user:list"
    title = str(data.get("title") or (existing or {}).get("title") or "").strip()
    if not title:
        return None, "菜单名称不能为空"
    return {
        "menu_code": code,
        "parent_id": int(data.get("parentId") or 0),
        "menu_type": menu_type,
        "title": str(data.get("title") or "").strip(),
        "route_path": str(data.get("path") or "").strip(),
        "component_key": component,
        "redirect_path": str(data.get("redirectPath") or "").strip(),
        "icon_key": str(data.get("icon") or "").strip(),
        "permission_code": permission,
        "link_url": str(data.get("linkUrl") or "").strip(),
        "visible_flag": 1 if data.get("visible", True) else 0,
        "cache_flag": 1 if data.get("cache") else 0,
        "sort_no": int(data.get("sortNo") or 0),
        "status": 1 if data.get("enabled", True) else 0,
    }, None


def _sync_buttons(conn, menu_id, menu_type, menu_code, buttons):
    """在菜单事务内同步底部按钮列表（BUTTON 行仍参与 RBAC 授权）。

    buttons: [{"id"?: int, "code": 权限码, "desc": 描述}]；未提交到的旧按钮删除，
    并同步清理角色授权，避免出现无菜单归属的孤儿授权。
    """
    if menu_type != "MENU" and buttons:
        raise ValueError("只有菜单类型才能维护按钮")
    items = buttons if isinstance(buttons, list) else []
    seen = set()
    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("按钮格式无效")
        code = str(item.get("code") or "").strip()
        desc = str(item.get("desc") or "").strip()
        if not code:
            raise ValueError(f"第 {index + 1} 个按钮的权限码不能为空")
        if not desc:
            raise ValueError(f"第 {index + 1} 个按钮的描述不能为空")
        if code.count(":") < 1:
            raise ValueError(f"按钮权限码格式应为 模块:动作：{code}")
        if code in seen:
            raise ValueError(f"按钮权限码重复：{code}")
        seen.add(code)
        normalized.append({
            "id": int(item.get("id") or 0),
            "code": code,
            "desc": desc,
            "sort": index + 1,
        })

    existing = {
        row["id"]: row for row in conn.execute(
            "SELECT id, menu_code FROM sys_menu WHERE parent_id = %s AND menu_type = 'BUTTON'",
            (menu_id,),
        ).fetchall()
    }
    keep_ids = set()
    for item in normalized:
        if item["id"] and item["id"] not in existing:
            raise ValueError(f"按钮不存在或不归属当前菜单：{item['id']}")
        if item["id"]:
            keep_ids.add(item["id"])
            conn.execute(
                "UPDATE sys_menu SET title = %s, permission_code = %s, sort_no = %s WHERE id = %s",
                (item["desc"], item["code"], item["sort"], item["id"]),
            )
            continue
        base = f"{menu_code}-btn-{item['code']}".replace(":", "-")
        button_code = base[:64]
        suffix = 1
        while conn.execute(
            "SELECT id FROM sys_menu WHERE menu_code = %s", (button_code,)
        ).fetchone():
            tail = f"-{suffix}"
            button_code = base[:64 - len(tail)] + tail
            suffix += 1
        conn.execute(
            "INSERT INTO sys_menu (menu_code, parent_id, menu_type, title, permission_code, sort_no, status) "
            "VALUES (%s, %s, 'BUTTON', %s, %s, %s, 1)",
            (button_code, menu_id, item["desc"], item["code"], item["sort"]),
        )

    for button_id in set(existing) - keep_ids:
        conn.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (button_id,))
        conn.execute("DELETE FROM sys_menu WHERE id = %s", (button_id,))


def _check_parent(payload, menu_id=None):
    """校验父级层级：父级必须存在、类型匹配、且不能是当前节点或其后代。"""
    parent_id = payload["parent_id"]
    if not parent_id:
        return None
    parent = db.query(
        "SELECT id, menu_type FROM sys_menu WHERE id = %s", (parent_id,), one=True
    )
    if not parent:
        return "父菜单不存在"
    parent_type = parent["menu_type"]
    menu_type = payload["menu_type"]
    if menu_type == "DIR" and parent_type != "DIR":
        return "目录只能挂在目录或顶级下"
    if menu_type == "MENU" and parent_type != "DIR":
        return "菜单只能挂在目录下"
    if menu_type == "BUTTON" and parent_type != "MENU":
        return "按钮只能挂在菜单下"
    # 沿父链向上遍历：若回到自身说明会形成环（包括把父级设成自己的孙子）
    seen = set()
    cursor = parent_id
    while cursor:
        if menu_id and cursor == menu_id:
            return "父菜单不能是当前菜单或其子菜单"
        if cursor in seen:
            return "菜单层级存在循环"
        seen.add(cursor)
        row = db.query("SELECT parent_id FROM sys_menu WHERE id = %s", (cursor,), one=True)
        cursor = (row or {}).get("parent_id") or 0
    return None


@bp.post("")
@require_login
@require_perm("system:menu:create")
def create_menu():
    body = request.get_json(silent=True) or {}
    payload, error = _validate(body)
    if error:
        return fail(error)
    if payload["menu_type"] == "BUTTON":
        return fail("按钮请在菜单弹窗底部的按钮列表维护")
    if db.query("SELECT id FROM sys_menu WHERE menu_code = %s", (payload["menu_code"],), one=True):
        return fail("菜单编码已存在")
    error = _check_parent(payload)
    if error:
        return fail(error)
    conn = get_conn()
    try:
        columns = ", ".join(payload)
        marks = ", ".join(["%s"] * len(payload))
        conn.execute(f"INSERT INTO sys_menu ({columns}) VALUES ({marks})", tuple(payload.values()))
        menu_id = conn.lastrowid
        _sync_buttons(conn, menu_id, payload["menu_type"], payload["menu_code"], body.get("buttons"))
        bump_permission_version(conn)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": menu_id})


@bp.put("/<int:menu_id>")
@require_login
@require_perm("system:menu:update")
def update_menu(menu_id):
    existing = db.query("SELECT * FROM sys_menu WHERE id = %s", (menu_id,), one=True)
    if not existing:
        return fail("菜单不存在", 404)
    body = request.get_json(silent=True) or {}
    payload, error = _validate(body, existing)
    if error:
        return fail(error)
    if payload["menu_type"] == "BUTTON":
        return fail("按钮请在菜单弹窗底部的按钮列表维护")
    if db.query("SELECT id FROM sys_menu WHERE menu_code = %s AND id <> %s",
                (payload["menu_code"], menu_id), one=True):
        return fail("菜单编码已存在")
    error = _check_parent(payload, menu_id)
    if error:
        return fail(error)
    conn = get_conn()
    try:
        assignments = ", ".join(f"{key} = %s" for key in payload)
        conn.execute(f"UPDATE sys_menu SET {assignments} WHERE id = %s",
                     tuple(payload.values()) + (menu_id,))
        if "buttons" in body:
            _sync_buttons(conn, menu_id, payload["menu_type"], payload["menu_code"], body["buttons"])
        elif existing["menu_type"] == "MENU" and payload["menu_type"] != "MENU":
            _sync_buttons(conn, menu_id, payload["menu_type"], payload["menu_code"], [])
        bump_permission_version(conn)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": menu_id})


@bp.delete("/<int:menu_id>")
@require_login
@require_perm("system:menu:delete")
def delete_menu(menu_id):
    if not db.query("SELECT id FROM sys_menu WHERE id = %s", (menu_id,), one=True):
        return fail("菜单不存在", 404)
    child = db.query(
        "SELECT id, menu_type FROM sys_menu WHERE parent_id = %s LIMIT 1", (menu_id,), one=True
    )
    if child and child["menu_type"] != "BUTTON":
        return fail("存在子菜单，请先删除子项")
    conn = get_conn()
    try:
        button_ids = [
            row["id"] for row in conn.execute(
                "SELECT id FROM sys_menu WHERE parent_id = %s AND menu_type = 'BUTTON'", (menu_id,)
            ).fetchall()
        ]
        for button_id in button_ids:
            conn.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (button_id,))
            conn.execute("DELETE FROM sys_menu WHERE id = %s", (button_id,))
        conn.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (menu_id,))
        conn.execute("DELETE FROM sys_menu WHERE id = %s", (menu_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    bump_permission_version()
    return ok({"id": menu_id})
