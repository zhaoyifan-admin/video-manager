"""P2 参数配置：CRUD + 值类型校验 + 版本号缓存刷新。

permission_version / dict_version / config_version 是内核自用的版本号，
允许查看但禁止增删改，避免管理界面把缓存失效机制改坏。
"""
import json
import re

from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from ... import cache
from .support import page_args

bp = Blueprint("system_configs", __name__)

CONFIG_TTL = 300
INTERNAL_KEYS = {"permission_version", "dict_version", "config_version"}
KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")
VALUE_TYPES = ("string", "number", "bool", "json")


def _config_version():
    row = db.query(
        "SELECT config_value FROM sys_config WHERE config_key = 'config_version'", one=True
    )
    return row["config_value"] if row else "0"


def _bump_version():
    db.execute(
        "UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1 "
        "WHERE config_key = 'config_version'"
    )
    cache.invalidate_prefix("configs:")
    # 参数里包含权限/菜单缓存版本，刷新参数时一并清掉旧身份缓存。
    cache.invalidate_prefix("permissions:")
    cache.invalidate_prefix("menus:")


def _row(row):
    return {
        "id": row["id"], "key": row["config_key"], "value": row["config_value"],
        "group": row["config_group"], "valueType": row["value_type"],
        "cache": bool(row["cache_flag"]), "remark": row["remark"] or "",
        "builtIn": row["config_key"] in INTERNAL_KEYS,
    }


def _validate(key, value, value_type):
    if not KEY_PATTERN.match(key):
        return "参数键需以字母开头，仅含字母、数字、点、下划线或短横线，且不超过 100 位"
    if value_type not in VALUE_TYPES:
        return "值类型只能是 string / number / bool / json"
    text = str(value)
    if value_type == "number":
        try:
            float(text)
        except ValueError:
            return "数值类型参数请填写合法数字"
    elif value_type == "bool":
        if text not in ("0", "1", "true", "false", "True", "False"):
            return "布尔类型参数请填写 0 / 1"
        text = "1" if text in ("1", "true", "True") else "0"
    elif value_type == "json":
        try:
            json.loads(text)
        except ValueError:
            return "JSON 类型参数内容不是合法 JSON"
    return text


@bp.get("/configs")
@require_login
@require_perm("system:config:list")
def list_configs():
    page, size = page_args()
    keyword = (request.args.get("keyword") or "").strip()
    group = (request.args.get("group") or "").strip()
    where, args = [], []
    if keyword:
        where.append("(config_key LIKE %s OR config_value LIKE %s OR remark LIKE %s)")
        args.extend([f"%{keyword}%"] * 3)
    if group:
        where.append("config_group = %s")
        args.append(group)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.query(f"SELECT COUNT(*) c FROM sys_config {clause}", args, one=True)["c"]
    rows = db.query(
        f"SELECT * FROM sys_config {clause} ORDER BY config_group, config_key LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_row(row) for row in rows], "total": total,
               "page": page, "pageSize": size})


@bp.get("/configs/groups")
@require_login
@require_perm("system:config:list")
def config_groups():
    rows = db.query("SELECT DISTINCT config_group FROM sys_config ORDER BY config_group")
    return ok({"items": [row["config_group"] for row in rows]})


@bp.get("/configs/values")
@require_login
def config_values():
    """按分组返回参数键值；带版本号缓存，供业务模块与前端读取。"""
    group = (request.args.get("group") or "").strip() or "system"
    key = f"configs:{_config_version()}:{group}"

    def loader():
        rows = db.query(
            "SELECT config_key, config_value FROM sys_config "
            "WHERE config_group = %s AND cache_flag = 1", (group,)
        )
        return {"items": {row["config_key"]: row["config_value"] for row in rows}}

    return ok(cache.remember(key, CONFIG_TTL, loader))


@bp.post("/configs")
@require_login
@require_perm("system:config:create")
def create_config():
    data = request.get_json(silent=True) or {}
    key = str(data.get("key") or "").strip()
    value_type = str(data.get("valueType") or "string").strip()
    value = _validate(key, data.get("value", ""), value_type)
    if not isinstance(value, str):
        return fail(value)
    if key in INTERNAL_KEYS:
        return fail("该参数由系统内核维护，不可新增")
    if db.query("SELECT id FROM sys_config WHERE config_key = %s", (key,), one=True):
        return fail("参数键已存在")
    db.execute(
        "INSERT INTO sys_config (config_key, config_value, config_group, value_type, cache_flag, remark) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (key, value, str(data.get("group") or "system").strip(), value_type,
         1 if data.get("cache", True) else 0, str(data.get("remark") or "")),
    )
    _bump_version()
    return ok({"key": key})


@bp.put("/configs/<int:config_id>")
@require_login
@require_perm("system:config:update")
def update_config(config_id):
    data = request.get_json(silent=True) or {}
    existing = db.query("SELECT * FROM sys_config WHERE id = %s", (config_id,), one=True)
    if not existing:
        return fail("参数不存在", 404)
    if existing["config_key"] in INTERNAL_KEYS:
        return fail("该参数由系统内核维护，不可修改")
    key = str(data.get("key") or existing["config_key"]).strip()
    value_type = str(data.get("valueType") or existing["value_type"]).strip()
    value = _validate(key, data.get("value", existing["config_value"]), value_type)
    if not isinstance(value, str):
        return fail(value)
    if key in INTERNAL_KEYS:
        return fail("该参数由系统内核维护，不可修改")
    if db.query("SELECT id FROM sys_config WHERE config_key = %s AND id <> %s",
                (key, config_id), one=True):
        return fail("参数键已存在")
    db.execute(
        "UPDATE sys_config SET config_key = %s, config_value = %s, config_group = %s, "
        "value_type = %s, cache_flag = %s, remark = %s WHERE id = %s",
        (key, value, str(data.get("group") or existing["config_group"]).strip(), value_type,
         1 if data.get("cache", bool(existing["cache_flag"])) else 0,
         str(data.get("remark") or existing["remark"] or ""), config_id),
    )
    _bump_version()
    return ok({"id": config_id})


@bp.delete("/configs/<int:config_id>")
@require_login
@require_perm("system:config:delete")
def delete_config(config_id):
    existing = db.query("SELECT config_key FROM sys_config WHERE id = %s", (config_id,), one=True)
    if not existing:
        return fail("参数不存在", 404)
    if existing["config_key"] in INTERNAL_KEYS:
        return fail("该参数由系统内核维护，不可删除")
    db.execute("DELETE FROM sys_config WHERE id = %s", (config_id,))
    _bump_version()
    return ok({"id": config_id})


@bp.post("/configs/refresh")
@require_login
@require_perm("system:config:refresh")
def refresh_configs():
    """主动刷新参数缓存：递增版本号并清空本进程相关缓存。"""
    _bump_version()
    return ok({"refreshed": True})
