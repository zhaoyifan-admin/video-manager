"""P2 字典管理：字典类型 / 字典项 CRUD + 带版本号的翻译缓存。

翻译 key 为 dict_code + item_value；字典变更后递增 sys_config.dict_version，
使本进程缓存与其它进程按版本取到的缓存同时失效。刷新接口只做失效，不改业务数据。
"""
import re

from flask import Blueprint, request

import db
from auth import require_login
from responses import fail, ok
from core.security import require_perm
from ... import cache
from .support import get_conn, page_args

bp = Blueprint("system_dictionaries", __name__)

DICT_TTL = 300
CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def _dict_version():
    row = db.query(
        "SELECT config_value FROM sys_config WHERE config_key = 'dict_version'", one=True
    )
    return row["config_value"] if row else "0"


def _bump_version(conn=None):
    sql = (
        "UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1 "
        "WHERE config_key = 'dict_version'"
    )
    if conn is not None:
        conn.execute(sql)
    else:
        db.execute(sql)
    cache.invalidate_prefix("dict:")


def _bool(value, default=True):
    if value is None:
        return default
    return 1 if value else 0


def _type(row):
    return {
        "id": row["id"], "code": row["dict_code"], "name": row["dict_name"],
        "enabled": bool(row["enabled_flag"]), "remark": row["remark"] or "",
        "itemCount": row.get("item_count", 0),
    }


def _item(row):
    return {
        "id": row["id"], "dictTypeId": row["dict_type_id"],
        "dictCode": row.get("dict_code", ""), "value": row["item_value"],
        "label": row["item_label"], "sortNo": row["sort_no"],
        "enabled": bool(row["enabled_flag"]),
    }


# ---------------- 字典类型 ----------------

@bp.get("/dict-types")
@require_login
@require_perm("system:dict:list")
def list_types():
    page, size = page_args()
    keyword = (request.args.get("keyword") or "").strip()
    where = "WHERE (t.dict_code LIKE %s OR t.dict_name LIKE %s)" if keyword else ""
    args = [f"%{keyword}%", f"%{keyword}%"] if keyword else []
    total = db.query(f"SELECT COUNT(*) c FROM sys_dict_type t {where}", args, one=True)["c"]
    rows = db.query(
        "SELECT t.*, (SELECT COUNT(*) FROM sys_dict_item i WHERE i.dict_type_id = t.id) item_count "
        f"FROM sys_dict_type t {where} ORDER BY t.dict_code, t.id LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_type(row) for row in rows], "total": total,
               "page": page, "pageSize": size})


@bp.post("/dict-types")
@require_login
@require_perm("system:dict:create")
def create_type():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not CODE_PATTERN.match(code):
        return fail("字典编码需以字母开头，仅含字母、数字、点、下划线或短横线，且不超过 64 位")
    if not name:
        return fail("字典名称不能为空")
    if db.query("SELECT id FROM sys_dict_type WHERE dict_code = %s", (code,), one=True):
        return fail("字典编码已存在")
    result = db.execute(
        "INSERT INTO sys_dict_type (dict_code, dict_name, enabled_flag, remark) "
        "VALUES (%s, %s, %s, %s)",
        (code, name, _bool(data.get("enabled")), str(data.get("remark") or "")),
    )
    _bump_version()
    return ok({"id": result["lastrowid"]})


@bp.put("/dict-types/<int:type_id>")
@require_login
@require_perm("system:dict:update")
def update_type(type_id):
    data = request.get_json(silent=True) or {}
    existing = db.query("SELECT * FROM sys_dict_type WHERE id = %s", (type_id,), one=True)
    if not existing:
        return fail("字典类型不存在", 404)
    code = str(data.get("code") or existing["dict_code"]).strip()
    name = str(data.get("name") or existing["dict_name"]).strip()
    if not CODE_PATTERN.match(code) or not name:
        return fail("字典编码或名称不合法")
    if db.query("SELECT id FROM sys_dict_type WHERE dict_code = %s AND id <> %s",
                (code, type_id), one=True):
        return fail("字典编码已存在")
    db.execute(
        "UPDATE sys_dict_type SET dict_code = %s, dict_name = %s, enabled_flag = %s, "
        "remark = %s WHERE id = %s",
        (code, name, _bool(data.get("enabled", bool(existing["enabled_flag"]))),
         str(data.get("remark") or existing["remark"] or ""), type_id),
    )
    _bump_version()
    return ok({"id": type_id})


@bp.delete("/dict-types/<int:type_id>")
@require_login
@require_perm("system:dict:delete")
def delete_type(type_id):
    if not db.query("SELECT id FROM sys_dict_type WHERE id = %s", (type_id,), one=True):
        return fail("字典类型不存在", 404)
    db.execute("DELETE FROM sys_dict_type WHERE id = %s", (type_id,))
    _bump_version()
    return ok({"id": type_id})


# ---------------- 字典项 ----------------

@bp.get("/dict-items")
@require_login
@require_perm("system:dict:list")
def list_items():
    page, size = page_args()
    type_id = (request.args.get("dictTypeId") or "").strip()
    dict_code = (request.args.get("dictCode") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    where, args = [], []
    if type_id.isdigit():
        where.append("i.dict_type_id = %s")
        args.append(int(type_id))
    if dict_code:
        where.append("t.dict_code = %s")
        args.append(dict_code)
    if keyword:
        where.append("(i.item_value LIKE %s OR i.item_label LIKE %s)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.query(
        f"SELECT COUNT(*) c FROM sys_dict_item i JOIN sys_dict_type t ON t.id = i.dict_type_id {clause}",
        args, one=True,
    )["c"]
    rows = db.query(
        "SELECT i.*, t.dict_code FROM sys_dict_item i "
        f"JOIN sys_dict_type t ON t.id = i.dict_type_id {clause} "
        "ORDER BY t.dict_code, i.sort_no, i.id LIMIT %s OFFSET %s",
        args + [size, (page - 1) * size],
    )
    return ok({"items": [_item(row) for row in rows], "total": total,
               "page": page, "pageSize": size})


def _resolve_type(conn, data, existing=None):
    """解析字典类型：优先 dictTypeId，其次 dictCode；返回类型 ID 或 None。"""
    type_id = data.get("dictTypeId", existing["dict_type_id"] if existing else None)
    dict_code = str(data.get("dictCode") or "").strip()
    if dict_code:
        row = conn.execute(
            "SELECT id FROM sys_dict_type WHERE dict_code = %s AND enabled_flag = 1", (dict_code,)
        ).fetchone()
        if not row:
            raise ValueError("字典类型不存在或已停用")
        return row["id"]
    try:
        type_id = int(type_id)
    except (TypeError, ValueError):
        raise ValueError("请选择字典类型")
    row = conn.execute(
        "SELECT id FROM sys_dict_type WHERE id = %s AND enabled_flag = 1", (type_id,)
    ).fetchone()
    if not row:
        raise ValueError("字典类型不存在或已停用")
    return type_id


@bp.post("/dict-items")
@require_login
@require_perm("system:dict:item")
def create_item():
    data = request.get_json(silent=True) or {}
    value = str(data.get("value") or "").strip()
    label = str(data.get("label") or "").strip()
    if not value or not label:
        return fail("字典值与显示文案不能为空")
    conn = get_conn()
    try:
        type_id = _resolve_type(conn, data)
        if conn.execute("SELECT id FROM sys_dict_item WHERE dict_type_id = %s AND item_value = %s",
                        (type_id, value)).fetchone():
            return fail("同一字典类型下该字典值已存在")
        result = conn.execute(
            "INSERT INTO sys_dict_item (dict_type_id, item_value, item_label, sort_no, enabled_flag) "
            "VALUES (%s, %s, %s, %s, %s)",
            (type_id, value, label, int(data.get("sortNo") or 0), _bool(data.get("enabled"))),
        )
        # 先取自增 ID：随后的版本号 UPDATE 会覆盖连接上的 lastrowid。
        item_id = result.lastrowid
        _bump_version(conn)
        conn.commit()
        return ok({"id": item_id})
    except ValueError as exc:
        return fail(str(exc))
    finally:
        conn.close()


@bp.put("/dict-items/<int:item_id>")
@require_login
@require_perm("system:dict:item")
def update_item(item_id):
    data = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        existing = conn.execute("SELECT * FROM sys_dict_item WHERE id = %s", (item_id,)).fetchone()
        if not existing:
            return fail("字典项不存在", 404)
        type_id = _resolve_type(conn, data, existing)
        value = str(data.get("value") or existing["item_value"]).strip()
        label = str(data.get("label") or existing["item_label"]).strip()
        if not value or not label:
            return fail("字典值与显示文案不能为空")
        if conn.execute(
            "SELECT id FROM sys_dict_item WHERE dict_type_id = %s AND item_value = %s AND id <> %s",
            (type_id, value, item_id),
        ).fetchone():
            return fail("同一字典类型下该字典值已存在")
        conn.execute(
            "UPDATE sys_dict_item SET dict_type_id = %s, item_value = %s, item_label = %s, "
            "sort_no = %s, enabled_flag = %s WHERE id = %s",
            (type_id, value, label, int(data.get("sortNo") or existing["sort_no"]),
             _bool(data.get("enabled", bool(existing["enabled_flag"]))), item_id),
        )
        _bump_version(conn)
        conn.commit()
        return ok({"id": item_id})
    except ValueError as exc:
        return fail(str(exc))
    finally:
        conn.close()


@bp.delete("/dict-items/<int:item_id>")
@require_login
@require_perm("system:dict:item")
def delete_item(item_id):
    if not db.query("SELECT id FROM sys_dict_item WHERE id = %s", (item_id,), one=True):
        return fail("字典项不存在", 404)
    db.execute("DELETE FROM sys_dict_item WHERE id = %s", (item_id,))
    _bump_version()
    return ok({"id": item_id})


# ---------------- 翻译缓存 ----------------

@bp.get("/dict/options")
@require_login
def dict_options():
    """按 dict_code 返回启用的字典项；无 dictCode 时返回全部类型。"""
    code = (request.args.get("dictCode") or "").strip()
    key = f"dict:{_dict_version()}:{code or '*'}"

    def loader():
        sql = (
            "SELECT t.dict_code, t.dict_name, i.item_value, i.item_label "
            "FROM sys_dict_type t LEFT JOIN sys_dict_item i "
            "ON i.dict_type_id = t.id AND i.enabled_flag = 1 "
            "WHERE t.enabled_flag = 1"
        )
        args = []
        if code:
            sql += " AND t.dict_code = %s"
            args.append(code)
        sql += " ORDER BY t.dict_code, i.sort_no, i.id"
        grouped = {}
        for row in db.query(sql, args):
            entry = grouped.setdefault(row["dict_code"], {
                "code": row["dict_code"], "name": row["dict_name"], "items": [],
            })
            if row["item_value"] is not None:
                entry["items"].append({"value": row["item_value"], "label": row["item_label"]})
        return {"items": [grouped[key_code] for key_code in sorted(grouped)]}

    return ok(cache.remember(key, DICT_TTL, loader))


@bp.post("/dict/refresh")
@require_login
@require_perm("system:dict:update")
def refresh_dict_cache():
    """主动刷新字典缓存：递增版本号 + 清空本进程缓存。"""
    _bump_version()
    return ok({"refreshed": True})
