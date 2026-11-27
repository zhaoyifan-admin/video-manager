"""平台安全入口：功能权限与数据范围装饰器。

视频子系统仍使用 auth.py 中的 require_admin / require_auditor / visible_sql，
公开可见规则保持不变；本模块的数据范围只作用于平台管理接口。
"""
from functools import wraps

from flask import g, jsonify

from .audit import scope_clause
from .rbac import load_identity


def has_permission(user, code):
    if not user:
        return False
    permissions = load_identity(user).get("permissions") or []
    return "*" in permissions or code in permissions


def require_perm(code):
    """视图装饰器：要求指定权限码，需在 require_login 之后使用。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_permission(g.user, code):
                return jsonify({"code": 1, "msg": f"需要权限：{code}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def data_scope(owner_field="user_id", table_alias=""):
    """视图装饰器：按当前用户角色注入数据范围 SQL 片段到 g。

    视图用 g.scope_sql / g.scope_params 参与参数化查询，禁止字符串插值用户输入。
    owner_field 必须是资源表上的白名单列名，不接受请求参数。
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            clause, params = scope_clause(g.user, owner_field, table_alias)
            g.scope_sql = clause
            g.scope_params = params
            return fn(*args, **kwargs)
        return wrapper
    return decorator
