"""存量库迁移：videos 表新增审核状态列 audit_status。

- 新增列：0 待审核 / 1 已通过 / 2 已驳回，默认 0
- 存量数据全部置为 1（已通过），保持迁移前的可见状态不变
- 幂等：列已存在时跳过
执行方式：backend/venv/bin/python migrate_add_audit.py
"""
import db
from config import DB_CONFIG


def main():
    col = db.query(
        """SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'videos' AND COLUMN_NAME = 'audit_status'""",
        (DB_CONFIG["database"],),
        one=True,
    )["cnt"]

    if col:
        print("audit_status 列已存在，跳过加列")
    else:
        db.execute(
            "ALTER TABLE videos "
            "ADD COLUMN audit_status TINYINT NOT NULL DEFAULT 0 "
            "COMMENT '审核状态：0 待审核 1 已通过 2 已驳回' AFTER is_public"
        )
        print("已新增 audit_status 列（默认 0 待审核）")

    result = db.execute("UPDATE videos SET audit_status = 1 WHERE audit_status = 0")
    print(f"存量视频已置为「已通过」：{result['rowcount']} 条")
    print("迁移完成")


if __name__ == "__main__":
    main()
