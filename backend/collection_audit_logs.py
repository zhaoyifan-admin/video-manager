"""合集审核留痕：动作文本、序列化、写入（与 tag_audit_logs 同范式）

仅依赖 db 与标准库，供 routes/collections.py 调用，避免循环依赖。
"""
import db

STATUS_TEXT = {0: "待审核", 1: "已通过", 2: "已驳回"}

ACTION_TEXT = {
    "submit": "提交审核",
    "resubmit": "重新提交",
    "approve": "审核通过",
    "reject": "审核驳回",
    "auto_approve": "免审通过",
}


def serialize_log(r):
    """把一条合集审核留痕序列化为前端结构"""
    return {
        "id": r["id"],
        "collectionId": r["collection_id"],
        "action": r["action"],
        "actionText": ACTION_TEXT.get(r["action"], r["action"]),
        "fromStatus": r["from_status"],
        "toStatus": r["to_status"],
        "fromStatusText": STATUS_TEXT.get(r["from_status"]) if r["from_status"] is not None else None,
        "toStatusText": STATUS_TEXT.get(r["to_status"]),
        "operatorName": r["operator_name"],
        "reason": r["reason"],
        "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M"),
    }


def add_log(collection_id, action, from_status, to_status, operator_id, operator_name, reason=""):
    """写入一条合集审核留痕（只追加、不修改）"""
    db.execute(
        "INSERT INTO collection_audit_logs "
        "(collection_id, action, from_status, to_status, operator_id, operator_name, reason) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (collection_id, action, from_status, to_status, operator_id, operator_name, reason),
    )
