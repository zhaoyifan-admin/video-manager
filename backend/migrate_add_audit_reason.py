"""存量库迁移：videos 表新增驳回理由列 audit_reason。

- 驳回理由由管理员填写，展示给上传用户，用于说明未通过原因
- 幂等：列已存在时跳过
执行方式：backend/venv/bin/python migrate_add_audit_reason.py
"""
import db
from config import DB_CONFIG


def main():
    col = db.query(
        """SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'videos' AND COLUMN_NAME = 'audit_reason'""",
        (DB_CONFIG["database"],),
        one=True,
    )["cnt"]

    if col:
        print("audit_reason 列已存在，跳过加列")
    else:
        db.execute(
            "ALTER TABLE videos "
            "ADD COLUMN audit_reason VARCHAR(500) NOT NULL DEFAULT '' "
            "COMMENT '驳回理由：管理员驳回时必填，展示给上传用户' AFTER audit_status"
        )
        print("已新增 audit_reason 列")
    print("迁移完成")


if __name__ == "__main__":
    main()
