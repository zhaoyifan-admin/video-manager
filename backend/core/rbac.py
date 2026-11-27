"""RBAC 身份、权限与菜单读取。

设计约束：
1. 新表尚未建立或数据未迁移时，自动回退到 users.role 单角色语义，保证视频子系统不中断；
2. 超级管理员权限码用 '*' 表示全量，前端守卫按 wildcard 处理；
3. 所有查询均参数化，菜单中的 component_key 只是本地组件白名单 key，不执行后端下发路径。
"""
import db

from . import cache

PERMISSION_TTL = 60
MENU_TTL = 60


def _safe_query(sql, args=None):
    """平台表不存在时返回 None，交由调用方走兼容分支；其他异常照常抛出。"""
    try:
        return db.query(sql, args)
    except Exception as exc:  # noqa: BLE001 - 明确用于缺表兼容
        message = str(exc).lower()
        if "doesn't exist" in message or "does not exist" in message or "unknown table" in message:
            return None
        if "unknown column" in message:
            return None
        raise


def _permission_version():
    row = _safe_query(
        "SELECT config_value FROM sys_config WHERE config_key = %s LIMIT 1",
        ("permission_version",),
    )
    return row[0]["config_value"] if row else "0"


def _load_roles(user_id, legacy_role):
    rows = _safe_query(
        "SELECT r.role_code FROM sys_user_role ur "
        "JOIN sys_role r ON r.id = ur.role_id "
        "WHERE ur.user_id = %s AND r.status = 1 ORDER BY r.sort_no, r.id",
        (user_id,),
    )
    if rows is None or not rows:
        # 存量账号尚未写入 sys_user_role 时，沿用 users.role
        return [legacy_role or "user"]
    return [row["role_code"] for row in rows]


def _load_permissions(user_id, roles, version):
    key = f"permissions:{user_id}:{version}"

    def loader():
        if "admin" in roles:
            rows = _safe_query(
                "SELECT DISTINCT permission_code FROM sys_menu "
                "WHERE status = 1 AND permission_code <> ''"
            )
            if rows is None:
                return ["*"]
            return [row["permission_code"] for row in rows] or ["*"]
        rows = _safe_query(
            "SELECT DISTINCT m.permission_code FROM sys_menu m "
            "JOIN sys_role_menu rm ON rm.menu_id = m.id "
            "JOIN sys_user_role ur ON ur.role_id = rm.role_id "
            "JOIN sys_role r ON r.id = ur.role_id "
            "WHERE ur.user_id = %s AND m.status = 1 AND r.status = 1 "
            "AND m.permission_code <> ''",
            (user_id,),
        )
        return [row["permission_code"] for row in rows] if rows else []

    return cache.remember(key, PERMISSION_TTL, loader)


def load_identity(user):
    """返回当前用户的 roles / permissions，供 /auth/me 与权限装饰器共用。"""
    if not user:
        return {"roles": [], "permissions": []}
    user_id = user["id"]
    legacy_role = user.get("role") or "user"
    roles = _load_roles(user_id, legacy_role)
    version = _permission_version()
    permissions = _load_permissions(user_id, roles, version)
    return {"roles": roles, "permissions": permissions}


def _build_tree(rows):
    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "code": row["menu_code"],
            "parentId": row["parent_id"] or 0,
            "type": row["menu_type"],
            "title": row["title"],
            "path": row["route_path"],
            "componentKey": row["component_key"],
            "icon": row["icon_key"],
            "permission": row["permission_code"],
            "linkUrl": row["link_url"],
            "cache": bool(row["cache_flag"]),
            "sort": row["sort_no"],
        })
    by_parent = {}
    for item in items:
        by_parent.setdefault(item["parentId"], []).append(item)
    for children in by_parent.values():
        children.sort(key=lambda node: (node["sort"], node["id"]))

    def grow(parent_id):
        return [
            {**node, "children": grow(node["id"])}
            for node in by_parent.get(parent_id, [])
        ]

    return grow(0)


def load_menus(user):
    """返回当前用户可见菜单树；未授权角色返回空树而非报错。"""
    if not user:
        return []
    version = _permission_version()
    key = f"menus:{user['id']}:{version}"
    roles = _load_roles(user["id"], user.get("role") or "user")

    def loader():
        if "admin" in roles:
            rows = _safe_query(
                "SELECT id, menu_code, parent_id, menu_type, title, route_path, "
                "component_key, icon_key, permission_code, link_url, cache_flag, sort_no "
                "FROM sys_menu WHERE status = 1 AND visible_flag = 1 "
                "ORDER BY sort_no, id"
            )
        else:
            rows = _safe_query(
                "SELECT DISTINCT m.id, m.menu_code, m.parent_id, m.menu_type, m.title, "
                "m.route_path, m.component_key, m.icon_key, m.permission_code, "
                "m.link_url, m.cache_flag, m.sort_no "
                "FROM sys_menu m "
                "JOIN sys_role_menu rm ON rm.menu_id = m.id "
                "JOIN sys_user_role ur ON ur.role_id = rm.role_id "
                "JOIN sys_role r ON r.id = ur.role_id "
                "WHERE ur.user_id = %s AND m.status = 1 AND m.visible_flag = 1 "
                "AND r.status = 1 ORDER BY m.sort_no, m.id",
                (user["id"],),
            )
        return _build_tree(rows or [])

    return cache.remember(key, MENU_TTL, loader)
