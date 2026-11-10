-- 已有数据库增量升级：新增「影视类型」功能（仅需执行一次）
-- 执行：/usr/local/mysql/bin/mysql -u root -p video_manager < migrate_add_types.sql

USE video_manager;

CREATE TABLE IF NOT EXISTS types (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(50) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

INSERT IGNORE INTO types (name) VALUES
  ('电影'), ('电视剧'), ('动漫'), ('纪录片'), ('综艺');

ALTER TABLE videos ADD COLUMN type_id INT UNSIGNED NULL COMMENT '影视类型';
ALTER TABLE videos ADD CONSTRAINT fk_video_type FOREIGN KEY (type_id) REFERENCES types (id) ON DELETE SET NULL;
