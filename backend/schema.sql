-- 视频管理系统数据库初始化脚本
-- 执行方式：/usr/local/mysql/bin/mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS video_manager
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE video_manager;

-- 标签表：一个标签可挂到多个视频（多对多）
CREATE TABLE IF NOT EXISTS tags (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  name       VARCHAR(50) NOT NULL UNIQUE COMMENT '标签名称',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='标签表：一个标签可挂到多个视频（多对多）';

-- 影视类型表：单选分类（如 电影 / 电视剧 / 动漫）
CREATE TABLE IF NOT EXISTS types (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  name       VARCHAR(50) NOT NULL UNIQUE COMMENT '类型名称（如 电影 / 电视剧 / 动漫）',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='影视类型表：单选分类（电影 / 电视剧 / 动漫 / 纪录片 / 综艺）';

-- 预置常用类型（已存在则跳过）
INSERT IGNORE INTO types (name) VALUES
  ('电影'), ('电视剧'), ('动漫'), ('纪录片'), ('综艺');

-- 用户表：登录账号，密码存哈希（pbkdf2）；role：user 普通用户 / admin 超级管理员
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  username      VARCHAR(50) NOT NULL UNIQUE COMMENT '登录用户名',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希（pbkdf2）',
  role          VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：user 普通用户 / admin 超级管理员',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户表：登录账号，密码存哈希（pbkdf2）';

-- 合集：把多部影片归到一组（剧集 / 系列），可按合集筛选
CREATE TABLE IF NOT EXISTS collections (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  name        VARCHAR(100) NOT NULL UNIQUE COMMENT '合集名称',
  description VARCHAR(500) NOT NULL DEFAULT '' COMMENT '合集简介',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='合集表：把多部影片归到一组（剧集 / 系列），可按合集筛选';

-- 视频主表（数据按用户隔离：每个用户只能看到自己的视频）
CREATE TABLE IF NOT EXISTS videos (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  user_id     INT UNSIGNED NOT NULL COMMENT '归属用户',
  title       VARCHAR(200) NOT NULL COMMENT '视频标题',
  file_path   VARCHAR(500) NOT NULL DEFAULT '' COMMENT '本地路径或播放链接（须在媒体目录白名单内）',
  subtitle_path VARCHAR(500) NOT NULL DEFAULT '' COMMENT 'WebVTT 字幕文件路径',
  collection_id INT UNSIGNED NULL COMMENT '所属合集',
  type_id     INT UNSIGNED NULL COMMENT '影视类型',
  -- 【已废弃】收藏已改为按用户记录（见 video_favorites），此列仅为兼容旧库保留，不再读写
  is_favorite TINYINT(1) NOT NULL DEFAULT 0 COMMENT '【已废弃】收藏已改为按用户记录（见 video_favorites），此列仅为兼容旧库保留，不再读写',
  view_count  INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '点击/播放次数：打开播放页时 +1',
  is_public   TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否公开：0 私有 1 所有用户可观看',
  audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回（未通过的视频不可公开给他人）',
  audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由：管理员驳回时必填，展示给上传用户',
  description VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '备注',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  KEY idx_title (title),
  KEY idx_user (user_id),
  KEY idx_status_public (audit_status, is_public),
  KEY idx_updated (updated_at),
  KEY idx_collection (collection_id),
  CONSTRAINT fk_video_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_video_type FOREIGN KEY (type_id) REFERENCES types (id) ON DELETE SET NULL,
  CONSTRAINT fk_video_collection FOREIGN KEY (collection_id) REFERENCES collections (id) ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='视频主表（数据按用户隔离：每个用户只能看到自己的视频）';

-- 视频-标签 关联表（多对多，级联删除）
CREATE TABLE IF NOT EXISTS video_tags (
  video_id INT UNSIGNED NOT NULL COMMENT '视频 ID',
  tag_id   INT UNSIGNED NOT NULL COMMENT '标签 ID',
  PRIMARY KEY (video_id, tag_id),
  CONSTRAINT fk_vt_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
  CONSTRAINT fk_vt_tag   FOREIGN KEY (tag_id)   REFERENCES tags (id)   ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='视频-标签关联表（多对多，级联删除）';

-- 审核留痕表：只追加、不修改，记录一条视频从上传到每次审核的完整轨迹
-- action：submit 提交审核 / resubmit 修改后重新提交 / approve 审核通过 / reject 审核驳回 / auto_approve 管理员上传免审通过
-- operator_name 存名称快照，即使账号被删除，历史记录仍可追溯
CREATE TABLE IF NOT EXISTS video_audit_logs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  video_id      INT UNSIGNED NOT NULL COMMENT '视频 ID',
  action        VARCHAR(24) NOT NULL COMMENT '动作：submit/resubmit/approve/reject/auto_approve',
  from_status   TINYINT NULL COMMENT '变更前审核状态（首次上传为 NULL）',
  to_status     TINYINT NOT NULL COMMENT '变更后审核状态：0 待审核 1 已通过 2 已驳回',
  operator_id   INT UNSIGNED NULL COMMENT '操作人 ID（系统补录为 NULL）',
  operator_name VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  reason        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由 / 动作说明',
  read_at       DATETIME NULL COMMENT '归属者查看该通知的时间（仅驳回记录有意义）',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '留痕时间',
  KEY idx_video_time (video_id, created_at),
  KEY idx_created (created_at),
  CONSTRAINT fk_audit_log_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='审核留痕表：只追加、不修改，记录一条视频从上传到每次审核的完整轨迹';

-- 按用户收藏表：同一视频可被多个用户各自收藏，收藏量 = COUNT(*)
-- 复合主键保证一个用户对一个视频只有一条记录；视频/用户删除时级联清理
CREATE TABLE IF NOT EXISTS video_favorites (
  user_id    INT UNSIGNED NOT NULL COMMENT '用户 ID',
  video_id   INT UNSIGNED NOT NULL COMMENT '视频 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '收藏时间',
  PRIMARY KEY (user_id, video_id),
  KEY idx_fav_video (video_id),
  CONSTRAINT fk_fav_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_fav_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='按用户收藏表：同一视频可被多个用户各自收藏，收藏量 = COUNT(*)';

-- 观看进度：按用户记录每个视频看到哪里，用于续播与「最近观看」
CREATE TABLE IF NOT EXISTS watch_history (
  user_id          INT UNSIGNED NOT NULL COMMENT '用户 ID',
  video_id         INT UNSIGNED NOT NULL COMMENT '视频 ID',
  position_seconds FLOAT NOT NULL DEFAULT 0 COMMENT '已播放进度（秒）',
  duration_seconds FLOAT NOT NULL DEFAULT 0 COMMENT '视频总时长（秒）',
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (user_id, video_id),
  KEY idx_watch_updated (user_id, updated_at),
  CONSTRAINT fk_watch_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_watch_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='观看进度表：按用户记录每个视频看到哪里，用于续播与「最近观看」';

-- 播放计数去重：同一用户对同一视频每天只累计一次，避免刷新页面刷高热度
CREATE TABLE IF NOT EXISTS video_view_daily (
  user_id   INT UNSIGNED NOT NULL COMMENT '用户 ID',
  video_id  INT UNSIGNED NOT NULL COMMENT '视频 ID',
  view_date DATE NOT NULL COMMENT '播放日期（按天去重）',
  PRIMARY KEY (user_id, video_id, view_date),
  CONSTRAINT fk_view_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_view_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='播放计数去重表：同一用户对同一视频每天只累计一次，避免刷新刷高热度';
