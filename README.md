# 视频管理系统

技术栈：Python (Flask + PyMySQL) + Vue3（纯手写组件，无 UI 框架）+ MySQL

## 功能

- 视频增删查改（标题、文件路径、备注），支持关键词搜索与分页
- 多标签：一个视频可挂多个标签；标签可独立管理；可按标签筛选
- 本地部署：MySQL 与 Flask 都跑在本机，迁移到其他电脑只需按下方步骤重装环境并导入数据库

## 目录结构

```
video-manager/
├── backend/                # Flask 后端（PyCharm 中运行 app.py）
│   ├── app.py              # 应用入口：create_app / 前端托管 / 全局错误处理
│   ├── config.py           # MySQL 连接 + 路径/ffmpeg 配置（★ 先改这里的密码）
│   ├── db.py               # 数据库访问层
│   ├── responses.py        # 统一响应 {code, msg, data}
│   ├── storage.py          # 文件路径工具（文件名清洗 / 路径解析 / 物理删除）
│   ├── thumbnails.py       # ffmpeg 缩略图（生成 / 并发锁 / 缓存清理）
│   ├── routes/             # 路由蓝图
│   │   ├── tags.py         # /api/tags
│   │   ├── types.py        # /api/types
│   │   ├── videos.py       # /api/videos（列表/详情/增删改/收藏/批量导入）
│   │   ├── media.py        # /api/videos（上传/播放流/缩略图）
│   │   └── paths.py        # /api/paths（磁盘/目录浏览/新建文件夹）
│   ├── schema.sql          # 建库脚本
│   └── requirements.txt
└── frontend/               # Vue3 前端（npm run dev 启动）
    ├── vite.config.js      # /api 代理到后端 5000 端口
    └── src/
        ├── main.js
        ├── api.js          # 接口封装（契约：{code, msg, data}，code===0 成功）
        ├── theme.css       # 全局主题（Netflix 风格）
        ├── composables/    # 组合式函数（useVideos / useCover）
        ├── components/     # 页面组件（导航/Hero/卡片/分页/各弹窗）
        ├── ui/             # 通用 UI（Toast / 确认框 / NfModal）
        └── App.vue         # 列表页组装层
```

## 首次部署步骤

### 1. 初始化数据库

全新安装执行建库脚本（含 users 用户表、videos 挂 user_id）：

```bash
/usr/local/mysql/bin/mysql -u root -p < backend/schema.sql
```

**已有存量数据的库**（升级到多用户版）执行迁移脚本，自动建表、加列，并把现有视频归入默认管理员 `admin / admin123`：

```bash
cd backend && ./venv/bin/python migrate_users.py
```

### 2. 配置数据库密码

真实配置 `backend/config.py` 不入 Git（含密码，已被 .gitignore 排除）。从模板复制后按本机实际填写：

```bash
cp backend/config.example.py backend/config.py
# 然后编辑 config.py：改 password，并更换 SECRET_KEY 为随机字符串
```

### 3. 启动后端（PyCharm）

1. 用 PyCharm 打开 `video-manager` 目录（或 `backend` 目录）
2. 新建 Python 解释器（venv），安装依赖：
   ```bash
   pip3 install -r backend/requirements.txt
   ```

3. 运行 `backend/app.py`，默认监听 `http://127.0.0.1:5000`

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173` 即可（开发态由 vite 把 `/api` 代理到后端 5000 端口）。

## 打包与生产部署

```bash
cd frontend
npm run build
```

打包产物在 `frontend/dist/`。**Flask 会自动托管 dist**（检测到该目录即生效），直接访问 `http://127.0.0.1:5000` 即可使用，无需 Nginx 或其他静态服务器：

- `/` 返回 `index.html`，`/play/:id`、`/detail/:id` 等前端路由自动回退到 `index.html`
- 所有业务接口仍在 `/api` 下，前后端同源，开发态的代理在生产态不再需要
- 注意：不要用 PyCharm 内置服务器（63343 端口）直接打开 `dist/index.html`——它无法正确返回静态资源，会导致样式 MIME 类型报错

## 迁移到其他电脑

1. 两台电脑都装好 Python 3.10+、Node 18+、MySQL 8
2. 新电脑执行 `schema.sql` 建库
3. 旧电脑导出数据（可选）：
   ```bash
   /usr/local/mysql/bin/mysqldump -u root -p video_manager > video_manager.sql
   ```
4. 新电脑导入数据：
   ```bash
   mysql -u root -p video_manager < video_manager.sql
   ```
5. 修改新电脑的 `config.py` 密码，重复步骤 3、4 启动前后端

## API 一览

所有 `/api` 接口（除 `/api/auth/*`）均要求登录（Flask session cookie），未登录返回 401。

### 认证

| 方法 | 接口 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册 `{username, password}`，成功即登录 |
| POST | `/api/auth/login` | 登录 `{username, password}` |
| POST | `/api/auth/logout` | 退出登录 |
| GET  | `/api/auth/me` | 当前登录用户 |

超级管理员（`users.role = 'admin'`，即 admin 账号）额外能力：查看所有用户的视频、编辑/删除任何视频、把任何视频设为公开。`is_public = 1` 的视频对所有用户可见可播放；普通用户编辑/删除仅限本人视频。

### 视频（全部按用户隔离：只能看到 / 操作自己的数据）

| 方法     | 路径                                            | 说明                                            |
| ------ | --------------------------------------------- | --------------------------------------------- |
| GET    | `/api/videos?keyword=&tagId=&page=&pageSize=` | 视频列表（搜索 / 标签筛选 / 分页）                          |
| GET    | `/api/videos/:id` | 单个视频详情（独立播放页 `/play/:id` 使用） |
| POST   | `/api/videos`                                 | 新增视频 `{title, filePath, tags[], description, typeId}` |
| PUT    | `/api/videos/:id`                             | 修改视频（全量更新，标签整体替换）                             |
| POST   | `/api/videos/upload` | 上传视频文件（multipart，可选 `saveDir` 自定义保存目录 / `fileName` 自定义保存文件名；未指定时存入 `backend/uploads/`，返回相对路径 + 原始文件名） |
| GET    | `/api/paths/drives` | 枚举本机磁盘与外接硬盘挂载点（macOS `/Volumes`、Windows 盘符、Linux `/media` 等），返回 `{path, name, free, total}` |
| GET    | `/api/paths/list?dir=` | 浏览目录下的子文件夹（dir 为空时返回磁盘列表）；用于「选择保存文件夹」 |
| POST   | `/api/paths/mkdir` | 新建文件夹 `{parent, name}`（保存路径不存在时自定义创建） |
| POST   | `/api/videos/batch` | 批量导入 `{items: [{title?, filePath, tags?, typeName?, description?}]}`，单条失败不影响其余，返回 `{success, failed[]}` |
| GET    | `/api/videos/:id/file` | 流式播放本地视频文件（支持 Range，兼容绝对路径与上传的相对路径） |
| GET    | `/api/videos/:id/thumb` | 视频缩略图（本地文件用 ffmpeg 现场生成并缓存到 `backend/thumbs/`，未装 ffmpeg 返回 404） |
| POST   | `/api/videos/:id/favorite` | 切换收藏状态，返回 `{isFavorite}` |
| DELETE | `/api/videos/:id`                             | 删除视频（**数据库记录 + 磁盘源文件 + 缩略图缓存一并物理删除**，返回 `{fileDeleted}` 表示源文件是否实际删除） |
| GET    | `/api/tags`                                   | 标签列表                                          |
| POST   | `/api/tags`                                   | 新增标签 `{name}`（已存在则幂等返回）                       |
| DELETE | `/api/tags/:id`

## 视频文件存储说明

- 通过「选择文件并上传」入库的视频存放在 `backend/uploads/`，数据库保存相对路径（如 `uploads/电影.mp4`），播放接口自动解析
- **自定义保存路径**：上传时可点「选择保存文件夹」浏览外接机械硬盘 / 固态硬盘的已有文件夹（磁盘列表会显示剩余空间），文件夹不存在可直接输入名称新建；指定目录后文件保存为绝对路径入库，播放与删除同样生效
- 手动填写的本机绝对路径、http(s) 播放链接同样支持
- **删除即物理删除**：删除视频时会同时删除数据库记录、磁盘上的视频源文件与缩略图缓存，不可恢复（前端确认框会明确提示）；仅删除单个文件，绝不递归删目录；播放链接（http(s)）没有本地源文件，删除时只清理记录
- 迁移电脑时把 `uploads/` 目录一并拷贝，上传的视频即可继续播放
- **播放链接直跳**：播放页自动识别链接类型——`.mp4/.webm` 等直链视频文件内嵌播放；其他网页地址显示「打开播放链接」按钮，点击新标签页直达
- 迁移电脑时把 `uploads/` 目录一并拷贝，上传的视频即可继续播放

## 批量导入说明

- 工具栏「批量导入」：每行一条视频，字段用 `|` 分隔：`标题 | 文件路径或播放链接 | 标签1,标签2 | 类型 | 备注`
- 仅「文件路径」必填；标题缺省自动取文件名；标签/类型不存在时自动创建
- 单次最多 500 条，单条失败不影响其余，导入后汇报成功/失败明细

## 视频封面缩略图说明

- 建议安装 ffmpeg（`brew install ffmpeg`）：安装后访问缩略图接口会自动用 ffmpeg 从视频约 10% 进度处抽帧，生成 640px 宽 JPEG 缓存到 `backend/thumbs/{视频id}.jpg`，之后直接读文件，刷新页面也秒开
- 同一视频并发请求只生成一次（进程内加锁）；未安装 ffmpeg 时接口返回 404，前端自动回退为浏览器端截帧，功能不受影响
- 外链（http(s)）视频无法由后端抽帧，始终使用前端截帧
- 迁移电脑时 `thumbs/` 目录可一并拷贝（不拷贝则首次访问时自动重新生成）
