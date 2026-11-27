# 中型管理系统（视频子系统）

唯一外层入口：`/`（平台登录与控制台）。`backend/` 是主系统后端，`apps/` 是 pnpm monorepo 前端应用目录；视频系统挂在 `/video/`，后续新增子系统按 `backend/<name>/` 与 `apps/<name>/` 建立目录。

技术栈：平台后端 Python Flask + PyMySQL + MySQL；前端为 pnpm workspace + turbo 管理的 Vue3 + TypeScript monorepo，平台应用使用 Element Plus + Pinia，视频子系统使用 Vue3 + TypeScript + Pinia + Tailwind（Netflix 暗红风格）。本机 / 局域网部署。

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

### 平台控制台模块（分批接入）

- P0 基座：统一登录、后端下发菜单与权限码、动态路由、按钮级 `v-permission`
- P1 组织与权限：用户 / 角色 / 菜单 / 部门 / 岗位 CRUD，多角色、Excel 导入导出、密码策略
- P2 基础设施（已接入）：
  - 字典：字典类型 / 字典项 CRUD，按 `dict_code + item_value` 翻译并缓存，支持手动刷新缓存
  - 参数：`sys_config` 统一配置管理，值类型校验，内核版本号参数只读，改动后自动刷新缓存
  - 通知公告：草稿 / 定时发布 / 发布 / 撤回，已读回执与未读角标；普通角色可通过「通知中心」查看，管理端负责发布
  - 页面：`/console/system/dict`、`/console/system/config`、`/console/system/notice`、`/console/notices`
- P3 审计与数据权限（已接入）：
  - 审计：操作 / 登录 / 异常三类日志，敏感字段（密码 / 令牌）递归脱敏后落库；平台写操作与登录成功 / 失败均自动埋点，异常只记类型与摘要
  - 数据范围：按角色 `data_scope`（ALL / DEPT_TREE / DEPT / CUSTOM / SELF）生成参数化 SQL，多角色取最宽；未分配部门退化为仅本人；视频公开可见规则保持独立不受影响
  - 页面：`/console/logs/operation`、`/console/logs/login`、`/console/logs/exception`（只读 + 筛选）；接口 `GET /api/logs/*`

## 目录结构

```
video-manager/
├── backend/                # ★ 主系统后端
│   ├── app.py              # ★ 唯一外层入口（WSGI）：平台 + 子系统挂载
│   ├── config.py           # ★ 全系统共用配置（含数据库密码，不入库）
│   ├── config.example.py   # 配置模板
│   ├── requirements.txt    # 全系统共用 Python 依赖
│   ├── core/               # 平台内核：RBAC / 权限缓存 / 安全入口
│   │   ├── cache.py / rbac.py / security.py
│   │   └── modules/system/ # /api/system 菜单与权限接口
│   └── video/              # 视频子系统后端（新增子系统按同名范式建立）
│       ├── app.py          # 子系统独立运行时入口；由主入口挂载到 /video
│       ├── db.py / responses.py / auth.py / storage.py
│       ├── routes/         # /api/videos、/api/media 等业务蓝图
│       ├── schema.sql      # 建库与表/列/注释定义
│       ├── tests/test_core.py
│       └── venv/           # Python 虚拟环境
├── apps/                   # ★ pnpm monorepo 前端应用
│   ├── platform/           # 平台前端：登录 + 控制台（Vue3 + TS + Pinia + Element Plus）
│   │   ├── package.json / vite.config.ts / tsconfig.json
│   │   ├── index.html / public/
│   │   └── src/            # main.ts / api.ts / router / stores / views
│   └── video/              # 视频子系统前端（新增子系统按同名范式建立）
│       ├── package.json / vite.config.ts / tsconfig.json
│       ├── index.html / public/
│       └── src/            # App.vue / PlayerPage.vue / components / composables / ui
├── packages/
│   └── shared/             # 跨应用 TS 类型与常量
├── package.json            # ★ workspace 根脚本
├── pnpm-workspace.yaml
├── turbo.json
├── tsconfig.base.json
└── pnpm-lock.yaml
├── setup.py                # ★ 新电脑一键安装程序（幂等，可重复运行）
├── install.bat             # Windows 双击入口
└── design/                 # 平台架构与迁移设计文档
```

后端统一用 `backend/config.py` 与 `backend/requirements.txt`；前端由根 `package.json` + `pnpm-workspace.yaml` + `turbo.json` 统一管理，每个应用只声明自身依赖与 `vite.config.ts`。新增子系统时在 `apps/` 下建应用、在 `backend/app.py` 挂载子应用即可。

URL 分区：`/` 平台前端，`/api/auth/*` 平台登录，`/api/system/*` 平台基座；`/video/` 视频子系统前端，`/video/api/*` 视频子系统接口。两套前端共享同一签名会话与 `users` 表。

## 新电脑一键安装（Windows，推荐）

把项目放到任意目录（路径建议不含空格），在**项目根目录**执行一条命令即可，不用再手工建库、改配置、插账号、装依赖、构建前端。

### 前置条件（系统级软件，只装一次）

| 软件 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | 安装时勾选 `Add python.exe to PATH`，并确保带 pip / venv |
| Node.js | 18+ | 自带 npm |
| MySQL | 8.0+ | 服务已启动，且知道 root 密码 |
| ffmpeg / ffprobe | 可选 | 缺了也能跑，只是不抽封面、播放页不做编码探测 |

安装程序不代装系统级运行时。空机器可用 winget 一次补齐（MySQL 还需在 Installer 里完成初始化并记住 root 密码）：

```powershell
winget install Python.Python.3.13 OpenJS.NodeJS.LTS Gyan.FFmpeg
```

### 一条命令

```powershell
# 方式一：双击 install.bat
# 方式二：命令行（首次只问一次 MySQL root 密码）
py setup.py
```

想连密码都不输入，直接用参数（完全免交互的推荐写法）：

```powershell
py setup.py --mysql-password 你的MySQL密码 --admin-password 你的强密码 --with-ffmpeg
```

### 自动完成的步骤（对应脚本里的 `[1/8]` ~ `[8/8]`）

| # | 动作 | 重复运行时的行为 |
|---|---|---|
| 准备 | 创建 `backend/video/venv` 并按 `backend/requirements.txt` 安装依赖，然后切换到该解释器 | 已有则只做依赖校验 |
| 1 | 检查 Python / Node / MySQL 端口 | 只读检查 |
| 2 | 校验 MySQL 认证，由 `config.example.py` 生成 `backend/config.py`（填数据库密码 + 随机 64 位 SECRET_KEY） | **已存在则保留**，只补齐过弱的 SECRET_KEY；`MEDIA_ROOTS` 等自定义项不动 |
| 3 | 执行 `schema.sql` 建库建表（优先 mysql 客户端，找不到就用 PyMySQL 逐句执行） | `CREATE TABLE IF NOT EXISTS` + 幂等补列，存量数据不动 |
| 4 | 补建超管 `admin`（`schema.sql` 不含种子账号，这是最容易漏的一步） | 已存在则跳过，**不覆盖密码、不改动角色** |
| 5 | 在项目根目录执行 `pnpm install` + `pnpm build`，由 turbo 一次产出两个前端 | 依赖齐全则跳过安装 |
| 6 | 检查 ffmpeg，`--with-ffmpeg` 时用 winget 自动安装 | 已装则跳过 |
| 7 | 创建 `backend/video/uploads`、`backend/video/thumbs` 运行目录 | 已存在则跳过 |
| 8 | Flask `test_client` 冒烟验收：首页、SPA 回退、静态资源、接口、登录态 | **不启动也不重启任何服务**，不占用 5000 / 9000 端口 |

任一步失败都不会留下半吊子状态：按报错修好（多半是 MySQL 密码或服务没起），重跑一次即可。

### 装完之后

```powershell
# 在项目根目录运行唯一外层入口（backend/app.py）
backend\video\venv\Scripts\python backend\app.py
```

打开 `http://127.0.0.1:5000/` 进入平台登录；登录后从控制台打开 `http://127.0.0.1:5000/video/` 进入视频子系统。开发态在项目根目录执行 `pnpm dev:platform`（平台 9000）或 `pnpm dev:video`（视频 9001）。**立即改密**：默认超管 `admin / admin123`；`backend/config.py` 里 `REGISTRATION_ENABLED` 默认 `True`（开放注册），按需关闭。

局域网长期运行：

```powershell
cd backend
video\venv\Scripts\python -m waitress --host=0.0.0.0 --port=5000 app:application
```

### 参数与排错

| 参数 | 说明 |
|---|---|
| `--mysql-host / --mysql-port / --mysql-user` | 非默认连接（默认 `127.0.0.1 / 3306 / root`） |
| `--mysql-password` | 不填时依次读 `MYSQL_PWD` 环境变量、已有 `config.py`，最后才交互询问 |
| `--admin-password` | 首次创建超管时用的密码，建议一并设强密码 |
| `--with-ffmpeg` | 缺 ffmpeg 时用 winget 安装（需联网；装完重开终端并重启后端才生效） |
| `--skip-frontend` / `--no-verify` | 排错时跳过前端步骤 / 跳过冒烟验收 |

- **MySQL 连不上**：先确认服务已启动、`mysql -u root -p` 能进，再带 `--mysql-password` 重跑。
- **已有 config.py 但换了数据库密码**：带 `--mysql-password 新密码` 重跑，只更新密码行，其他配置保留。
- **pnpm 装不动**：删掉根目录 `node_modules` 后重跑 `pnpm install --force`；不要再用 npm 在 `apps/` 下单独安装。
- **锁文件唯一**：仓库只保留根目录 `pnpm-lock.yaml`，由 pnpm workspace 统一管理；不再使用 `package-lock.json`。
- **不要用 PyCharm 内置服务器（63343）直接打开 `dist/index.html`**，前端路由与 `/api` 都由 Flask 5000 托管。

## 手动安装（分步，排错时用）

推荐用上面的一键安装；以下步骤仅供手动排错，命令为 Windows 风格。

### 1. 数据库

```powershell
# 全新安装 / 存量库升级：统一执行 schema.sql 即可
# （CREATE TABLE IF NOT EXISTS 安全幂等：仅补齐缺失的表/列并写入表与列中文注释，已有结构不受影响）
mysql -u root -p < backend\video\schema.sql
```

`schema.sql` **不含超管种子账号**（旧版 README 误写成「初始账号」）。纯手动安装可跑一次 `py setup.py --skip-frontend --no-verify` 只补数据库与账号。默认超管 `admin / admin123`，**上线后请立即改密**。

### 2. 配置

```powershell
copy backend\config.example.py backend\config.py
py -3 -c "import secrets; print(secrets.token_hex(32))"   # 生成 SECRET_KEY
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

**媒体目录白名单**：默认允许 `backend/video/uploads/`、系统检测到的外接硬盘挂载点（macOS `/Volumes/*`、Linux `/media`、`/mnt`、Windows 盘符）、`~/Movies`、`~/Downloads`、`~/Desktop`、`~/Documents`。所有视频路径必须落在这些根内、为允许的视频扩展名，且 `realpath` 解析后不越界（挡符号链接与 `..` 穿越）。写入、读取、删除、目录浏览共用这套校验。

### 3. 启动

```powershell
py -3 -m venv backend\video\venv
backend\video\venv\Scripts\python -m pip install -r backend\requirements.txt

# 生产态：一套配置构建全部前端（平台 + 视频子系统）
cd frontend && npm install && npm run build

# 启动唯一入口（回到项目根目录）
cd ..\
backend\video\venv\Scripts\python backend\app.py
```

生产态访问 `http://127.0.0.1:5000/`（平台登录），视频子系统在 `/video/`；各前端路由自动回退到各自的 `index.html`。开发态在项目根目录执行 `pnpm dev:platform` 或 `pnpm dev:video`，依赖与构建由 workspace 统一管理。

**长期运行 / 局域网访问**：Flask 内置服务器只适合开发调试，`DEBUG` 已默认关闭。生产或多人访问请用 waitress（已列入 `backend/requirements.txt`），并把 `HOST` 改为 `0.0.0.0`：

```powershell
cd backend
video\venv\Scripts\python -m waitress --host=0.0.0.0 --port=5000 app:application
```

此时本机路径浏览、播放与删除仍受媒体目录白名单约束；请同时确认 `SECRET_KEY` 已随机化、`REGISTRATION_ENABLED` 符合预期。

**接口性能 / 数据库连接**：`backend/video/db.py` 在单个 HTTP 请求内复用同一条连接（挂在 `flask.g`，请求结束由 `teardown_appcontext` 归还），请求之间再用一个上限 8 条的轻量连接池，避免每条 SQL 都重新做 TCP 握手与 MySQL 认证 —— PyMySQL 的纯 Python 握手约 20ms，在 PyCharm 调试器下可放大到 100ms，一个视频列表请求原先要建 8 次连接。`get_conn()` 仍返回独立连接给显式事务（新增 / 编辑 / 批量导入），事务语义不变。若接口仍慢，优先用非调试模式或 waitress 启动；修改 `db.py` / `app.py` 后需**重启后端进程**才生效（`DEBUG=False` 不启用自动重载）。

## 审核流程

1. 普通用户新增 / 批量导入 → `audit_status = 0` 待审核，**不进主影库**，导航「审核结果」可查看
2. 超管或审核员在 `/audit` 表格页通过 / 驳回；驳回必填理由，理由写入 `audit_reason` 并通知上传者
3. 通过后视频进入影库；归属者可设「允许所有用户观看」（未过审时该勾选置灰）
4. 被驳回的视频由本人编辑保存 → 自动重回待审核、清空理由；**已通过的视频一旦更换源文件或字幕，也会重新送审并收回公开**（防止过审后换片绕过审核）
5. 管理员自己上传的视频免审通过，但会留下一条 `auto_approve` 留痕
6. 所有动作写入 `video_audit_logs`（只追加），审核中心「审核记录」页签可查全局流水，每行可展开单视频时间线

角色：`user` 普通用户 / `manager` 管理员（可查看并审核平级及以下用户的视频：管理员、审核员、普通用户）/ `reviewer` 审核员（可审核、查看全部视频，不能编辑删除他人内容）/ `admin` 超级管理员（全部权限 + 站点管理）。普通用户只能看自己上传的视频和已过审且设为公开的视频。

## 存储与路径

- 上传视频默认存 `backend/video/uploads/`（相对路径入库），也可在「选择保存文件夹」里选外接硬盘（绝对路径入库）
- **存储体检**（站点管理）：列出源文件丢失的记录与当前允许的媒体根目录，外接硬盘未挂载时一眼可见
- **批量路径重定位**：换硬盘 / 改盘符 / 换机器时，把 `filePath` 的旧前缀整体换成新前缀；支持先预览，且**只替换路径、不触发重新审核**
- 删除视频会同时清理数据库记录、白名单内的源文件与缩略图缓存，**不可恢复**
- 编码兼容：本地片源直接由浏览器播放，MKV / HEVC 等浏览器不支持的编码会在播放页给出明确原因与转码建议（需本机安装 ffprobe）

## 明暗主题

平台主题由 `apps/platform/src/stores/theme.ts` 控制，视频子系统主题由 `apps/video/src/stores/theme.ts` 控制；两者都只切换 `<html data-theme>`（`dark` / `light`），偏好存 `localStorage: nf-theme`，**不自动跟随系统**。`apps/video/src/composables/useTheme.ts` 仅为兼容旧调用方式的薄封装。色板与全部浅色适配规则集中在 `apps/platform/src/theme.css`：

| 层 | 位置 | 作用 |
|---|---|---|
| `@theme` token | 文件开头 | `--color-nf-*`，供 `bg-nf-*` / `text-nf-*` 等 Tailwind 工具类引用 |
| `:root` + `html[data-theme='light']` | 变量层 | 背景 / 文字 / 边框 / 输入控件 / 状态语义色，两套主题各一套值 |
| `@layer components` | 手写组件类 | `.nf-btn` / `.nf-input` / `.chip-opt` 等，统一走变量 |
| **浅色适配补丁层** | 文件末尾 | 覆盖历史组件里写死的 `#fff` 文字、`#161619` 深底、`#333338` 边框，以及 `bg-white/x`、`border-white/x`、`bg-black/20` 等 Tailwind 半透明叠层 |

新增组件时请直接引用 `--nf-*` 变量（次级底 `--nf-bg-subtle`、分隔线 `--nf-divider`、hover 底 `--nf-bg-hover`、状态色 `--nf-danger-text` 等），**不要写死黑白值**；确需兼容旧组件时在补丁层按选择器补规则，不要散落到各 `.vue`。

**媒体区刻意保持深色**：Hero 大图、详情页头图、频道头图渐变、视频封面叠层 / 信息条 / 详情浮层、播放器黑底、封面占位渐变、模态遮罩。这些区域的文字用 `--nf-on-media-text`（两套主题恒为浅色），不能跟随 `--nf-text-primary` 变深，否则白底主题下会出现深字压深底。

修改视频子系统 `theme.css` 后需重新构建：在项目根目录执行 `pnpm build:video`（生产态由根入口托管到 `/video/`；Vite dev 会自动热更新）。平台前端样式在 `apps/platform/src/console-theme.css`，构建目录为 `apps/platform/dist`。

## 测试

```powershell
cd backend\video
venv\Scripts\python tests\test_core.py
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
| 标签 / 类型 | `GET /api/tags/visible`（标签栏展示视图：**后端按会话角色**返回，超管含未发布项与 `badge`，其他角色仅已发布）、`GET/POST /api/tags`（工作台管理视图）、`DELETE /api/tags/:id`、`GET/POST /api/types`、`DELETE /api/types/:id` |

## 迁移到其他电脑（含历史数据）

新电脑先按「新电脑一键安装」跑一次（建好空库、超管、配置与前端产物），再搬数据：

1. 旧机导出 `mysqldump -u root -p video_manager > video_manager.sql`；新机导入 `mysql -u root -p video_manager < video_manager.sql`。导入可在安装前或安装后做，安装程序幂等、不会清空已有数据
2. 拷贝 `backend/video/uploads/`、`backend/video/thumbs/`，以及外接硬盘上的视频目录
3. 绝对路径变了：用「站点管理 → 存储体检 → 批量路径重定位」整体替换前缀（只换路径，不触发重新审核）；新目录不在默认白名单时登记到 `MEDIA_ROOTS`
4. 想保留所有人的登录态，把旧机 `config.py` 的 `SECRET_KEY` 抄到新机；核对数据库密码后重跑 `py setup.py` 做一次验收
5. 视频编码探测与封面抽帧依赖 ffmpeg，新机缺了按一键安装章节补装
