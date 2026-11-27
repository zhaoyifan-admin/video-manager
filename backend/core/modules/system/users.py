"""用户管理：分页列表、新增/编辑/删除、密码重置、Excel 导入导出。

数据口径：
- users 是账号主表，只改 username / password_hash / role（主角色快照）；
- 组织与策略状态在 sys_user_profile；角色与岗位在多对多关联表；
- 读写角色/岗位时必须同步 users.role，保证视频子系统既有单层判断不失效。
"""
import io

from flask import Blueprint, g, request, send_file

import db
from auth import hash_password, require_login
from responses import fail, ok
from core.security import require_perm
from .support import get_conn
from .support import  (
    VALID_ROLES, like, page_args, pwd_policy, sync_user_posts, sync_user_roles,
    validate_password, write_password_history, bump_permission_version,
)

bp = Blueprint("system_users", __name__)

LIST_SQL = (
    "SELECT u.id, u.username, u.role, u.created_at, "
    "p.display_name, p.phone, p.email, p.dept_id, p.enabled_flag, "
    "p.pwd_updated_at, p.force_pwd_flag, p.locked_until, p.failed_attempts, "
    "d.dept_name, "
    "(SELECT GROUP_CONCAT(r.role_code ORDER BY r.sort_no) FROM sys_user_role ur "
    " JOIN sys_role r ON r.id = ur.role_id WHERE ur.user_id = u.id) AS role_codes, "
    "(SELECT GROUP_CONCAT(post.post_name ORDER BY post.sort_no) FROM sys_user_post up "
    " JOIN sys_post post ON post.id = up.post_id WHERE up.user_id = u.id) AS post_names "
    "FROM users u "
    "LEFT JOIN sys_user_profile p ON p.user_id = u.id "
    "LEFT JOIN sys_dept d ON d.id = p.dept_id "
)


def _row(item):
    role_codes = [code for code in (item.get("role_codes") or "").split(",") if code]
    return {
        "id": item["id"],
        "username": item["username"],
        "displayName": item.get("display_name") or "",
        "phone": item.get("phone") or "",
        "email": item.get("email") or "",
        "deptId": item.get("dept_id") or 0,
        "deptName": item.get("dept_name") or "",
        "primaryRole": item["role"],
        "roleCodes": role_codes,
        "postNames": item.get("post_names") or "",
        "enabled": bool(item.get("enabled_flag", 1)),
        "createdAt": item.get("created_at"),
        "pwdUpdatedAt": item.get("pwd_updated_at"),
        "forcePwd": bool(item.get("force_pwd_flag")),
        "locked": bool(item.get("locked_until")),
    }


@bp.get("")
@require_login
@require_perm("system:user:list")
def list_users():
    page, size = page_args()
    where, args = ["1 = 1"], []
    keyword = like(request.args.get("keyword"))
    if keyword:
        where.append("(u.username LIKE %s OR p.display_name LIKE %s)")
        args.extend([keyword, keyword])
    dept_id = request.args.get("deptId")
    if dept_id and dept_id.isdigit():
        where.append("p.dept_id = %s")
        args.append(int(dept_id))
    role = (request.args.get("role") or "").strip()
    if role in VALID_ROLES:
        where.append("EXISTS (SELECT 1 FROM sys_user_role ur JOIN sys_role r ON r.id = ur.role_id "
                     "WHERE ur.user_id = u.id AND r.role_code = %s)")
        args.append(role)
    enabled = request.args.get("enabled")
    if enabled in ("0", "1"):
        where.append("COALESCE(p.enabled_flag, 1) = %s")
        args.append(int(enabled))
    clause = " AND ".join(where)
    total = db.query(f"SELECT COUNT(*) AS c FROM users u LEFT JOIN sys_user_profile p "
                     f"ON p.user_id = u.id WHERE {clause}", args, one=True)["c"]
    rows = db.query(
        f"{LIST_SQL} WHERE {clause} ORDER BY u.id LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_row(row) for row in rows], "total": total, "page": page, "pageSize": size,
               "pwdPolicy": pwd_policy()})


@bp.post("")
@require_login
@require_perm("system:user:create")
def create_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    roles = data.get("roleCodes") or ["user"]
    if not username:
        return fail("用户名不能为空")
    if db.query("SELECT id FROM users WHERE username = %s", (username,), one=True):
        return fail("该用户名已被注册")
    error = validate_password(password)
    if error:
        return fail(error)
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hash_password(password)),
        )
        user_id = conn.lastrowid
        conn.execute(
            "INSERT INTO sys_user_profile (user_id, display_name, phone, email, dept_id, enabled_flag, "
            "force_pwd_flag, pwd_updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
            (user_id, str(data.get("displayName") or ""), str(data.get("phone") or ""),
             str(data.get("email") or ""), int(data.get("deptId") or 0),
             1 if data.get("enabled", True) else 0, 1 if data.get("forcePwd") else 0),
        )
        sync_user_roles(conn, user_id, roles)
        sync_user_posts(conn, user_id, data.get("postIds") or [])
        write_password_history(conn, user_id, password)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception as exc:
        conn.rollback()
        if "Duplicate entry" in str(exc):
            return fail("该用户名已被注册")
        raise
    finally:
        conn.close()
    bump_permission_version()
    return ok({"id": user_id, "username": username})


@bp.put("/<int:user_id>")
@require_login
@require_perm("system:user:update")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    row = db.query("SELECT id, username, role FROM users WHERE id = %s", (user_id,), one=True)
    if not row:
        return fail("用户不存在", 404)
    if row["role"] == "admin" and data.get("enabled") is False and g.user["id"] == user_id:
        return fail("不能停用当前登录的超管账号")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sys_user_profile (user_id, display_name, phone, email, dept_id, enabled_flag, "
            "force_pwd_flag) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), phone = VALUES(phone), "
            "email = VALUES(email), dept_id = VALUES(dept_id), enabled_flag = VALUES(enabled_flag), "
            "force_pwd_flag = VALUES(force_pwd_flag)",
            (user_id, str(data.get("displayName") or ""), str(data.get("phone") or ""),
             str(data.get("email") or ""), int(data.get("deptId") or 0),
             1 if data.get("enabled", True) else 0, 1 if data.get("forcePwd") else 0),
        )
        if "roleCodes" in data:
            if user_id == g.user["id"] and "admin" not in (data.get("roleCodes") or []):
                return fail("不能移除自己的超级管理员角色")
            sync_user_roles(conn, user_id, data["roleCodes"])
        if "postIds" in data:
            sync_user_posts(conn, user_id, data["postIds"])
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return fail(str(exc))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    bump_permission_version()
    return ok({"id": user_id})


@bp.delete("/<int:user_id>")
@require_login
@require_perm("system:user:delete")
def delete_user(user_id):
    if user_id == g.user["id"]:
        return fail("不能删除当前登录账号")
    row = db.query("SELECT role FROM users WHERE id = %s", (user_id,), one=True)
    if not row:
        return fail("用户不存在", 404)
    if row["role"] == "admin":
        return fail("超级管理员账号不可删除")
    conn = get_conn()
    try:
        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    bump_permission_version()
    return ok({"id": user_id})


@bp.post("/<int:user_id>/reset-password")
@require_login
@require_perm("system:user:reset-pwd")
def reset_password(user_id):
    data = request.get_json(silent=True) or {}
    password = str(data.get("password") or "")
    if not db.query("SELECT id FROM users WHERE id = %s", (user_id,), one=True):
        return fail("用户不存在", 404)
    error = validate_password(password, user_id=user_id)
    if error:
        return fail(error)
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                     (hash_password(password), user_id))
        conn.execute(
            "UPDATE sys_user_profile SET pwd_updated_at = NOW(), failed_attempts = 0, "
            "locked_until = NULL, force_pwd_flag = %s WHERE user_id = %s",
            (1 if data.get("forcePwd") else 0, user_id),
        )
        write_password_history(conn, user_id, password)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ok({"id": user_id})


@bp.get("/template")
@require_login
@require_perm("system:user:import")
def import_template():
    """下载用户导入模板；表头使用语义字段，不暴露数据库列名。"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "用户导入"
    ws.append(["用户名", "显示姓名", "手机号", "邮箱", "部门编码", "角色编码(逗号分隔)",
               "岗位编码(逗号分隔)", "初始密码"])
    ws.append(["zhangsan", "张三", "13800000000", "zhangsan@example.com", "default",
               "user", "", "ChangeMe123"])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(stream, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="用户导入模板.xlsx")


@bp.post("/import")
@require_login
@require_perm("system:user:import")
def import_users():
    """按行校验、单事务写入；失败返回行号+原因且整体回滚。"""
    from openpyxl import load_workbook
    upload = request.files.get("file")
    if not upload:
        return fail("请选择 Excel 文件")
    try:
        wb = load_workbook(upload.stream, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
    except Exception:
        return fail("Excel 文件解析失败，请确认使用 .xlsx 模板")
    errors, prepared = [], []
    seen = set()
    for index, values in enumerate(rows, start=2):
        if not values or not any(values):
            continue
        cells = [str(v).strip() if v is not None else "" for v in values[:8]]
        username, display, phone, email, dept_code, role_text, post_text, password = cells
        if not username:
            errors.append({"row": index, "reason": "用户名不能为空"})
            continue
        if username in seen:
            errors.append({"row": index, "reason": "文件内用户名重复"})
            continue
        seen.add(username)
        role_codes = [code for code in role_text.split(",") if code] or ["user"]
        invalid = [code for code in role_codes if code not in VALID_ROLES]
        if invalid:
            errors.append({"row": index, "reason": f"角色编码无效：{', '.join(invalid)}"})
            continue
        error = validate_password(password)
        if error:
            errors.append({"row": index, "reason": error})
            continue
        prepared.append((username, display, phone, email, dept_code, role_codes,
                         [code for code in post_text.split(",") if code], password))
    if errors:
        return ok({"success": 0, "failed": errors})
    conn = get_conn()
    failed = []
    try:
        for username, display, phone, email, dept_code, role_codes, post_codes, password in prepared:
            if db.query("SELECT id FROM users WHERE username = %s", (username,), one=True):
                failed.append({"row": 0, "reason": f"用户名已存在：{username}"})
                continue
            dept = conn.execute(
                "SELECT id FROM sys_dept WHERE dept_code = %s AND enabled_flag = 1", (dept_code,)
            ).fetchone()
            if not dept_code or not dept:
                failed.append({"row": 0, "reason": f"部门编码不存在：{dept_code or '空'}"})
                continue
            posts = []
            for code in post_codes:
                post = conn.execute(
                    "SELECT id FROM sys_post WHERE post_code = %s AND enabled_flag = 1", (code,)
                ).fetchone()
                if not post:
                    failed.append({"row": 0, "reason": f"岗位编码不存在：{code}"})
                    break
                posts.append(post["id"])
            if failed:
                continue
            conn.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                         (username, hash_password(password)))
            user_id = conn.lastrowid
            conn.execute(
                "INSERT INTO sys_user_profile (user_id, display_name, phone, email, dept_id, "
                "force_pwd_flag, pwd_updated_at) VALUES (%s, %s, %s, %s, %s, 1, NOW())",
                (user_id, display, phone, email, dept["id"]),
            )
            sync_user_roles(conn, user_id, role_codes)
            if posts:
                sync_user_posts(conn, user_id, posts)
            write_password_history(conn, user_id, password)
        if failed:
            conn.rollback()
        else:
            conn.commit()
    except Exception as exc:
        conn.rollback()
        raise
    finally:
        conn.close()
    if failed:
        return ok({"success": 0, "failed": failed})
    bump_permission_version()
    return ok({"success": len(prepared), "failed": []})


@bp.get("/export")
@require_login
@require_perm("system:user:export")
def export_users():
    """按当前筛选条件导出，不偷跑全表。"""
    from openpyxl import Workbook
    where, args = ["1 = 1"], []
    keyword = like(request.args.get("keyword"))
    if keyword:
        where.append("(u.username LIKE %s OR p.display_name LIKE %s)")
        args.extend([keyword, keyword])
    dept_id = request.args.get("deptId")
    if dept_id and dept_id.isdigit():
        where.append("p.dept_id = %s")
        args.append(int(dept_id))
    clause = " AND ".join(where)
    rows = db.query(
        f"{LIST_SQL} WHERE {clause} ORDER BY u.id LIMIT 5000", args
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "用户列表"
    ws.append(["用户名", "显示姓名", "手机号", "邮箱", "部门", "角色编码", "岗位", "状态", "创建时间"])
    for row in rows:
        item = _row(row)
        ws.append([item["username"], item["displayName"], item["phone"], item["email"],
                   item["deptName"], ",".join(item["roleCodes"]), item["postNames"],
                   "启用" if item["enabled"] else "停用", str(item["createdAt"] or "")])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(stream, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="用户列表.xlsx")
