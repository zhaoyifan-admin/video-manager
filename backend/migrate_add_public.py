"""存量库迁移：超级管理员 + 视频公开标记（一次性执行）

执行方式：
    cd backend && ./venv/bin/python migrate_add_public.py

做什么：
  1. users 表新增 role 列（user / admin）
  2. 把用户名 admin 的账号设为超级管理员（不存在则创建 admin / admin123）
  3. videos 表新增 is_public 列（0 私有 / 1 公开）
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


def main():
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            # 1. users.role 列
            if not column_exists(cur, "users", "role"):
                cur.execute(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：user 普通用户 / admin 超级管理员'"
                )
                print("✓ 已为 users 新增 role 列")
            else:
                print("• users.role 已存在，跳过")

            # 2. admin 设为超级管理员（不存在则创建）
            cur.execute("SELECT id, username FROM users WHERE username = 'admin'")
            admin = cur.fetchone()
            if not admin:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')",
                    ("admin", hash_password("admin123")),
                )
                print("✓ 已创建超级管理员：admin / admin123")
            else:
                cur.execute("UPDATE users SET role = 'admin' WHERE id = %s", (admin["id"],))
                print(f"✓ 已把账号「{admin['username']}」(id={admin['id']}) 设为超级管理员")

            # 3. videos.is_public 列
            if not column_exists(cur, "videos", "is_public"):
                cur.execute(
                    "ALTER TABLE videos ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否公开：0 私有 1 所有用户可观看' AFTER is_favorite"
                )
                print("✓ 已为 videos 新增 is_public 列")
            else:
                print("• videos.is_public 已存在，跳过")

        conn.commit()
        print("迁移完成")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
