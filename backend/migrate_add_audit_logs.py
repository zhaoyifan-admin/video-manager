"""存量库迁移：新建审核留痕表 video_audit_logs，并为已有视频补录初始记录。

- 留痕只追加、不修改：记录每次上传 / 提交 / 通过 / 驳回 / 重新提交
- 幂等：表已存在不会重建；已有留痕的视频不会重复补录
- 补录规则：管理员所属且已通过 → auto_approve（免审）；普通用户已通过 → approve；
            已驳回 → reject（带原驳回理由）；待审核 → submit
执行方式：backend/venv/bin/python migrate_add_audit_logs.py
"""
import db

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS video_audit_logs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  video_id      INT UNSIGNED NOT NULL COMMENT '视频 ID',
  action        VARCHAR(24) NOT NULL COMMENT '动作：submit/resubmit/approve/reject/auto_approve',
  from_status   TINYINT NULL COMMENT '变更前审核状态（首次上传为 NULL）',
  to_status     TINYINT NOT NULL COMMENT '变更后审核状态：0 待审核 1 已通过 2 已驳回',
  operator_id   INT UNSIGNED NULL COMMENT '操作人 ID（系统补录为 NULL）',
  operator_name VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  reason        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由 / 动作说明',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_video_time (video_id, created_at),
  KEY idx_created (created_at),
  CONSTRAINT fk_audit_log_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4
"""


def main():
    db.execute(CREATE_SQL)
    print("video_audit_logs 表已就绪")

    # 已有留痕的视频不再补录，避免重复执行脚本产生脏历史
    rows = db.query(
        """
        SELECT v.id, v.audit_status, v.audit_reason, v.created_at, u.role
        FROM videos v
        LEFT JOIN users u ON u.id = v.user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM video_audit_logs l WHERE l.video_id = v.id
        )
        ORDER BY v.id
        """
    )
    if not rows:
        print("没有需要补录的存量视频")
        print("迁移完成")
        return

    records = []
    for r in rows:
        status = r["audit_status"]
        if status == 0:
            action, reason = "submit", "上传视频，提交管理员审核（留痕功能上线前存量数据补录）"
        elif status == 2:
            action = "reject"
            reason = r.get("audit_reason") or "审核未通过（留痕功能上线前存量数据补录）"
        elif r.get("role") == "admin":
            action, reason = "auto_approve", "管理员上传，无需审核直接通过（留痕功能上线前存量数据补录）"
        else:
            action, reason = "approve", "管理员审核通过（留痕功能上线前存量数据补录）"
        records.append((
            r["id"], action, None, status, None, "系统补录", reason[:500], r["created_at"],
        ))

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO video_audit_logs "
                "(video_id, action, from_status, to_status, operator_id, operator_name, reason, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                records,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"已补录 {len(records)} 条存量视频的初始留痕")
    print("迁移完成")


if __name__ == "__main__":
    main()
