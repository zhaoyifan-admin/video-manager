"""存量库迁移：新增播放计数 view_count 与按用户收藏表 video_favorites。

- view_count：打开播放页时 +1，用于轮播热度排序
- video_favorites：收藏改为「用户 × 视频」记录，收藏量 = COUNT(*)，
  同时修复旧的 videos.is_favorite 单标记被多用户互相覆盖的问题
- 幂等：列/表已存在时跳过；存量 is_favorite=1 的视频按归属用户回填一条收藏记录
执行方式：backend/venv/bin/python migrate_add_popularity.py
"""
import db
from config import DB_CONFIG

CREATE_FAV_SQL = """
CREATE TABLE IF NOT EXISTS video_favorites (
  user_id    INT UNSIGNED NOT NULL,
  video_id   INT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, video_id),
  KEY idx_fav_video (video_id),
  CONSTRAINT fk_fav_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_fav_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4
"""


def column_exists(table, column):
    return bool(db.query(
        """SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (DB_CONFIG["database"], table, column),
        one=True,
    )["cnt"])


def main():
    if column_exists("videos", "view_count"):
        print("view_count 列已存在，跳过加列")
    else:
        db.execute(
            "ALTER TABLE videos ADD COLUMN view_count INT UNSIGNED NOT NULL DEFAULT 0 "
            "COMMENT '点击/播放次数：打开播放页时 +1' AFTER is_favorite"
        )
        print("已新增 view_count 列")

    db.execute(CREATE_FAV_SQL)
    print("video_favorites 表已就绪")

    # 旧版收藏标记迁移：归属用户补一条收藏，避免升级后已收藏影片丢失
    if column_exists("videos", "is_favorite"):
        result = db.execute(
            "INSERT IGNORE INTO video_favorites (user_id, video_id, created_at) "
            "SELECT user_id, id, created_at FROM videos WHERE is_favorite = 1"
        )
        print(f"已从旧收藏标记回填 {result['rowcount']} 条用户收藏")
    else:
        print("无旧 is_favorite 列，跳过收藏回填")

    total = db.query("SELECT COUNT(*) AS c FROM video_favorites", one=True)["c"]
    print(f"当前收藏记录总数：{total}")
    print("迁移完成")


if __name__ == "__main__":
    main()
