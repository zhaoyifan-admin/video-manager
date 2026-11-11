"""幂等迁移：观看体验 / 通知已读 / 合集 / 索引 / 播放去重 / 审核员相关字段

新库直接用 schema.sql；已有库执行本脚本一次即可。
    ./venv/bin/python migrate_add_experience.py
"""
import db

DB_NAME = db.query("SELECT DATABASE() AS d", one=True)["d"]


def has_table(name):
    return bool(db.query(
        "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (DB_NAME, name), one=True,
    ))


def has_column(table, column):
    return bool(db.query(
        "SELECT 1 FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (DB_NAME, table, column), one=True,
    ))


def has_index(table, index):
    return bool(db.query(
        "SELECT 1 FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s",
        (DB_NAME, table, index), one=True,
    ))


def has_constraint(name):
    return bool(db.query(
        "SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA=%s AND CONSTRAINT_NAME=%s",
        (DB_NAME, name), one=True,
    ))


def run(label, sql):
    db.execute(sql)
    print(f"  ✓ {label}")


def main():
    print(f"迁移数据库：{DB_NAME}")

    if not has_table("collections"):
        run("建 collections 表", """
            CREATE TABLE collections (
              id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              name VARCHAR(100) NOT NULL UNIQUE,
              description VARCHAR(500) NOT NULL DEFAULT '',
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    if not has_table("watch_history"):
        run("建 watch_history 表", """
            CREATE TABLE watch_history (
              user_id INT UNSIGNED NOT NULL,
              video_id INT UNSIGNED NOT NULL,
              position_seconds FLOAT NOT NULL DEFAULT 0,
              duration_seconds FLOAT NOT NULL DEFAULT 0,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (user_id, video_id),
              KEY idx_watch_updated (user_id, updated_at),
              CONSTRAINT fk_watch_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
              CONSTRAINT fk_watch_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    if not has_table("video_view_daily"):
        run("建 video_view_daily 表", """
            CREATE TABLE video_view_daily (
              user_id INT UNSIGNED NOT NULL,
              video_id INT UNSIGNED NOT NULL,
              view_date DATE NOT NULL,
              PRIMARY KEY (user_id, video_id, view_date),
              CONSTRAINT fk_view_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
              CONSTRAINT fk_view_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    if not has_column("videos", "subtitle_path"):
        run("videos.subtitle_path", "ALTER TABLE videos ADD COLUMN subtitle_path VARCHAR(500) NOT NULL DEFAULT ''")
    if not has_column("videos", "collection_id"):
        run("videos.collection_id", "ALTER TABLE videos ADD COLUMN collection_id INT UNSIGNED NULL")
    if not has_column("video_audit_logs", "read_at"):
        run("video_audit_logs.read_at", "ALTER TABLE video_audit_logs ADD COLUMN read_at DATETIME NULL")

    for idx, cols in (
        ("idx_status_public", "audit_status, is_public"),
        ("idx_updated", "updated_at"),
        ("idx_collection", "collection_id"),
    ):
        if not has_index("videos", idx):
            run(f"索引 videos.{idx}", f"ALTER TABLE videos ADD INDEX {idx} ({cols})")

    if not has_constraint("fk_video_collection"):
        run("外键 videos → collections", """
            ALTER TABLE videos ADD CONSTRAINT fk_video_collection
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
        """)

    print("迁移完成（可重复执行）")


if __name__ == "__main__":
    main()
