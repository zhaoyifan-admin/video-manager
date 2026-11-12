# 影库 · 视频管理系统

技术栈：Python (Flask + PyMySQL) + Vue3（纯手写组件，无 UI 框架）+ MySQL。Netflix 暗红风格，本机 / 局域网部署。

## 功能

- 视频增删查改、关键词搜索、多标签、影视类型、分页；排序（最近更新 / 上架 / 热度 / 播放量 / 标题）与合集筛选、批量设为公开 / 删除
- 播放页：独立播放、收藏、续播（按用户记录进度）、WebVTT 字幕、编码不兼容提示（ffprobe 探测）
- 大图轮播：按热度（播放次数 + 收藏人数 × 5）取最多 9 条已过审且可见的视频；播放计数按「用户 + 视频 + 天」去重
- 登录与数据隔离：按用户隔离视频与收藏；超管可管理全部；审核员（reviewer）独立审核权
- 审核闭环：用户上传 → 待审核（不进主影库）→ 管理员通过 / 驳回（必填理由）→ 上传者查看理由并修改重新送审 → 全程留痕时间线
- 通知：导航未读角标、审核结果页；打开即标记已读
- 存储：自定义保存目录（外接硬盘）、目录浏览与新建、批量导入、存储体检（源文件丢失巡检）、批量路径重定位
- 站点管理：数据看板、账号与角色分配、存储体检、合集管理
- 封面：入库后后台异步 ffmpeg 抽帧，首屏先出占位图再自动补图

## 目录结构

```
video-manager/
├── backend/                # Flask 后端（PyCharm 运行 app.py）
│   ├── app.py              # 应用入口 / 前端托管 / 全局错误处理
│   ├── config.py           # ★ 本机配置（含数据库密码，不入库）
│   ├── config.example.py   # 配置模板
│   ├── db.py / responses.py
│   ├── auth.py             # 登录态、角色、可见性 SQL
│   ├── storage.py          # 媒体目录白名单与路径安全校验
│   ├── thumbnails.py       # ffmpeg 抽帧（后台线程池 + 并发锁）
│   ├── audit_logs.py       # 审核留痕写入工具
│   ├── routes/
│   │   ├── auth.py         # /api/auth（注册/登录/账号与角色）
│   │   ├── videos.py       # /api/videos（列表/增删改/收藏/审核/批量导入）
│   │   ├── media.py        # 上传 / 播放流 / 缩略图 / 字幕 / 编码探测
│   │   ├── paths.py        # /api/paths（媒体根目录浏览）
│   │   ├── audit_logs.py   # /api/audit-logs（全局审核流水）
│   │   └── extra.py        # 进度/通知/存储体检/重定位/合集/看板
│   ├── schema.sql          # 建库与表/列/注释定义（全新安装与存量升级统一入口）
│   └── tests/test_core.py  # 常驻回归测试（标准库 unittest，零额外依赖）
└── frontend/               # Vue3 前端
    └── src/
        ├── main.js         # 路由与守卫
        ├── api.js          # 接口封装（契约 {code, msg, data}，code === 0 成功）
        ├── App.vue         # 影库列表页
        ├── AdminPage.vue / AuditCenterPage.vue / MySubmissionsPage.vue
        ├── PlayerPage.vue / DetailPage.vue / LoginPage.vue
        ├── components/     # 导航 / 轮播 / 卡片 / 表单 / 弹窗 / 时间线
        ├── composables/    # useAuth / useVideos / useCover
        └── ui/             # Toast / 确认框 / NfModal
```

## 首次部署

### 1. 数据库

```bash
# 全新安装 / 存量库升级：统一执行 schema.sql 即可
# （CREATE TABLE IF NOT EXISTS 安全幂等：仅补齐缺失的表/列并写入表与列中文注释，已有结构不受影响）
/usr/local/mysql/bin/mysql -u root -p < backend/schema.sql
```

超管初始账号 `admin / admin123`，**上线后请立即改密**。

### 2. 配置

```bash
cp backend/config.example.py backend/config.py
python3 -c "import secrets; print(secrets.token_hex(32))"   # 生成 SECRET_KEY
```

在 `backend/config.py` 中填写：

| 配置 | 说明 |
|---|---|
| `DB_CONFIG.password` | MySQL 密码 |
| `SECRET_KEY` | 会话签名密钥，必须是 32 位以上随机值；占位符会在启动时报错 |
| `MEDIA_ROOTS` | 额外的媒体根目录绝对路径列表（视频放在非默认位置时登记） |
| `ALLOWED_VIDEO_EXTS` | 允许入库的视频扩展名 |
| `REGISTRATION_ENABLED` | 是否开放注册；关闭后由超管在「站点管理 → 用户与角色」创建账号 |
| `MAX_VIDEOS_PER_USER` | 单用户视频数上限，0 不限 |
| `DEBUG` | 开发调试开关，局域网/公网部署务必保持 `False` |
| `CORS_ORIGINS` | 允许跨域的前端来源；前后端同源部署留空即不启用 CORS |

**媒体目录白名单**：默认允许 `backend/uploads/`、系统检测到的外接硬盘挂载点（macOS `/Volumes/*`、Linux `/media`、`/mnt`、Windows 盘符）、`~/Movies`、`~/Downloads`、`~/Desktop`、`~/Documents`。所有视频路径必须落在这些根内、为允许的视频扩展名，且 `realpath` 解析后不越界（挡符号链接与 `..` 穿越）。写入、读取、删除、目录浏览共用这套校验。

### 3. 启动

```bash
pip3 install -r backend/requirements.txt    # 或用 backend/venv
# PyCharm 运行 backend/app.py → http://127.0.0.1:5000

cd frontend && npm install && npm run dev    # 开发态 http://localhost:5173
cd frontend && npm run build                 # 生产态由 Flask 托管 frontend/dist
```

生产态直接访问 `http://127.0.0.1:5000`；前端路由（`/play/:id`、`/audit` 等）自动回退到 `index.html`。不要用 PyCharm 内置服务器（63343）直接打开 `dist/index.html`。

**长期运行 / 局域网访问**：Flask 内置服务器只适合开发调试，`DEBUG` 已默认关闭。生产或多人访问请用 waitress（已列入 requirements.txt），并把 `HOST` 改为 `0.0.0.0`：

```bash
cd backend
./venv/bin/python -m waitress --host=0.0.0.0 --port=5000 app:app
```

此时本机路径浏览、播放与删除仍受媒体目录白名单约束；请同时确认 `SECRET_KEY` 已随机化、`REGISTRATION_ENABLED` 符合预期。

## 审核流程

1. 普通用户新增 / 批量导入 → `audit_status = 0` 待审核，**不进主影库**，导航「审核结果」可查看
2. 超管或审核员在 `/audit` 表格页通过 / 驳回；驳回必填理由，理由写入 `audit_reason` 并通知上传者
3. 通过后视频进入影库；归属者可设「允许所有用户观看」（未过审时该勾选置灰）
4. 被驳回的视频由本人编辑保存 → 自动重回待审核、清空理由；**已通过的视频一旦更换源文件或字幕，也会重新送审并收回公开**（防止过审后换片绕过审核）
5. 管理员自己上传的视频免审通过，但会留下一条 `auto_approve` 留痕
6. 所有动作写入 `video_audit_logs`（只追加），审核中心「审核记录」页签可查全局流水，每行可展开单视频时间线

角色：`user` 普通用户 / `manager` 管理员（可查看并审核平级及以下用户的视频：管理员、审核员、普通用户）/ `reviewer` 审核员（可审核、查看全部视频，不能编辑删除他人内容）/ `admin` 超级管理员（全部权限 + 站点管理）。普通用户只能看自己上传的视频和已过审且设为公开的视频。

## 存储与路径

- 上传视频默认存 `backend/uploads/`（相对路径入库），也可在「选择保存文件夹」里选外接硬盘（绝对路径入库）
- **存储体检**（站点管理）：列出源文件丢失的记录与当前允许的媒体根目录，外接硬盘未挂载时一眼可见
- **批量路径重定位**：换硬盘 / 改盘符 / 换机器时，把 `filePath` 的旧前缀整体换成新前缀；支持先预览，且**只替换路径、不触发重新审核**
- 删除视频会同时清理数据库记录、白名单内的源文件与缩略图缓存，**不可恢复**
- 编码兼容：本地片源直接由浏览器播放，MKV / HEVC 等浏览器不支持的编码会在播放页给出明确原因与转码建议（需本机安装 ffprobe）

## 测试

```bash
cd backend
./venv/bin/python -m unittest discover -s tests -v
```

覆盖：路径白名单（任意文件读写拦截）、审核绕过防护、播放计数去重、续播、驳回通知已读、审核员权限、看板权限、排序与合集、存储体检与重定位预览、批量导入路径校验。测试账号使用 `__test_` 前缀，结束后由外键级联清理。

## API 一览

所有 `/api` 接口（除 `/api/auth/config`、`/api/auth/check-username`、`/api/auth/register`、`/api/auth/login`）均要求登录，未登录返回 401。

| 分类 | 接口 |
|---|---|
| 认证 | `POST /api/auth/register`、`/login`、`/logout`，`GET /api/auth/me`、`/config`、`/check-username`、`/users`，`POST /api/auth/users`、`/users/:id/role` |
| 视频 | `GET/POST /api/videos`、`GET/PUT/DELETE /api/videos/:id`、`POST /api/videos/batch`、`GET /api/videos/featured` |
| 列表参数 | `keyword` `tagId` `typeId` `favorite` `auditStatus` `scope=gallery/audit/mine` `sort=updated/created/hot/views/title` `collectionId` `ownerId` `page` `pageSize` |
| 审核 | `POST /api/videos/:id/audit`（`{status:1|2, reason}`）、`/public`、`GET /api/videos/:id/audit-logs`、`GET /api/audit-logs` |
| 收藏 / 热度 | `POST /api/videos/:id/favorite`、`/view` |
| 播放 | `GET /api/videos/:id/file`、`/thumb`、`/subtitle`、`/media-info`、`GET/POST /api/videos/:id/progress`、`GET /api/watch-history` |
| 通知 | `GET /api/notifications`、`/notifications/unread-count`、`POST /api/notifications/read` |
| 存储 | `POST /api/videos/upload`、`GET /api/paths/drives`、`/paths/list`、`POST /api/paths/mkdir`、`GET /api/videos/integrity`、`POST /api/videos/relocate` |
| 管理 | `GET/POST /api/collections`、`DELETE /api/collections/:id`、`GET /api/admin/overview` |
| 标签 / 类型 | `GET/POST /api/tags`、`DELETE /api/tags/:id`、`GET/POST /api/types`、`DELETE /api/types/:id` |

## 迁移到其他电脑

1. 两台电脑都装好 Python 3.10+、Node 18+、MySQL 8、ffmpeg/ffprobe（可选但推荐）
2. 新电脑执行 `schema.sql`；旧电脑导出：`mysqldump -u root -p video_manager > video_manager.sql`，新电脑导入
3. 拷贝 `backend/uploads/`、`backend/thumbs/`，以及外接硬盘上的视频目录
4. 若绝对路径变了，用「站点管理 → 存储体检 → 批量路径重定位」批量替换前缀；若新目录不在默认白名单，登记到 `MEDIA_ROOTS`
5. 修改 `config.py` 的密码与 `SECRET_KEY`，重复启动步骤
