"""存量库迁移脚本：为视频管理系统增加用户体系（一次性执行）

执行方式：
    cd backend && ./venv/bin/python migrate_users.py

做什么：
  1. 创建 users 表（已存在则跳过）
  2. videos 表新增 user_id 列 + 外键（已存在则跳过）
  3. 无任何用户时创建默认管理员 admin / admin123（登录后可在系统里再注册新账号）
  4. 把现有视频全部归属到默认管理员名下
"""
import pymysql

from auth import hash_password
from config import DB_CONFIG


def column_exists(cur, table, column):
    cur.execute(
        """SELECT COUNT(*) AS n FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (DB_CONFIG["database"], table, column),
    )
    return cur.fetchone()["n"] > 0


def table_exists(cur, table):
    cur.execute(
        """SELECT COUNT(*) AS n FROM information_schema.TABLES
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
        (DB_CONFIG["database"], table),
    )
    return cur.fetchone()["n"] > 0


def fk_exists(cur, name):
    cur.execute(
        """SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = %s AND CONSTRAINT_NAME = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'""",
        (DB_CONFIG["database"], name),
    )
    return cur.fetchone()["n"] > 0


def main():
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            # 1. users 表
            if not table_exists(cur, "users"):
                cur.execute(
                    """CREATE TABLE users (
                         id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                         username      VARCHAR(50) NOT NULL UNIQUE,
                         password_hash VARCHAR(255) NOT NULL,
                         created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4"""
                )
                print("✓ 已创建 users 表")
            else:
                print("• users 表已存在，跳过")

            # 2. videos.user_id 列 + 外键
            if not column_exists(cur, "videos", "user_id"):
                cur.execute(
                    "ALTER TABLE videos ADD COLUMN user_id INT UNSIGNED NULL COMMENT '归属用户' AFTER id"
                )
                print("✓ 已为 videos 新增 user_id 列")
            else:
                print("• videos.user_id 已存在，跳过")

            if not fk_exists(cur, "fk_video_user"):
                cur.execute(
                    """ALTER TABLE videos
                         ADD CONSTRAINT fk_video_user FOREIGN KEY (user_id)
                         REFERENCES users (id) ON DELETE CASCADE,
                         ADD KEY idx_user (user_id)"""
                )
                print("✓ 已添加 user_id 外键与索引")
            else:
                print("• user_id 外键已存在，跳过")

            # 3. 默认管理员（仅在库中无任何用户时创建）
            cur.execute("SELECT COUNT(*) AS n FROM users")
            if cur.fetchone()["n"] == 0:
                cur.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    ("admin", hash_password("admin123")),
                )
                print("✓ 已创建默认管理员：admin / admin123（请尽快修改密码）")
            else:
                print("• 库中已有用户，跳过默认管理员创建")

            # 4. 存量视频归属到最早的账号
            cur.execute("SELECT id, username FROM users ORDER BY id ASC LIMIT 1")
            admin = cur.fetchone()
            if admin:
                cur.execute(
                    "UPDATE videos SET user_id = %s WHERE user_id IS NULL",
                    (admin["id"],),
                )
                print(f"✓ 已把 {cur.rowcount} 条存量视频归属到用户「{admin['username']}」")

        conn.commit()
        print("迁移完成")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
