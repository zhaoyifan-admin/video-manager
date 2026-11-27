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

-- ==================== 平台化基座：RBAC / 菜单 / 权限缓存 ====================
-- 说明：沿用本文件既有范式（CREATE TABLE IF NOT EXISTS + 幂等 seed），
-- 不改动 users / videos 等存量表的语义；users.role 仅保留为「主角色快照」，
-- 与 sys_user_role 在同事务内同步（P1 起在多角色写入处保证）。

CREATE TABLE IF NOT EXISTS sys_role (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '角色 ID',
  role_code   VARCHAR(64) NOT NULL UNIQUE COMMENT '角色编码：admin / manager / reviewer / user',
  role_name   VARCHAR(64) NOT NULL COMMENT '角色名称',
  data_scope  VARCHAR(20) NOT NULL DEFAULT 'SELF' COMMENT '数据范围：ALL/DEPT/DEPT_TREE/SELF/CUSTOM（P3 生效）',
  sort_no     INT NOT NULL DEFAULT 0 COMMENT '排序号',
  status      TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态：1 启用 / 0 停用',
  built_in    TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否内置角色：1 内置不可删除',
  remark      VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='平台角色表：RBAC 角色与数据范围定义';

CREATE TABLE IF NOT EXISTS sys_user_role (
  user_id   INT UNSIGNED NOT NULL COMMENT '用户 ID，指向 users.id',
  role_id   INT UNSIGNED NOT NULL COMMENT '角色 ID，指向 sys_role.id',
  PRIMARY KEY (user_id, role_id),
  KEY idx_role (role_id),
  CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES sys_role (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户-角色关联：支持多角色分配';

CREATE TABLE IF NOT EXISTS sys_menu (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '菜单 ID',
  menu_code       VARCHAR(64) NOT NULL UNIQUE COMMENT '菜单编码：seed 与同步使用的稳定键',
  parent_id       INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '父菜单 ID，0 表示根节点',
  parent_code     VARCHAR(64) NOT NULL DEFAULT '' COMMENT '父菜单编码，用于幂等 seed 后回填 parent_id',
  menu_type       ENUM('DIR','MENU','BUTTON') NOT NULL DEFAULT 'MENU' COMMENT '类型：目录 / 菜单 / 按钮',
  title           VARCHAR(64) NOT NULL COMMENT '显示名称',
  route_path      VARCHAR(200) NOT NULL DEFAULT '' COMMENT '前端路由路径',
  component_key   VARCHAR(64) NOT NULL DEFAULT '' COMMENT '前端组件白名单 key，不存可执行路径',
  redirect_path   VARCHAR(200) NOT NULL DEFAULT '' COMMENT '目录默认跳转路径',
  icon_key        VARCHAR(64) NOT NULL DEFAULT '' COMMENT '图标标识',
  permission_code VARCHAR(100) NOT NULL DEFAULT '' COMMENT '权限标识，如 system:user:list',
  link_url        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '外链地址，非空时前端新窗口打开',
  visible_flag    TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否显示：1 显示 / 0 隐藏',
  cache_flag      TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否缓存组件：1 keep-alive',
  sort_no         INT NOT NULL DEFAULT 0 COMMENT '排序号',
  status          TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态：1 启用 / 0 停用',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  KEY idx_parent (parent_id),
  KEY idx_status (status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='平台菜单表：动态路由 / 外链 / 缓存 / 权限标识';

CREATE TABLE IF NOT EXISTS sys_role_menu (
  role_id  INT UNSIGNED NOT NULL COMMENT '角色 ID',
  menu_id  INT UNSIGNED NOT NULL COMMENT '菜单 ID（含按钮级权限）',
  PRIMARY KEY (role_id, menu_id),
  KEY idx_menu (menu_id),
  CONSTRAINT fk_rm_role FOREIGN KEY (role_id) REFERENCES sys_role (id) ON DELETE CASCADE,
  CONSTRAINT fk_rm_menu FOREIGN KEY (menu_id) REFERENCES sys_menu (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='角色-菜单授权：菜单与按钮共用';

CREATE TABLE IF NOT EXISTS sys_config (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '参数 ID',
  config_key   VARCHAR(100) NOT NULL UNIQUE COMMENT '参数键',
  config_value VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '参数值',
  config_group VARCHAR(64) NOT NULL DEFAULT 'system' COMMENT '分组',
  value_type   VARCHAR(20) NOT NULL DEFAULT 'string' COMMENT '值类型：string/number/bool/json',
  cache_flag   TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否参与缓存',
  remark       VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='系统参数表：P0 仅用于权限缓存版本号，P2 开放完整配置管理';

-- 内置角色 seed：保留原有四个角色的编码，视频子系统继续按 users.role 判断无需改动。
INSERT INTO sys_role (role_code, role_name, data_scope, sort_no, status, built_in)
SELECT 'admin', '超级管理员', 'ALL', 10, 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE role_code = 'admin');
INSERT INTO sys_role (role_code, role_name, data_scope, sort_no, status, built_in)
SELECT 'manager', '管理员', 'DEPT_TREE', 20, 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE role_code = 'manager');
INSERT INTO sys_role (role_code, role_name, data_scope, sort_no, status, built_in)
SELECT 'reviewer', '审核员', 'ALL', 30, 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE role_code = 'reviewer');
INSERT INTO sys_role (role_code, role_name, data_scope, sort_no, status, built_in)
SELECT 'user', '普通用户', 'SELF', 40, 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE role_code = 'user');

-- 存量账号按 users.role 建立一条主角色关联，多角色写入由 P1 的用户管理接管。
INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id FROM users u JOIN sys_role r ON r.role_code = u.role;

-- 平台菜单 seed：P0 只交付骨架页面，业务页面在 P1-P4 替换为真实组件。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, cache_flag)
VALUES
  ('system-root', '', 'DIR', '系统管理', '/console/system', '', 'gear', '', 100, 0),
  ('system-user', 'system-root', 'MENU', '用户管理', '/console/system/user', 'SystemPlaceholder', 'user', 'system:user:list', 110, 0),
  ('system-role', 'system-root', 'MENU', '角色管理', '/console/system/role', 'SystemPlaceholder', 'shield', 'system:role:list', 120, 0),
  ('system-menu', 'system-root', 'MENU', '菜单管理', '/console/system/menu', 'SystemPlaceholder', 'bars', 'system:menu:list', 130, 0),
  ('system-dept', 'system-root', 'MENU', '部门管理', '/console/system/dept', 'SystemPlaceholder', 'sitemap', 'system:dept:list', 140, 0),
  ('system-post', 'system-root', 'MENU', '岗位管理', '/console/system/post', 'SystemPlaceholder', 'id-card', 'system:post:list', 150, 0),
  ('system-dict', 'system-root', 'MENU', '字典管理', '/console/system/dict', 'SystemPlaceholder', 'book', 'system:dict:list', 160, 0),
  ('system-config', 'system-root', 'MENU', '参数配置', '/console/system/config', 'SystemPlaceholder', 'sliders', 'system:config:list', 170, 0),
  ('system-notice', 'system-root', 'MENU', '通知公告', '/console/system/notice', 'SystemPlaceholder', 'bell', 'system:notice:list', 180, 0),
  ('log-root', '', 'DIR', '日志审计', '/console/logs', '', 'file-lines', '', 200, 0),
  ('log-operation', 'log-root', 'MENU', '操作日志', '/console/logs/operation', 'SystemPlaceholder', 'list', 'log:operation:list', 210, 0),
  ('log-login', 'log-root', 'MENU', '登录日志', '/console/logs/login', 'SystemPlaceholder', 'right-to-bracket', 'log:login:list', 220, 0),
  ('log-exception', 'log-root', 'MENU', '异常日志', '/console/logs/exception', 'SystemPlaceholder', 'triangle-exclamation', 'log:exception:list', 230, 0),
  ('file-root', '', 'DIR', '文件管理', '/console/files', '', 'folder-open', '', 300, 0),
  ('file-manager', 'file-root', 'MENU', '文件库', '/console/files/manager', 'SystemPlaceholder', 'file', 'file:manager:list', 310, 0);

UPDATE sys_menu m
JOIN sys_menu p ON p.menu_code = m.parent_code
SET m.parent_id = p.id
WHERE m.parent_code <> '';

-- P0 阶段管理控制台仅对超管开放；P1 起按模块细化授权。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_type IN ('DIR','MENU')
WHERE r.role_code = 'admin';

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, value_type, cache_flag, remark)
VALUES ('permission_version', '1', 'system', 'string', 0, '权限缓存版本号：菜单/角色变更后递增');

-- ==================== P1：组织与权限（用户扩展 / 部门 / 岗位 / 密码策略） ====================
-- 说明：全部为新语义字段，不复用 users/videos 的旧业务字段；users 仅作为账号主表被引用。

CREATE TABLE IF NOT EXISTS sys_user_profile (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '扩展记录 ID',
  user_id         INT UNSIGNED NOT NULL UNIQUE COMMENT '账号 ID，指向 users.id（1:1）',
  display_name    VARCHAR(64) NOT NULL DEFAULT '' COMMENT '显示姓名',
  phone           VARCHAR(20) NOT NULL DEFAULT '' COMMENT '手机号',
  email           VARCHAR(100) NOT NULL DEFAULT '' COMMENT '邮箱',
  dept_id         INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '主部门 ID，0 表示未分配',
  enabled_flag    TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用标记：1 启用 / 0 停用',
  pwd_updated_at  DATETIME NULL DEFAULT NULL COMMENT '最近改密时间，NULL 表示从未改密',
  failed_attempts INT NOT NULL DEFAULT 0 COMMENT '连续登录失败次数',
  locked_until    DATETIME NULL DEFAULT NULL COMMENT '账号锁定截止时间',
  force_pwd_flag  TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否强制下次登录改密',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户扩展信息：与 users 1:1，承载组织与密码策略状态';

CREATE TABLE IF NOT EXISTS sys_dept (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '部门 ID',
  dept_code      VARCHAR(64) NOT NULL UNIQUE COMMENT '部门编码：稳定键，导入/接口以此匹配',
  parent_id      INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '父部门 ID，0 表示根',
  ancestor_path  VARCHAR(500) NOT NULL DEFAULT '/' COMMENT '祖先路径 /1/3/，用于后代部门批量查询',
  dept_name      VARCHAR(64) NOT NULL COMMENT '部门名称',
  leader_user_id INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '部门负责人账号 ID，0 表示未设置',
  sort_no        INT NOT NULL DEFAULT 0 COMMENT '排序号',
  enabled_flag   TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用标记：1 启用 / 0 停用',
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  KEY idx_dept_parent (parent_id),
  KEY idx_dept_path (ancestor_path)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='部门表：树形组织，ancestor_path 支持后代 IN 查询';

CREATE TABLE IF NOT EXISTS sys_post (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '岗位 ID',
  post_code   VARCHAR(64) NOT NULL UNIQUE COMMENT '岗位编码：稳定键',
  post_name   VARCHAR(64) NOT NULL COMMENT '岗位名称',
  sort_no     INT NOT NULL DEFAULT 0 COMMENT '排序号',
  enabled_flag TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用标记：1 启用 / 0 停用',
  remark      VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='岗位表：与用户多对多关联';

CREATE TABLE IF NOT EXISTS sys_user_post (
  user_id INT UNSIGNED NOT NULL COMMENT '账号 ID，指向 users.id',
  post_id INT UNSIGNED NOT NULL COMMENT '岗位 ID，指向 sys_post.id',
  PRIMARY KEY (user_id, post_id),
  KEY idx_up_post (post_id),
  CONSTRAINT fk_up_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_up_post FOREIGN KEY (post_id) REFERENCES sys_post (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='用户-岗位关联：多对多';

CREATE TABLE IF NOT EXISTS sys_role_dept (
  role_id INT UNSIGNED NOT NULL COMMENT '角色 ID，指向 sys_role.id',
  dept_id INT UNSIGNED NOT NULL COMMENT '部门 ID，指向 sys_dept.id',
  PRIMARY KEY (role_id, dept_id),
  CONSTRAINT fk_rd_role FOREIGN KEY (role_id) REFERENCES sys_role (id) ON DELETE CASCADE,
  CONSTRAINT fk_rd_dept FOREIGN KEY (dept_id) REFERENCES sys_dept (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='角色-部门授权：data_scope=CUSTOM 时限定部门集合（P3 消费，P1 先建表）';

CREATE TABLE IF NOT EXISTS sys_password_history (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '历史记录 ID',
  user_id       INT UNSIGNED NOT NULL COMMENT '账号 ID，指向 users.id',
  password_hash VARCHAR(255) NOT NULL COMMENT '历史密码哈希，仅用于不可复用比对',
  changed_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '改密时间',
  KEY idx_ph_user (user_id, changed_at),
  CONSTRAINT fk_ph_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='密码历史：P1 密码策略的历史不可复用校验';

-- 存量账号补齐扩展记录：显示名取用户名，部门暂不分配（后续由用户管理页面维护）。
INSERT IGNORE INTO sys_user_profile (user_id, display_name)
SELECT id, username FROM users;

-- 默认根部门：dept_code='default' 作为稳定键，幂等 seed。
INSERT INTO sys_dept (dept_code, parent_id, ancestor_path, dept_name, sort_no, enabled_flag)
SELECT 'default', 0, '/', '默认部门', 10, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_dept WHERE dept_code = 'default');

-- 存量账号挂到默认部门，使 DEPT/DEPT_TREE 数据范围在 P3 开启前有稳定初值。
UPDATE sys_user_profile SET dept_id = (SELECT id FROM sys_dept WHERE dept_code = 'default')
WHERE dept_id = 0;

-- 按钮级权限 seed：visible_flag=0 不下发到侧栏，但进入 permissions 权限码集合。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, visible_flag, cache_flag)
VALUES
  ('system-user-create', 'system-user', 'BUTTON', '新增用户', '', '', '', 'system:user:create', 111, 0, 0),
  ('system-user-update', 'system-user', 'BUTTON', '编辑用户', '', '', '', 'system:user:update', 112, 0, 0),
  ('system-user-delete', 'system-user', 'BUTTON', '删除用户', '', '', '', 'system:user:delete', 113, 0, 0),
  ('system-user-import', 'system-user', 'BUTTON', '导入用户', '', '', '', 'system:user:import', 114, 0, 0),
  ('system-user-export', 'system-user', 'BUTTON', '导出用户', '', '', '', 'system:user:export', 115, 0, 0),
  ('system-user-reset-pwd', 'system-user', 'BUTTON', '重置密码', '', '', '', 'system:user:reset-pwd', 116, 0, 0),
  ('system-role-create', 'system-role', 'BUTTON', '新增角色', '', '', '', 'system:role:create', 121, 0, 0),
  ('system-role-update', 'system-role', 'BUTTON', '编辑角色', '', '', '', 'system:role:update', 122, 0, 0),
  ('system-role-delete', 'system-role', 'BUTTON', '删除角色', '', '', '', 'system:role:delete', 123, 0, 0),
  ('system-role-assign', 'system-role', 'BUTTON', '分配权限', '', '', '', 'system:role:assign', 124, 0, 0),
  ('system-menu-create', 'system-menu', 'BUTTON', '新增菜单', '', '', '', 'system:menu:create', 131, 0, 0),
  ('system-menu-update', 'system-menu', 'BUTTON', '编辑菜单', '', '', '', 'system:menu:update', 132, 0, 0),
  ('system-menu-delete', 'system-menu', 'BUTTON', '删除菜单', '', '', '', 'system:menu:delete', 133, 0, 0),
  ('system-dept-create', 'system-dept', 'BUTTON', '新增部门', '', '', '', 'system:dept:create', 141, 0, 0),
  ('system-dept-update', 'system-dept', 'BUTTON', '编辑部门', '', '', '', 'system:dept:update', 142, 0, 0),
  ('system-dept-delete', 'system-dept', 'BUTTON', '删除部门', '', '', '', 'system:dept:delete', 143, 0, 0),
  ('system-post-create', 'system-post', 'BUTTON', '新增岗位', '', '', '', 'system:post:create', 151, 0, 0),
  ('system-post-update', 'system-post', 'BUTTON', '编辑岗位', '', '', '', 'system:post:update', 152, 0, 0),
  ('system-post-delete', 'system-post', 'BUTTON', '删除岗位', '', '', '', 'system:post:delete', 153, 0, 0);

UPDATE sys_menu m
JOIN sys_menu p ON p.menu_code = m.parent_code
SET m.parent_id = p.id
WHERE m.parent_code <> '';

-- P1 页面组件绑定：component_key 必须是 apps/platform/src/router/dynamic.ts 白名单内的 key。
UPDATE sys_menu SET component_key = 'UserManagePage' WHERE menu_code = 'system-user';
UPDATE sys_menu SET component_key = 'RoleManagePage' WHERE menu_code = 'system-role';
UPDATE sys_menu SET component_key = 'MenuManagePage' WHERE menu_code = 'system-menu';
UPDATE sys_menu SET component_key = 'DeptManagePage' WHERE menu_code = 'system-dept';
UPDATE sys_menu SET component_key = 'PostManagePage' WHERE menu_code = 'system-post';

-- 按钮权限授予超管；manager 仅授予五个模块的查看与编辑类按钮，不含删除/导入/角色分配。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_type = 'BUTTON'
WHERE r.role_code = 'admin';

INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_type = 'BUTTON'
  AND m.permission_code IN (
    'system:user:create','system:user:update','system:user:export',
    'system:role:create','system:role:update',
    'system:menu:create','system:menu:update',
    'system:dept:create','system:dept:update',
    'system:post:create','system:post:update'
  )
WHERE r.role_code = 'manager';

-- 密码策略参数：改 sys_config 即生效，不需要改代码。
INSERT IGNORE INTO sys_config (config_key, config_value, config_group, value_type, cache_flag, remark)
VALUES
  ('pwd_min_length', '8', 'security', 'number', 1, '密码最小长度'),
  ('pwd_require_complex', '1', 'security', 'bool', 1, '是否要求字母+数字混合'),
  ('pwd_history_limit', '3', 'security', 'number', 1, '不可复用的历史密码条数'),
  ('pwd_lock_threshold', '5', 'security', 'number', 1, '连续登录失败锁定阈值'),
  ('pwd_lock_minutes', '15', 'security', 'number', 1, '锁定时长（分钟）'),
  ('pwd_expire_days', '90', 'security', 'number', 1, '密码过期提醒天数');

-- ==================== P2：基础设施（字典 / 参数 / 通知公告） ====================
-- 说明：新增独立语义表，不改动 users / videos / P1 表结构；全部语句可重复执行。

CREATE TABLE IF NOT EXISTS sys_dict_type (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '字典类型 ID',
  dict_code    VARCHAR(64) NOT NULL UNIQUE COMMENT '字典编码：翻译缓存的稳定 key',
  dict_name    VARCHAR(64) NOT NULL COMMENT '字典名称',
  enabled_flag TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用标记：1 启用 / 0 停用',
  remark       VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='字典类型：业务下拉与翻译的唯一入口';

CREATE TABLE IF NOT EXISTS sys_dict_item (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '字典项 ID',
  dict_type_id INT UNSIGNED NOT NULL COMMENT '字典类型 ID，指向 sys_dict_type.id',
  item_value   VARCHAR(100) NOT NULL COMMENT '字典值：与 dict_code 组合为翻译 key',
  item_label   VARCHAR(100) NOT NULL COMMENT '显示文案',
  sort_no      INT NOT NULL DEFAULT 0 COMMENT '排序号',
  enabled_flag TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用标记：1 启用 / 0 停用',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_dict_item (dict_type_id, item_value),
  KEY idx_dict_item_type (dict_type_id),
  CONSTRAINT fk_dict_item_type FOREIGN KEY (dict_type_id) REFERENCES sys_dict_type (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='字典项：同一类型内 item_value 唯一';

CREATE TABLE IF NOT EXISTS sys_notice (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '公告 ID',
  title        VARCHAR(150) NOT NULL COMMENT '标题',
  content_md   TEXT NOT NULL COMMENT '正文（Markdown 纯文本存储，前端按纯文本/Markdown 渲染）',
  notice_type  VARCHAR(20) NOT NULL DEFAULT 'NOTICE' COMMENT '类型：NOTICE 通知 / ANNOUNCEMENT 公告',
  publish_at   DATETIME NULL DEFAULT NULL COMMENT '发布时间；NULL 表示立即发布',
  withdraw_at  DATETIME NULL DEFAULT NULL COMMENT '撤回时间',
  publisher_id INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布人 users.id，0 表示系统',
  status       VARCHAR(20) NOT NULL DEFAULT 'DRAFT' COMMENT '状态：DRAFT/SCHEDULED/PUBLISHED/WITHDRAWN',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  KEY idx_notice_status (status, publish_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='通知公告：撤回不物理删除，发布/撤回以状态与时间为准';

CREATE TABLE IF NOT EXISTS sys_notice_receipt (
  notice_id INT UNSIGNED NOT NULL COMMENT '公告 ID，指向 sys_notice.id',
  user_id   INT UNSIGNED NOT NULL COMMENT '接收人 users.id',
  read_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次已读时间，重复已读不覆盖',
  PRIMARY KEY (notice_id, user_id),
  KEY idx_receipt_user (user_id, read_at),
  CONSTRAINT fk_receipt_notice FOREIGN KEY (notice_id) REFERENCES sys_notice (id) ON DELETE CASCADE,
  CONSTRAINT fk_receipt_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='公告已回执：以是否存在回执判定已读，撤回不清空';

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, value_type, cache_flag, remark)
VALUES
  ('dict_version', '1', 'system', 'number', 0, '字典缓存版本号：字典变更后递增'),
  ('config_version', '1', 'system', 'number', 0, '参数缓存版本号：参数变更后递增');

-- 示例字典：仅作为可编辑的初始数据，业务侧按 dict_code 读取。
INSERT IGNORE INTO sys_dict_type (dict_code, dict_name, enabled_flag, remark)
VALUES ('notice_type', '通知类型', 1, '通知公告的展示类型');
INSERT IGNORE INTO sys_dict_item (dict_type_id, item_value, item_label, sort_no, enabled_flag)
SELECT t.id, 'NOTICE', '通知', 10, 1 FROM sys_dict_type t WHERE t.dict_code = 'notice_type';
INSERT IGNORE INTO sys_dict_item (dict_type_id, item_value, item_label, sort_no, enabled_flag)
SELECT t.id, 'ANNOUNCEMENT', '公告', 20, 1 FROM sys_dict_type t WHERE t.dict_code = 'notice_type';

-- P2 页面组件绑定：component_key 必须在 apps/platform/src/router/dynamic.ts 白名单内。
UPDATE sys_menu SET component_key = 'DictManagePage' WHERE menu_code = 'system-dict';
UPDATE sys_menu SET component_key = 'ConfigManagePage' WHERE menu_code = 'system-config';
UPDATE sys_menu SET component_key = 'NoticeManagePage' WHERE menu_code = 'system-notice';

-- 通知中心：面向所有登录角色，与「系统管理 / 通知公告」管理页分离。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, visible_flag, cache_flag)
VALUES
  ('notice-center', '', 'MENU', '通知中心', '/console/notices', 'NoticeCenterPage', 'bell', 'system:notice:read', 400, 1, 0);

-- P2 按钮权限码：字典、参数、公告管理；notice:read 是通知中心的读取权限。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, visible_flag, cache_flag)
VALUES
  ('system-dict-create', 'system-dict', 'BUTTON', '新增字典类型', '', '', '', 'system:dict:create', 161, 0, 0),
  ('system-dict-update', 'system-dict', 'BUTTON', '编辑字典类型', '', '', '', 'system:dict:update', 162, 0, 0),
  ('system-dict-delete', 'system-dict', 'BUTTON', '删除字典类型', '', '', '', 'system:dict:delete', 163, 0, 0),
  ('system-dict-item', 'system-dict', 'BUTTON', '维护字典项', '', '', '', 'system:dict:item', 164, 0, 0),
  ('system-config-create', 'system-config', 'BUTTON', '新增参数', '', '', '', 'system:config:create', 171, 0, 0),
  ('system-config-update', 'system-config', 'BUTTON', '编辑参数', '', '', '', 'system:config:update', 172, 0, 0),
  ('system-config-delete', 'system-config', 'BUTTON', '删除参数', '', '', '', 'system:config:delete', 173, 0, 0),
  ('system-config-refresh', 'system-config', 'BUTTON', '刷新参数缓存', '', '', '', 'system:config:refresh', 174, 0, 0),
  ('system-notice-create', 'system-notice', 'BUTTON', '新增公告', '', '', '', 'system:notice:create', 181, 0, 0),
  ('system-notice-update', 'system-notice', 'BUTTON', '编辑公告', '', '', '', 'system:notice:update', 182, 0, 0),
  ('system-notice-delete', 'system-notice', 'BUTTON', '删除公告', '', '', '', 'system:notice:delete', 183, 0, 0),
  ('system-notice-publish', 'system-notice', 'BUTTON', '发布公告', '', '', '', 'system:notice:publish', 184, 0, 0),
  ('system-notice-withdraw', 'system-notice', 'BUTTON', '撤回公告', '', '', '', 'system:notice:withdraw', 185, 0, 0),
  ('system-notice-read', 'notice-center', 'BUTTON', '查看通知', '', '', '', 'system:notice:read', 401, 0, 0);

UPDATE sys_menu m
JOIN sys_menu p ON p.menu_code = m.parent_code
SET m.parent_id = p.id
WHERE m.parent_code <> '';

-- 超管获得全部菜单/按钮；其他角色默认可读通知中心，manager 额外获得 P2 的新增/编辑类权限。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_type IN ('DIR','MENU','BUTTON')
WHERE r.role_code = 'admin';

INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_code IN ('notice-center', 'system-notice-read')
WHERE r.role_code IN ('manager', 'reviewer', 'user');

-- manager 是系统管理员角色：可查看 P2 三类管理页并新增/编辑，但不含删除与撤回。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_code IN ('system-dict', 'system-config', 'system-notice')
WHERE r.role_code = 'manager';

INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.permission_code IN (
  'system:dict:create','system:dict:update','system:dict:item',
  'system:config:update','system:config:refresh',
  'system:notice:create','system:notice:update','system:notice:publish'
)
WHERE r.role_code = 'manager';

-- 菜单/按钮授权发生变化，递增权限版本让已有登录会话立即拿到新菜单。
UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1
WHERE config_key = 'permission_version';

-- ==================== P3：审计与数据范围 ====================
-- 三张日志表均为新语义表，不改动存量表；写入侧统一脱敏（见 core/audit.py），
-- 异常日志只存摘要，不在响应里回传完整堆栈。

CREATE TABLE IF NOT EXISTS sys_operate_log (
  id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '日志 ID',
  operator_id       INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '操作人账号 ID，未登录为 0',
  operator_snapshot VARCHAR(255) NOT NULL DEFAULT '' COMMENT '操作人快照 JSON（已脱敏）',
  module_code       VARCHAR(64) NOT NULL DEFAULT '' COMMENT '模块编码，如 system:user',
  action_code       VARCHAR(64) NOT NULL DEFAULT '' COMMENT '动作编码，如 create/update',
  target_snapshot   TEXT COMMENT '请求参数快照 JSON（敏感字段已脱敏）',
  request_path      VARCHAR(300) NOT NULL DEFAULT '' COMMENT '请求方法与路径',
  success_flag      TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否成功：1 成功 / 0 失败',
  cost_ms           INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '耗时毫秒',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  KEY idx_operator (operator_id, created_at),
  KEY idx_module (module_code),
  KEY idx_created (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='操作审计日志：敏感字段脱敏后落库';

CREATE TABLE IF NOT EXISTS sys_login_log (
  id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '日志 ID',
  user_id           INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录账号 ID，失败且账号不存在时为 0',
  account_snapshot  VARCHAR(128) NOT NULL DEFAULT '' COMMENT '登录账号快照',
  login_ip          VARCHAR(64) NOT NULL DEFAULT '' COMMENT '来源 IP',
  result_flag       TINYINT(1) NOT NULL DEFAULT 1 COMMENT '结果：1 成功 / 0 失败',
  fail_reason       VARCHAR(128) NOT NULL DEFAULT '' COMMENT '失败原因（成功为空）',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
  KEY idx_user (user_id, created_at),
  KEY idx_created (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='登录审计日志：成功与失败均记录';

CREATE TABLE IF NOT EXISTS sys_exception_log (
  id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '日志 ID',
  user_id           INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '触发异常的账号 ID，未登录为 0',
  request_path      VARCHAR(300) NOT NULL DEFAULT '' COMMENT '请求方法与路径',
  exception_type    VARCHAR(128) NOT NULL DEFAULT '' COMMENT '异常类名',
  message_digest    VARCHAR(500) NOT NULL DEFAULT '' COMMENT '异常摘要（截断，不含完整堆栈）',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '异常时间',
  KEY idx_user (user_id, created_at),
  KEY idx_created (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT='异常审计日志：只存类型与摘要';

-- 日志页面组件绑定：component_key 必须在 backend/core/modules/system/menus.py 白名单内。
UPDATE sys_menu SET component_key = 'OperationLogPage' WHERE menu_code = 'log-operation';
UPDATE sys_menu SET component_key = 'LoginLogPage' WHERE menu_code = 'log-login';
UPDATE sys_menu SET component_key = 'ExceptionLogPage' WHERE menu_code = 'log-exception';

-- 日志审计授权：超管/管理员/审核员可查看；普通用户不进入日志审计（仍保留通知中心）。
-- 菜单带出的 log:*:list 权限码即查询接口鉴权依据，无需额外按钮权限码。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1
  AND m.menu_code IN ('log-root', 'log-operation', 'log-login', 'log-exception')
WHERE r.role_code IN ('admin', 'manager', 'reviewer');

UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1
WHERE config_key = 'permission_version';

-- ==================== 视频运营管理（管理功能从子系统搬移到主系统） ====================
-- 三个管理页面挂到统一目录；component_key 须在前端动态路由白名单内。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, visible_flag, cache_flag)
VALUES
  ('video-mgmt-root', '', 'DIR', '视频管理', '/console/video-mgmt', '', 'video', '', 500, 1, 0),
  ('video-audit', 'video-mgmt-root', 'MENU', '视频审核', '/console/video-mgmt/audit', 'VideoAuditPage', 'clipboard-check', 'video:audit:list', 510, 1, 0),
  ('video-taxonomy', 'video-mgmt-root', 'MENU', '分类管理', '/console/video-mgmt/taxonomy', 'TaxonomyManagePage', 'tags', 'video:taxonomy:list', 520, 1, 0),
  ('video-site', 'video-mgmt-root', 'MENU', '站点管理', '/console/video-mgmt/site', 'VideoSiteManagePage', 'gauge', 'video:admin:view', 530, 1, 0);

UPDATE sys_menu m
JOIN sys_menu p ON p.menu_code = m.parent_code
SET m.parent_id = p.id
WHERE m.parent_code <> '' AND m.parent_id = 0;

-- 按钮级权限码：审核 / 分类管理 / 站点管理。
INSERT IGNORE INTO sys_menu
  (menu_code, parent_code, menu_type, title, route_path, component_key, icon_key, permission_code, sort_no, visible_flag, cache_flag)
VALUES
  ('video-audit-review', 'video-audit', 'BUTTON', '审核视频', '', '', '', 'video:audit:review', 511, 0, 0),
  ('video-taxonomy-manage', 'video-taxonomy', 'BUTTON', '维护分类', '', '', '', 'video:taxonomy:manage', 521, 0, 0),
  ('video-taxonomy-review', 'video-taxonomy', 'BUTTON', '审核分类', '', '', '', 'video:taxonomy:review', 522, 0, 0),
  ('video-admin-manage', 'video-site', 'BUTTON', '维护存储路径', '', '', '', 'video:admin:manage', 531, 0, 0),
  ('video-admin-log', 'video-site', 'BUTTON', '查看操作审计', '', '', '', 'video:admin:log', 532, 0, 0);

UPDATE sys_menu m
JOIN sys_menu p ON p.menu_code = m.parent_code
SET m.parent_id = p.id
WHERE m.parent_code <> '' AND m.parent_id = 0;

-- 存量库：账号管理已统一到平台用户管理，按钮只保留存储路径职责（幂等）
UPDATE sys_menu SET title = '维护存储路径' WHERE menu_code = 'video-admin-manage' AND title <> '维护存储路径';

-- 授权：超管全部；管理员/审核员可审核视频与分类，站点看板仅管理员及以上。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_type IN ('DIR','MENU','BUTTON')
WHERE r.role_code = 'admin';

INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r
JOIN sys_menu m ON m.status = 1 AND m.menu_code IN (
  'video-mgmt-root', 'video-audit', 'video-taxonomy',
  'video-audit-review', 'video-taxonomy-manage', 'video-taxonomy-review'
)
WHERE r.role_code IN ('manager', 'reviewer');

UPDATE sys_config SET config_value = CAST(config_value AS UNSIGNED) + 1
WHERE config_key = 'permission_version';
