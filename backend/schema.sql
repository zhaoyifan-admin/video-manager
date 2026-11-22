-- 视频管理系统数据库初始化脚本
-- 执行方式：/usr/local/mysql/bin/mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS video_manager
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE video_manager;

-- 标签表：一个标签可挂到多个视频（多对多）
-- 普通用户可提交新标签，经管理员审核通过（audit_status=1）后才发布（is_published=1）对其他用户可见
CREATE TABLE IF NOT EXISTS tags (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  name         VARCHAR(50) NOT NULL UNIQUE COMMENT '标签名称',
  is_published TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否发布：1 已发布（普通用户可见） 0 未发布',
  audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回（普通用户创建的标签需审核通过才发布）',
  audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由：管理员驳回时必填，展示给标签创建者',
  created_by   INT UNSIGNED NULL COMMENT '创建者用户 ID（管理员创建为 NULL），用于审核追踪',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='标签表：一个标签可挂到多个视频（多对多）；普通用户可提交新标签，经管理员审核通过后发布';

-- 存量库升级：补齐 is_published 列（幂等）
-- 通过 ALTER 补列时用 DEFAULT 1，让补列瞬间存在的旧标签一次性全部置为已发布（不影响正常运行后的发布/下架操作）
SET @col_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'tags' AND column_name = 'is_published'
);
SET @ddl = IF(
  @col_exists = 0,
  'ALTER TABLE tags ADD COLUMN is_published TINYINT(1) NOT NULL DEFAULT 1 COMMENT ''是否发布：0 未发布（普通用户不可见） 1 已发布'' AFTER name',
  'SELECT ''tags.is_published 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 存量库升级：补齐标签审核相关列（幂等）
SET @tag_audit = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'tags' AND column_name = 'audit_status'
);
SET @tag_audit_ddl = IF(
  @tag_audit = 0,
  "ALTER TABLE tags ADD COLUMN audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回' AFTER is_published",
  'SELECT ''tags.audit_status 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @tag_audit_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @tag_reason = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'tags' AND column_name = 'audit_reason'
);
SET @tag_reason_ddl = IF(
  @tag_reason = 0,
  "ALTER TABLE tags ADD COLUMN audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由：管理员驳回时必填' AFTER audit_status",
  'SELECT ''tags.audit_reason 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @tag_reason_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @tag_by = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'tags' AND column_name = 'created_by'
);
SET @tag_by_ddl = IF(
  @tag_by = 0,
  'ALTER TABLE tags ADD COLUMN created_by INT UNSIGNED NULL COMMENT ''创建者用户 ID（管理员创建为 NULL）'' AFTER audit_reason',
  'SELECT ''tags.created_by 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @tag_by_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @tag_upd = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'tags' AND column_name = 'updated_at'
);
SET @tag_upd_ddl = IF(
  @tag_upd = 0,
  'ALTER TABLE tags ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间'' AFTER created_at',
  'SELECT ''tags.updated_at 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @tag_upd_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 存量库回填：旧标签（管理员创建、created_by 为空）补列后 audit_status 默认为 0（待审核），
-- 但旧标签本就是已发布状态，这里统一置为已通过（1），避免“已发布却待审核”的矛盾
UPDATE tags SET audit_status = 1 WHERE created_by IS NULL AND audit_status = 0;

-- 标签审核留痕表：只追加、不修改，记录一条标签从提交到每次审核的完整轨迹
-- action：submit 提交审核 / resubmit 重新提交 / approve 审核通过 / reject 审核驳回 / auto_approve 管理员免审通过
CREATE TABLE IF NOT EXISTS tag_audit_logs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  tag_id        INT UNSIGNED NOT NULL COMMENT '标签 ID',
  action        VARCHAR(24) NOT NULL COMMENT '动作：submit/resubmit/approve/reject/auto_approve',
  from_status   TINYINT NULL COMMENT '变更前审核状态（首次提交为 NULL）',
  to_status     TINYINT NOT NULL COMMENT '变更后审核状态：0 待审核 1 已通过 2 已驳回',
  operator_id   INT UNSIGNED NULL COMMENT '操作人 ID（系统补录为 NULL）',
  operator_name VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  reason        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由 / 动作说明',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '留痕时间',
  KEY idx_tag_time (tag_id, created_at),
  KEY idx_created (created_at),
  CONSTRAINT fk_tag_log_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='标签审核留痕表：只追加、不修改，记录一条标签从提交到每次审核的完整轨迹';

-- 影视类型表：单选分类（如 电影 / 电视剧 / 动漫）
-- 普通用户可提交新类型，经管理员审核通过（audit_status=1）后才发布（is_published=1）对其他用户可见
CREATE TABLE IF NOT EXISTS types (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  name         VARCHAR(50) NOT NULL UNIQUE COMMENT '类型名称（如 电影 / 电视剧 / 动漫）',
  is_published TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否发布：1 已发布（普通用户可见） 0 未发布',
  audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回（普通用户创建的类型需审核通过才发布）',
  audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由：管理员驳回时必填，展示给类型创建者',
  created_by   INT UNSIGNED NULL COMMENT '创建者用户 ID（管理员创建为 NULL），用于审核追踪',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='影视类型表：单选分类（电影 / 电视剧 / 动漫 / 纪录片 / 综艺）；普通用户可提交新类型，经管理员审核通过后发布';

-- 预置常用类型（已存在则跳过）
INSERT IGNORE INTO types (name) VALUES
  ('电影'), ('电视剧'), ('动漫'), ('纪录片'), ('综艺');

-- 存量库升级：补齐影视类型审核相关列（幂等）
SET @type_pub = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'types' AND column_name = 'is_published'
);
SET @type_pub_ddl = IF(
  @type_pub = 0,
  'ALTER TABLE types ADD COLUMN is_published TINYINT(1) NOT NULL DEFAULT 1 COMMENT ''是否发布：0 未发布 1 已发布'' AFTER name',
  'SELECT ''types.is_published 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @type_pub_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @type_audit = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'types' AND column_name = 'audit_status'
);
SET @type_audit_ddl = IF(
  @type_audit = 0,
  "ALTER TABLE types ADD COLUMN audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回' AFTER is_published",
  'SELECT ''types.audit_status 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @type_audit_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @type_reason = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'types' AND column_name = 'audit_reason'
);
SET @type_reason_ddl = IF(
  @type_reason = 0,
  "ALTER TABLE types ADD COLUMN audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由：管理员驳回时必填' AFTER audit_status",
  'SELECT ''types.audit_reason 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @type_reason_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @type_by = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'types' AND column_name = 'created_by'
);
SET @type_by_ddl = IF(
  @type_by = 0,
  'ALTER TABLE types ADD COLUMN created_by INT UNSIGNED NULL COMMENT ''创建者用户 ID（管理员创建为 NULL）'' AFTER audit_reason',
  'SELECT ''types.created_by 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @type_by_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @type_upd = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'types' AND column_name = 'updated_at'
);
SET @type_upd_ddl = IF(
  @type_upd = 0,
  'ALTER TABLE types ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间'' AFTER created_at',
  'SELECT ''types.updated_at 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @type_upd_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 存量库回填：旧类型（管理员创建、created_by 为空）补列后 audit_status 默认为 0（待审核），
-- 但旧类型本就是已发布状态，这里统一置为已通过（1），避免“已发布却待审核”的矛盾
UPDATE types SET audit_status = 1, is_published = 1 WHERE created_by IS NULL AND audit_status = 0;

-- 影视类型审核留痕表：只追加、不修改，记录一条类型从提交到每次审核的完整轨迹
-- action：submit 提交审核 / resubmit 重新提交 / approve 审核通过 / reject 审核驳回 / auto_approve 管理员免审通过
CREATE TABLE IF NOT EXISTS type_audit_logs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  type_id       INT UNSIGNED NOT NULL COMMENT '类型 ID',
  action        VARCHAR(24) NOT NULL COMMENT '动作：submit/resubmit/approve/reject/auto_approve',
  from_status   TINYINT NULL COMMENT '变更前审核状态（首次提交为 NULL）',
  to_status     TINYINT NOT NULL COMMENT '变更后审核状态：0 待审核 1 已通过 2 已驳回',
  operator_id   INT UNSIGNED NULL COMMENT '操作人 ID（系统补录为 NULL）',
  operator_name VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  reason        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由 / 动作说明',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '留痕时间',
  KEY idx_type_time (type_id, created_at),
  KEY idx_created (created_at),
  CONSTRAINT fk_type_log_type FOREIGN KEY (type_id) REFERENCES types (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='影视类型审核留痕表：只追加、不修改，记录一条类型从提交到每次审核的完整轨迹';

-- 用户表：登录账号，密码存哈希（pbkdf2）
-- role 层级：user 普通用户(1) / reviewer 审核员(2) / manager 管理员(2) / admin 超级管理员(3)
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  username      VARCHAR(50) NOT NULL UNIQUE COMMENT '登录用户名',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希（pbkdf2）',
  role          VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：user 普通用户 / reviewer 审核员 / manager 管理员 / admin 超级管理员',
  avatar        VARCHAR(255) NOT NULL DEFAULT '' COMMENT '头像相对路径（uploads/avatars/...），空串表示未设置，前端回退为首字母',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户表：登录账号，密码存哈希（pbkdf2）';

-- 存量库升级：补齐 avatar 列（幂等）
SET @avatar_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'avatar'
);
SET @avatar_ddl = IF(
  @avatar_exists = 0,
  "ALTER TABLE users ADD COLUMN avatar VARCHAR(255) NOT NULL DEFAULT '' COMMENT '头像相对路径（uploads/avatars/...），空串表示未设置' AFTER role",
  'SELECT ''users.avatar 已存在，跳过补列'' AS msg'
);
PREPARE stmt FROM @avatar_ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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

-- 用户自建片单：与系统合集(collections)完全隔离的多对多维度。
-- collections 是管理员单归属维度（videos.collection_id），不适合做用户片单；
-- 本表仅记录片单元信息，视频成员关系在 playlist_videos 中。同名约束仅限同一账号。
CREATE TABLE IF NOT EXISTS playlists (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '片单 ID',
  user_id     INT UNSIGNED NOT NULL COMMENT '归属用户 ID',
  name        VARCHAR(50)  NOT NULL COMMENT '片单名称',
  description VARCHAR(500) NOT NULL DEFAULT '' COMMENT '片单简介',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  UNIQUE KEY uk_user_name (user_id, name),
  KEY idx_user_updated (user_id, updated_at),
  CONSTRAINT fk_playlist_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户自建片单：与系统合集隔离，管理员仅能管理自己的片单';

-- 片单-视频关联：多对多，带排序号（用户自定义片单内顺序）。
-- 级联删除：片单或视频被删时关联自动清理。
CREATE TABLE IF NOT EXISTS playlist_videos (
  playlist_id INT UNSIGNED NOT NULL COMMENT '片单 ID',
  video_id    INT UNSIGNED NOT NULL COMMENT '视频 ID',
  sort_order  INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '片单内排序号（越大越靠后）',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
  PRIMARY KEY (playlist_id, video_id),
  KEY idx_playlist_order (playlist_id, sort_order),
  KEY idx_video (video_id),
  CONSTRAINT fk_pv_playlist FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
  CONSTRAINT fk_pv_video    FOREIGN KEY (video_id)    REFERENCES videos (id)    ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='片单-视频关联表（多对多，带排序号，级联删除）';

-- ==================== 运营管理：合集审核 / 管理员操作审计 ====================

-- 存量库升级：合集补齐审核相关列（幂等，与 tags / types 同范式）
-- 普通用户可提交合集，审核通过后发布（is_published=1）才对全站可见；
-- 超级管理员可直接发布（免审通过）或暂不发布。
SET @col_pub_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'collections' AND column_name = 'is_published'
);
SET @col_pub_ddl = IF(@col_pub_exists = 0,
  "ALTER TABLE collections ADD COLUMN is_published TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否发布：1 全站可见' AFTER description",
  'SELECT ''collections.is_published 已存在，跳过补列'' AS msg');
PREPARE stmt FROM @col_pub_ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_status_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'collections' AND column_name = 'audit_status'
);
SET @col_status_ddl = IF(@col_status_exists = 0,
  "ALTER TABLE collections ADD COLUMN audit_status TINYINT NOT NULL DEFAULT 0 COMMENT '审核状态：0 待审核 1 已通过 2 已驳回' AFTER is_published",
  'SELECT ''collections.audit_status 已存在，跳过补列'' AS msg');
PREPARE stmt FROM @col_status_ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_reason_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'collections' AND column_name = 'audit_reason'
);
SET @col_reason_ddl = IF(@col_reason_exists = 0,
  "ALTER TABLE collections ADD COLUMN audit_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由，展示给创建者' AFTER audit_status",
  'SELECT ''collections.audit_reason 已存在，跳过补列'' AS msg');
PREPARE stmt FROM @col_reason_ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_creator_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'collections' AND column_name = 'created_by'
);
SET @col_creator_ddl = IF(@col_creator_exists = 0,
  "ALTER TABLE collections ADD COLUMN created_by INT UNSIGNED NULL COMMENT '提交者用户 ID，NULL 表示系统存量数据' AFTER audit_reason",
  'SELECT ''collections.created_by 已存在，跳过补列'' AS msg');
PREPARE stmt FROM @col_creator_ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 存量回填：升级前已存在的合集本就是全站可见，统一置为「已通过 + 已发布」，
-- 避免「已发布却待审核」的矛盾；新建的待审条目 created_by 非空，不会被误改。
UPDATE collections SET audit_status = 1, is_published = 1
WHERE created_by IS NULL AND audit_status = 0;

-- 合集审核留痕表：只追加、不修改，与 tag_audit_logs / type_audit_logs 同构
CREATE TABLE IF NOT EXISTS collection_audit_logs (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  collection_id   INT UNSIGNED NOT NULL COMMENT '合集 ID',
  action          VARCHAR(24) NOT NULL COMMENT '动作：submit/resubmit/approve/reject/auto_approve',
  from_status     TINYINT NULL COMMENT '变更前审核状态（首次提交为 NULL）',
  to_status       TINYINT NOT NULL COMMENT '变更后审核状态：0 待审核 1 已通过 2 已驳回',
  operator_id     INT UNSIGNED NULL COMMENT '操作人 ID',
  operator_name   VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  reason          VARCHAR(500) NOT NULL DEFAULT '' COMMENT '驳回理由 / 动作说明',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '留痕时间',
  KEY idx_collection_time (collection_id, created_at),
  KEY idx_created (created_at),
  CONSTRAINT fk_collection_log_collection FOREIGN KEY (collection_id)
    REFERENCES collections (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='合集审核留痕表：只追加、不修改';

-- 管理员操作审计：记录敏感管理动作（改角色 / 建账号 / 删视频 / 删合集 / 路径重定位 / 发布下架等）。
-- 操作人与对象均存名称快照，账号或对象删除后历史仍可追溯，因此不设外键。
CREATE TABLE IF NOT EXISTS admin_audit_logs (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  action          VARCHAR(32) NOT NULL COMMENT '动作：change_role/create_user/delete_video/delete_collection/relocate_videos/toggle_publish 等',
  target_type     VARCHAR(24) NOT NULL DEFAULT '' COMMENT '对象类型：user/video/collection/tag/type/path',
  target_id       INT UNSIGNED NULL COMMENT '对象 ID 快照',
  target_name     VARCHAR(200) NOT NULL DEFAULT '' COMMENT '对象名称快照',
  detail          VARCHAR(500) NOT NULL DEFAULT '' COMMENT '变更详情，如「普通用户 → 管理员」',
  operator_id     INT UNSIGNED NULL COMMENT '操作人 ID 快照',
  operator_name   VARCHAR(50) NOT NULL DEFAULT '' COMMENT '操作人名称快照',
  operator_role   VARCHAR(20) NOT NULL DEFAULT '' COMMENT '操作人角色快照',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  KEY idx_created (created_at),
  KEY idx_action (action),
  KEY idx_operator (operator_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='管理员操作审计表：敏感管理动作只追加、不修改';

-- ============ 第四档：影片互动（评分 / 想看清单） ============
-- 评分与收藏相互独立：收藏表达「喜欢且已收」，评分表达量化评价，想看表达未来意向。
-- 三者各自按用户记录，同一部影片对不同用户互不影响；影片/账号删除时级联清理。
CREATE TABLE IF NOT EXISTS video_ratings (
  user_id    INT UNSIGNED NOT NULL COMMENT '评价人 ID',
  video_id   INT UNSIGNED NOT NULL COMMENT '影片 ID',
  score      TINYINT UNSIGNED NOT NULL COMMENT '星级 1~5，由接口校验范围',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次评分时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近改分时间',
  PRIMARY KEY (user_id, video_id),
  KEY idx_rating_video (video_id),
  CONSTRAINT fk_rating_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_rating_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='影片评分表：按用户 1~5 星，均分与评分人数由聚合查询得出';

CREATE TABLE IF NOT EXISTS video_watchlist (
  user_id    INT UNSIGNED NOT NULL COMMENT '用户 ID',
  video_id   INT UNSIGNED NOT NULL COMMENT '影片 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入想看清单的时间',
  PRIMARY KEY (user_id, video_id),
  KEY idx_watchlist_video (video_id),
  CONSTRAINT fk_watchlist_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
  CONSTRAINT fk_watchlist_video FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='想看清单：与收藏分离的「稍后观看」意向';
