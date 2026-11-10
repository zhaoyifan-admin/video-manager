-- 已有数据库增量升级：新增「收藏」功能（仅需执行一次）
-- 执行：/usr/local/mysql/bin/mysql -u root -p video_manager < migrate_add_favorites.sql

USE video_manager;

ALTER TABLE videos ADD COLUMN is_favorite TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否收藏：0 否 1 是';
