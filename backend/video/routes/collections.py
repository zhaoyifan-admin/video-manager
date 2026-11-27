"""合集接口：/api/collections（视频侧只读）

视频侧仅保留 GET /api/collections，供视频筛选下拉使用；响应维持 {items: [...]} 契约。
合集的提交 / 审核 / 发布 / 改名 / 删除 / 审核留痕已移至主系统控制台
（/api/video-admin/taxonomy/collection），视频侧不再提供管理接口。
"""
from flask import Blueprint, g

import db
from auth import can_audit, require_login
from responses import ok

bp = Blueprint("collections", __name__, url_prefix="/api/collections")


def _serialize(row, viewer_id, admin_view):
    """序列化合集：所有用户可见 id/name/description/状态/isMine；
    审核角色额外看到创建者与驳回理由，普通用户仅对自己提交的条目可见。"""
    data = {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "videoCount": row.get("video_count") or 0,
        "auditStatus": row["audit_status"],
        "isMine": row["created_by"] == viewer_id,
        "isPublished": bool(row["is_published"]),
    }
    if admin_view:
        data["auditReason"] = row["audit_reason"]
        data["createdBy"] = row["created_by"]
        data["createdByName"] = row.get("created_by_name") or ""
    elif data["isMine"]:
        data["createdBy"] = viewer_id
        data["auditReason"] = row["audit_reason"]
    return data


@bp.get("")
@require_login
def list_collections():
    """合集列表：审核角色看全部；其他用户看已发布 + 自己提交的"""
    admin_view = can_audit(g.user)
    if admin_view:
        rows = db.query(
            "SELECT c.*, u.username AS created_by_name, "
            "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
            "FROM collections c LEFT JOIN users u ON u.id = c.created_by ORDER BY c.name ASC"
        )
    else:
        rows = db.query(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM videos v WHERE v.collection_id = c.id) AS video_count "
            "FROM collections c WHERE c.is_published = 1 OR c.created_by = %s ORDER BY c.name ASC",
            (g.user["id"],),
        )
    return ok({"items": [_serialize(r, g.user["id"], admin_view) for r in rows]})
