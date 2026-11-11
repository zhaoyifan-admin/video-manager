"""审核留痕工具：video_audit_logs 只追加写入（不提供修改/删除）。

设计要点：
- 留痕与业务变更共用同一个数据库连接/事务，业务回滚时留痕一并回滚，不会出现「状态变了但没记录」
- operator_name 存操作人名称快照，账号删除后历史仍可追溯
- 系统自动动作（管理员上传免审、存量补录）user 传 None，记为「系统」
"""

ACTION_TEXT = {
    "submit": "提交审核",
    "resubmit": "重新提交",
    "approve": "审核通过",
    "reject": "审核驳回",
    "auto_approve": "免审通过",
}

STATUS_TEXT = {0: "待审核", 1: "已通过", 2: "已驳回"}


def add_log(conn, video_id, action, from_status, to_status, user=None, reason=""):
    """在当前事务内追加一条审核留痕。action 需为 ACTION_TEXT 中的键。"""
    if action not in ACTION_TEXT:
        raise ValueError(f"未知的审核动作：{action}")
    operator_id = user["id"] if user else None
    operator_name = user.get("username", "") if user else "系统"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO video_audit_logs "
            "(video_id, action, from_status, to_status, operator_id, operator_name, reason) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (video_id, action, from_status, to_status, operator_id, operator_name, (reason or "")[:500]),
        )


def serialize_log(row):
    """统一转成前端驼峰字段（单视频时间线与全局流水共用）"""
    from_status = row.get("from_status")
    to_status = row.get("to_status")
    return {
        "id": row["id"],
        "videoId": row["video_id"],
        "videoTitle": row.get("video_title") or "",
        "ownerName": row.get("owner_name") or "",
        "action": row["action"],
        "actionText": ACTION_TEXT.get(row["action"], row["action"]),
        "fromStatus": from_status,
        "toStatus": to_status,
        "fromStatusText": STATUS_TEXT.get(from_status, "") if from_status is not None else "",
        "toStatusText": STATUS_TEXT.get(to_status, ""),
        "operatorName": row.get("operator_name") or "系统",
        "reason": row.get("reason") or "",
        "createdAt": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }
