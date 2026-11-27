"""系统基座接口：菜单树、权限码、P1 组织权限与 P2 基础设施 CRUD。

所有子接口共用 /api/system 前缀；业务子模块按资源拆蓝图，URL 前缀保持 P0 约定。
"""
from flask import Blueprint

from auth import current_user, require_login
from responses import ok
from ...rbac import load_identity, load_menus
from .support import pwd_policy
from .users import bp as users_bp
from .roles import bp as roles_bp
from .menus import bp as menus_bp
from .departments import bp as departments_bp
from .posts import bp as posts_bp
from .dictionaries import bp as dictionaries_bp
from .configs import bp as configs_bp
from .notices import bp as notices_bp

bp = Blueprint("system", __name__, url_prefix="/api/system")


@bp.get("/menus")
@require_login
def menus():
    """当前用户可见菜单树，供前端动态路由与侧栏渲染。"""
    return ok({"items": load_menus(current_user())})


@bp.get("/permissions")
@require_login
def permissions():
    """当前用户权限码集合；'*' 表示全量权限。"""
    identity = load_identity(current_user())
    return ok({"roles": identity["roles"], "items": identity["permissions"]})


@bp.get("/security-policy")
@require_login
def security_policy():
    """当前密码策略；列表接口也会下发，单独暴露便于前端表单校验。"""
    return ok(pwd_policy())


@bp.get("/options")
@require_login
def options():
    """用户/角色表单的候选项：部门、岗位、角色。"""
    import db
    return ok({
        "departments": [
            {"id": row["id"], "code": row["dept_code"], "name": row["dept_name"]}
            for row in db.query(
                "SELECT id, dept_code, dept_name FROM sys_dept WHERE enabled_flag = 1 "
                "ORDER BY sort_no, id"
            )
        ],
        "posts": [
            {"id": row["id"], "code": row["post_code"], "name": row["post_name"]}
            for row in db.query(
                "SELECT id, post_code, post_name FROM sys_post WHERE enabled_flag = 1 "
                "ORDER BY sort_no, id"
            )
        ],
        "roles": [
            {"code": row["role_code"], "name": row["role_name"], "builtIn": bool(row["built_in"])}
            for row in db.query(
                "SELECT role_code, role_name, built_in FROM sys_role WHERE status = 1 "
                "ORDER BY sort_no, id"
            )
        ],
    })


# P1 业务子蓝图：路径分别为 /users、/roles、/menus、/departments、/posts。
bp.register_blueprint(users_bp, url_prefix="/users")
bp.register_blueprint(roles_bp, url_prefix="/roles")
bp.register_blueprint(menus_bp, url_prefix="/menus")
bp.register_blueprint(departments_bp, url_prefix="/departments")
bp.register_blueprint(posts_bp, url_prefix="/posts")

# P2 基础设施：字典 / 参数 / 通知的子蓝图内部已声明完整路径，不再追加前缀。
bp.register_blueprint(dictionaries_bp)
bp.register_blueprint(configs_bp)
bp.register_blueprint(notices_bp)
