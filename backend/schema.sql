-- 视频管理系统数据库初始化脚本
-- 执行方式：/usr/local/mysql/bin/mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS video_manager
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE video_manager;

-- 标签表：一个标签可挂到多个视频（多对多）
CREATE TABLE IF NOT EXISTS tags (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(50) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 影视类型表：单选分类（如 电影 / 电视剧 / 动漫）
CREATE TABLE IF NOT EXISTS types (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(50) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 预置常用类型（已存在则跳过）
INSERT IGNORE INTO types (name) VALUES
  ('电影'), ('电视剧'), ('动漫'), ('纪录片'), ('综艺');

-- 用户表：登录账号，密码存哈希（pbkdf2）；role：user 普通用户 / admin 超级管理员
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：user 普通用户 / admin 超级管理员',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 视频主表（数据按用户隔离：每个用户只能看到自己的视频）
CREATE TABLE IF NOT EXISTS videos (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL COMMENT '归属用户',
  title       VARCHAR(200) NOT NULL,
  file_path   VARCHAR(500) NOT NULL DEFAULT '' COMMENT '本地路径或播放链接',
  type_id     INT UNSIGNED NULL COMMENT '影视类型',
  is_favorite TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否收藏：0 否 1 是',
  is_public   TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否公开：0 私有 1 所有用户可观看',
  description VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '备注',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_title (title),
  KEY idx_user (user_id),
  CONSTRAINT fk_video_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_video_type FOREIGN KEY (type_id) REFERENCES types (id) ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 视频-标签 关联表（多对多，级联删除）
CREATE TABLE IF NOT EXISTS video_tags (
  video_id INT UNSIGNED NOT NULL,
  tag_id   INT UNSIGNED NOT NULL,
  PRIMARY KEY (video_id, tag_id),
  CONSTRAINT fk_vt_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
  CONSTRAINT fk_vt_tag   FOREIGN KEY (tag_id)   REFERENCES tags (id)   ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
