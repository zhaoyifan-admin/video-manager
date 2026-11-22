"""管理员操作审计：敏感管理动作只追加写入（不提供修改/删除）。

设计要点：
- 操作人与对象都保存名称快照，账号/视频/合集被删后历史仍可追溯，因此不设外键；
- 记录所有具备管理性质的动作（含普通用户删除自己的视频），角色快照便于按权限回溯；
- 写入失败不应阻断主业务，由调用方通过 try/except 兜底（见 record）。
"""
import db

ACTION_TEXT = {
    "change_role": "调整角色",
    "create_user": "创建账号",
    "delete_video": "删除视频",
    "delete_collection": "删除合集",
    "delete_tag": "删除标签",
    "delete_type": "删除类型",
    "relocate_videos": "路径重定位",
    "toggle_publish": "发布 / 下架",
    "rename": "修改名称",
}

TARGET_TEXT = {
    "user": "账号",
    "video": "视频",
    "collection": "合集",
    "tag": "标签",
    "type": "影视类型",
    "path": "媒体路径",
}


def record(user, action, target_type, target_id=None, target_name="", detail=""):
    """追加一条操作审计。user 为 g.user（dict）或 None（系统动作）。

    审计属于旁路留痕：任何异常都不能影响业务变更的结果，故此处吞掉异常。
    """
    try:
        db.execute(
            "INSERT INTO admin_audit_logs "
            "(action, target_type, target_id, target_name, detail, "
            " operator_id, operator_name, operator_role) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                action,
                target_type,
                target_id,
                (target_name or "")[:200],
                (detail or "")[:500],
                user.get("id") if user else None,
                (user.get("username") if user else "系统") or "系统",
                (user.get("role") if user else "") or "",
            ),
        )
    except Exception:
        pass


def serialize_log(r):
    """转成前端驼峰字段"""
    return {
        "id": r["id"],
        "action": r["action"],
        "actionText": ACTION_TEXT.get(r["action"], r["action"]),
        "targetType": r["target_type"],
        "targetTypeText": TARGET_TEXT.get(r["target_type"], r["target_type"] or "其他"),
        "targetId": r["target_id"],
        "targetName": r["target_name"],
        "detail": r["detail"],
        "operatorId": r["operator_id"],
        "operatorName": r["operator_name"],
        "operatorRole": r["operator_role"],
        "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }
