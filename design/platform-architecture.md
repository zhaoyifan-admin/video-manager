# 中型管理平台总体设计（视频系统作为子系统）

> 状态：已确认总体方向 —— 沿用 Flask + PyMySQL；管理端采用 Element Plus + Tailwind 混合；P0 基座先行。
> 依据：对当前仓库 `video-manager` 实际代码的核查，而非通用模板。
> 核查基线：`backend/video/app.py`（应用工厂 + 静态托管 + 统一异常）、`backend/video/responses.py`（`code === 0` 契约）、`backend/video/auth.py`（单角色 + 角色层级 + 可见性 SQL）、`backend/video/schema.sql:218-239`（`users` 表）、`backend/video/routes/__init__.py`（12 个业务蓝图）、`apps/video/src/main.ts`（子系统路由与角色守卫）、`apps/video/src/api.ts`（前端响应拦截）。
> 目录约定：`backend/` 是主系统后端，`apps/` 是 pnpm monorepo 前端应用；视频子系统对应 `backend/video/` 与 `apps/video/`。

## 1. 结论与架构选择

**采用“模块化单体 + 子系统分区”，不采用微服务，不重写视频子系统。**

理由：
1. 现有数据访问层已做请求内连接复用与连接池（`backend/video/db.py`），单机/局域网部署模型成立；引入服务拆分会新增分布式事务、认证传递与部署成本，超出“中型系统”需要。
2. 视频子系统已有 12 个蓝图、审核留痕、路径白名单、ffmpeg 抽帧等完整能力（`backend/video/routes/__init__.py:7-10`、`backend/video/storage.py`、`backend/video/thumbnails.py`）；整体重写会破坏既有功能，违背最小改动原则。
3. 前端当前为手写组件 + Tailwind，适合营销式视频页，但 11 个管理模块需要大量表格/表单/树控件；建议仅对**管理端外壳**引入 Element Plus，视频页面保持原样。

**分层结构（目标态）：**

```
backend/                      # 主系统后端
├── app.py                    # 唯一外层入口（WSGI）：平台 + 子系统挂载
├── config.py                 # 全系统共用配置：DB / 会话 / 路径 / 运行策略
├── config.example.py         # 配置模板（安装脚本据此生成 config.py）
├── requirements.txt          # 全系统共用 Python 依赖
├── core/                     # 平台内核（避免遮蔽标准库 platform）
│   ├── security.py           # 登录态、@require_perm、@data_scope（P3 引入）
│   ├── rbac.py               # 权限集合加载 / 缓存 / 失效
│   ├── cache.py              # 本地 TTL 缓存（单进程）+ 版本号失效
│   ├── audit.py              # 操作 / 登录 / 异常日志写入（P3 引入）
│   ├── storage/              # 文件存储适配器（P4 引入）
│   └── modules/
│       ├── system/           # 用户/角色/菜单/部门/岗位/字典/参数/通知
│       ├── log/              # 操作/登录/异常日志查询（P3 引入）
│       └── file/             # 文件管理（P4 引入）
└── video/                    # 视频子系统后端（新增子系统按同名范式建立）
    └── app.py / db.py / auth.py / routes/ / schema.sql / tests/
apps/                         # pnpm monorepo 前端应用
├── platform/                 # 平台前端：统一登录 + 控制台
│   ├── package.json          # 仅声明自身运行时依赖
│   ├── vite.config.ts        # base '/'；dev 代理 /api 与 /video 到后端 5000
│   ├── tsconfig.json
│   ├── index.html / public/
│   └── src/                  # Vue3 + TS 全量源码（main/api/router/stores + .vue 均 lang="ts"）
└── video/                    # 视频子系统前端
    ├── package.json
    ├── vite.config.ts        # base '/video/'；dev 代理 /video/api 到后端
    ├── tsconfig.json
    ├── index.html / public/
    └── src/                  # 全量 TS；createWebHistory('/video/')，接口统一 /video/api
        ├── api.ts / types/    # 按后端真实响应标注返回类型
        ├── stores/            # Pinia：auth / theme / videos
        └── composables/       # 兼容旧调用的薄封装（useAuth/useTheme/useVideos/useCover/useTaxonomy）
packages/
└── shared/                   # 跨应用类型与常量：ApiResult / CurrentUser / MenuNode
turbo.json                    # build / typecheck / dev 任务编排
pnpm-workspace.yaml           # apps/* + packages/*
tsconfig.base.json            # 严格 TS 基线
```

**配置单一来源**：后端仍只有 `backend/config.py` + `backend/requirements.txt`。前端依赖与任务由根 `package.json` + `pnpm-workspace.yaml` + `turbo.json` 统一管理，各应用只声明自身依赖；不再有 `frontend/package.json` 与 `--mode` 分支。后端静态目录已同步为 `apps/platform/dist` 与 `apps/video/dist`，对外 URL 不变。新增子系统时：后端在 `backend/app.py` 挂载子应用，前端在 `apps/` 下新增应用并建立自己的 `vite.config.ts`。

**开发态子系统入口**：平台 Vite 开发服务（`pnpm dev:platform`）把 `/video` 代理到后端 `5000`，由 `DispatcherMiddleware` 返回视频子系统页面与接口；否则 Vite 会把 `apps/video/index.html` 当目录首页并返回错误入口。视频源码热更新用 `pnpm dev:video`（`localhost:9001`）；平台开发态点击入口展示 `apps/video/dist` 的已构建版本，改视频源码后需先 `pnpm build:video`。


**URL 分区**：平台对外是 `/api/auth/*`、`/api/system/*`；视频子系统对外统一加 `/video/api/*`（播放流、缩略图、字幕、上传等所有写死 URL 必须引用 `VIDEO_API_BASE`，不能写成 `/api/...`，否则请求会落到平台 SPA 而拿到 HTML）。视频 Flask 应用内部仍按原有 `/api/videos` 等蓝图注册，由 `DispatcherMiddleware` 去掉 `/video` 前缀后转发，现有测试无需改路径。

## 2. 数据模型（新增表，全部 `sys_` 前缀）

**保留 `users` 作为唯一账号主表**，在其上幂等补列，不另建 `sys_user` 造成双份身份数据。现有列 `id/username/password_hash/role/avatar/created_at` 全部保留；`role` 降级为“主角色快照”，用于兼容 `auth.py:is_super_admin` 与审核流程，写多角色时同步更新。

| 表 | 关键字段（新语义字段，不复用旧业务字段） | 说明 |
|---|---|---|
| `sys_user_profile` | `user_id`, `nick_name`, `phone`, `email`, `dept_id`, `status`, `pwd_updated_at`, `failed_attempts`, `locked_until`, `must_change_pwd` | 用户扩展信息；与 `users` 1:1 |
| `sys_dept` | `id`, `parent_id`, `ancestor_path`, `dept_name`, `leader_user_id`, `sort_no`, `status` | 树形组织；`ancestor_path` 形如 `/1/3/`，便于后代部门一次性 IN 查询 |
| `sys_post` | `id`, `post_code`, `post_name`, `sort_no`, `status` | 岗位与用户通过关联表多对多 |
| `sys_user_post` | `user_id`, `post_id` | 用户-岗位关联 |
| `sys_role` | `id`, `role_code`, `role_name`, `data_scope`, `sort_no`, `status`, `remark` | `data_scope`：`ALL/DEPT/DEPT_TREE/SELF/CUSTOM` |
| `sys_user_role` | `user_id`, `role_id` | 多角色分配 |
| `sys_menu` | `id`, `parent_id`, `menu_type`, `title`, `route_path`, `component_key`, `redirect_path`, `icon_key`, `permission_code`, `link_url`, `visible_flag`, `cache_flag`, `sort_no`, `status` | `menu_type`：`DIR/MENU/BUTTON`；`component_key` 是前端组件白名单 key，不存任意路径，避免后端下发可执行路径 |
| `sys_role_menu` | `role_id`, `menu_id` | 角色-菜单/按钮授权 |
| `sys_role_dept` | `role_id`, `dept_id` | `CUSTOM` 范围的部门集合 |
| `sys_data_rule` | `id`, `rule_name`, `resource_code`, `field_name`, `operator`, `value_expr`, `status` | 自定义数据规则；`field_name/operator` 必须走白名单，禁止拼接原始 SQL |
| `sys_dict_type` | `id`, `dict_code`, `dict_name`, `status` | 字典类型 |
| `sys_dict_item` | `id`, `dict_type_id`, `item_value`, `item_label`, `sort_no`, `status` | 字典项；缓存翻译用 `dict_code + item_value` 为 key |
| `sys_config` | `id`, `config_key`, `config_value`, `config_group`, `value_type`, `cache_flag`, `remark` | 参数配置；`config_key` 唯一 |
| `sys_notice` | `id`, `title`, `content_md`, `notice_type`, `publish_at`, `withdraw_at`, `publisher_id`, `status` | 通知公告；撤回标记不物理删除 |
| `sys_notice_receipt` | `notice_id`, `user_id`, `read_at` | 已读状态 |
| `sys_operate_log` | `id`, `operator_id`, `operator_snapshot`, `module_code`, `action_code`, `target_snapshot`, `request_path`, `success_flag`, `cost_ms`, `created_at` | 操作审计；密码等敏感字段脱敏 |
| `sys_login_log` | `id`, `account_snapshot`, `login_ip`, `result_flag`, `fail_reason`, `created_at` | 登录日志 |
| `sys_exception_log` | `id`, `request_path`, `exception_type`, `message_digest`, `created_at` | 异常日志；不落完整堆栈到前端响应 |
| `sys_file` | `id`, `file_name`, `storage_backend`, `storage_key`, `mime_type`, `byte_size`, `checksum`, `category_code`, `uploader_id`, `created_at` | 文件元数据；物理文件与记录解耦 |

**存量迁移**：`schema.sql` 沿用现有幂等范式（`CREATE TABLE IF NOT EXISTS` + `information_schema` 补列）。初始化时把 `users.role` 的四个值 seed 到 `sys_role`，并为每个存量用户写一条 `sys_user_role`；审计人员等既有语义由 `permission_code` 精确映射，不靠角色名字符串硬编码。

## 3. 权限与数据范围设计

### 3.1 功能权限（RBAC）

- 链路：登录 → `sys_user_role` → `sys_role_menu` → 权限码集合 → 前端动态路由 + `v-permission`。
- 后端在所有管理接口使用 `@require_perm('system:user:list')` 装饰器；接口内部不再散落 `if role == ...`。
- 权限集合缓存在进程内，TTL 60 秒；`sys_menu/sys_role_menu/sys_user_role` 变更时递增 `sys_config` 中的 `permission_version`，各进程按版本号失效。单机当前是多进程 waitress 部署时需注意：本地缓存不跨进程，后续可平滑替换为 Redis（接口不变）。
- **视频子系统过渡**：保留 `auth.py` 原有 `require_admin/require_auditor/visible_sql/manageable_sql`，先把它们改为读 RBAC 权限码，行为等价后再收敛；不在第 1 批同时改权限模型和审核流程。

### 3.2 数据范围

- `sys_role.data_scope` 决定 SQL 片段：
  - `ALL`：无额外条件；
  - `SELF`：`owner_field = 当前用户 ID`；
  - `DEPT`：`dept_id = 当前用户部门`；
  - `DEPT_TREE`：`dept_id IN (当前部门及后代)`，用 `ancestor_path` 前缀匹配；
  - `CUSTOM`：`sys_role_dept` 限定部门集合 + `sys_data_rule` 附加条件。
- 封装为 `@data_scope(resource_code, owner_field='user_id', dept_field='dept_id')`，向视图注入 `scope_sql` / `scope_params`，由现有 `db.query()` 参数化拼接，禁止字符串插值用户输入。
- **视频特例必须保留**：当前 `auth.py:visible_sql` 中普通用户可见“本人视频 OR 已过审公开视频”，这不是标准数据范围，先作为 `video_public_visibility` 策略独立保留；迁移时与 `data_scope` 取 OR 关系，避免上线后用户突然看不到已公开视频。

## 4. 模块与接口清单（分批）

| 批次 | 模块 | 关键接口（均遵循 `{code,msg,data}` / `code === 0`） | 完成判据 |
|---|---|---|---|
| **P0 基座** | 应用结构、登录态、动态路由、权限缓存、审计基建 | `GET /api/system/menus`（当前用户菜单树）、`GET /api/system/permissions`、`GET /api/auth/me`（扩展返回 roles/permissions） | 视频子系统全部原功能回归通过；管理端空外壳可登录、菜单来自后端 |
| **P1 组织与权限**（已交付） | 用户、角色、菜单、部门、岗位（需求 1-5） | `GET/POST/PUT/DELETE /api/system/users`；`POST /api/system/users/import`、`GET /api/system/users/export`、`GET /api/system/users/template`；`/roles`（含 `/<id>/menus`、`/<id>/depts` 授权）、`/menus`、`/departments`、`/posts` 同构 CRUD；`GET /api/system/options`、`GET /api/system/security-policy` | 多角色分配生效且同步 `users.role` 主角色快照；菜单/按钮权限对同一账号在不同角色下表现一致；Excel 导入有错误行报告且事务回滚 |
| **P2 基础设施**（已交付） | 字典、参数、通知公告（需求 6-8） | `/dict-types`、`/dict-items`、`/dict/options`、`/dict/refresh`、`/configs`（含 `/groups`、`/values`、`/refresh`）、`/notices`（含 `/publish`、`/withdraw`、`/mine`、`/unread-count`、`/<id>/read`） | 字典翻译有缓存且改后能刷新；公告已读统计与撤回在所有接收端一致 |
| **P3 审计与数据权限**（已交付） | 操作/登录/异常日志、数据范围（需求 9-10） | `GET /api/logs/operations`、`/logs/logins`、`/logs/exceptions`（支持 `moduleCode`/`requestPath`/`account`/`exceptionType` 筛选）；管理接口接 `@data_scope` | 敏感字段（密码/令牌）递归脱敏后落库；三个角色分别用 SELF/DEPT_TREE/ALL 范围查询得到预期行数；视频公开可见规则未被破坏 |
| **视频运营管理迁移**（已交付） | 视频审核、站点管理、标签/类型/合集管理从子系统搬到平台控制台；账号角色统一到 P1 用户管理 | `/api/video-admin/audit/*`、`/api/video-admin/taxonomy/*`、`/api/video-admin/admin/*` 共 15 条（站点侧用户管理 3 条已移除）；页面 `/console/video-mgmt/{audit,taxonomy,site}` | 视频侧入口与 26 条管理接口已移除；平台三个页面用 Element Plus + `tvue-crud`；账号角色唯一写入口为 `/api/system/users`（sync_user_roles 同步快照）；24 项回归测试通过，视频日常浏览/上传/播放/审核结果不受影响 |
| **P4 文件管理** | 多存储后端（需求 11） | `/files`（上传/列表/分类/删除）、`/files/{id}/preview`；`POST /api/system/settings/storage` | 本地后端可用；切换后端不改调用方接口；预览有 MIME 白名单与越界校验 |

**密码安全策略（P1，已实现）**：沿用 `werkzeug.security.generate_password_hash/check_password_hash`（`backend/video/auth.py:12-19`），不自行实现哈希；最小长度、字母+数字复杂度、历史不可复用（`sys_password_history`）、连续失败锁定、90 天过期提醒，策略值来自 `sys_config.security.*`，改配置即生效。实现位于 `backend/core/modules/system/support.py` 的 `pwd_policy()` / `validate_password()`。

**P1 落地要点**：
- 后端子模块在 `backend/core/modules/system/{users,roles,menus,departments,posts,support}.py`，共用 `/api/system` 前缀，业务接口统一 `@require_login` + `@require_perm`。
- 多表写入经 `support.TxConnection` 包装原生 PyMySQL 连接，提供 `execute/fetchone/fetchall/lastrowid` 的 cursor 语义，不改变 `db.get_conn()` 既有调用方式。
- 角色/菜单/按钮变更后 `bump_permission_version()` 递增 `sys_config.permission_version` 并清空进程缓存，动态路由与权限码即时刷新。
- 前端五个管理页位于 `apps/platform/src/views/system/*ManagePage.vue`，统一使用 `@zhaoyifannan/tvue` 的 `tvue-crud`；按钮级控制用 `v-permission` 指令。
- 菜单 `component_key` 由后端下发，必须在 `apps/platform/src/router/dynamic.ts` 的组件白名单内；P1 五个页面已写入 `schema.sql` 的幂等 UPDATE。

**菜单管理交互（参照 SoybeanAdmin，已改造）**：菜单列表用 `tvue-crud` 树形模式（`rowKey: 'id'`、`treeProps.children`、`defaultExpandAll`），层级直接来自后端 `children`。父级 ID 不再让用户填写：顶部「新增顶级菜单」注入 `parentId=0`，行内「新增子级」注入当前行 `id`，表单里父级只显示面包屑标签且编辑时不可改。表单按类型动态显示字段（目录 / 菜单 / 按钮），组件标识从后端 `componentWhitelist` 下拉选择而非手输；编辑时类型禁用。后端 `_check_parent()` 校验父级存在、类型层级（目录父级只能是目录或 0、菜单父级只能是目录、按钮父级只能是菜单）并沿父链向上防环，取代原来只挡直接自指的判断。另修复 `_validate()` 返回键误写为 `code` 导致 INSERT/UPDATE 报 `Unknown column 'code'` 的缺陷——正确字段名为 `menu_code`。

**Excel 导入导出（P1）**：新增 `openpyxl` 依赖；先下载模板，导入按行校验（用户名唯一、部门/岗位编码存在、角色存在），单事务写入，失败时返回行号 + 原因；导出沿用当前筛选条件而非全表偷跑。

**P2 落地要点**：
- 后端子模块位于 `backend/core/modules/system/{dictionaries,configs,notices}.py`，共用 `/api/system` 前缀，全部 `@require_login` + `@require_perm`。
- 字典：类型 / 项 CRUD，`/dict/options` 以 `sys_config.dict_version` 作为缓存 key 的一部分；字典变更与 `/dict/refresh` 同时递增版本号并清本进程缓存。
- 参数：`value_type` 限定 string / number / bool / json；`permission_version`、`dict_version`、`config_version` 为内核版本号，接口只读不改；`/configs/values` 按分组读缓存值，`/configs/refresh` 递增 `config_version` 并清理权限/菜单缓存。
- 通知：状态 `DRAFT/SCHEDULED/PUBLISHED/WITHDRAWN`，可见性由状态 + `publish_at` + `withdraw_at` 共同判定；已读以 `sys_notice_receipt` 是否存在为准，撤回不清空回执。
- 前端页面位于 `apps/platform/src/views/system/{DictManagePage,ConfigManagePage,NoticeManagePage,NoticeCenterPage}.vue`，表格统一 `tvue-crud`；顶栏通知角标由 `stores/notices.ts` 统一维护。

**通知定时（P2）**：采用惰性发布——列表 / 未读数 / 已读等读取入口先执行条件更新 `status='SCHEDULED' AND publish_at <= NOW() → PUBLISHED`。该 SQL 幂等，单进程与多进程均只生效一次，无需后台线程或消息中间件；放弃原计划的调度线程，避免 WSGI 多进程下重复发布与进程生命周期问题。

**审计与数据范围（P3）**：
- 写入侧 `backend/core/audit.py` 统一负责脱敏：`mask_payload()` 递归清洗 dict/list，命中密码/令牌/密钥类 key 置为 `***`；`record_operate/record_login/record_exception` 内部吞异常，审计失败绝不影响主流程。平台 `app.py` 用 `before_request`/`after_request` 对所有 `/api/` 写操作统一埋点；平台与视频共用的登录路由在成功/失败两路均写登录日志；非 HTTPException 异常在 errorhandler 记类型与摘要（不留完整堆栈）。
- 数据范围由 `scope_clause(user, owner_field, table_alias)` 生成参数化 SQL 片段与参数列表，`@data_scope` 注入 `g.scope_sql`/`g.scope_params`。多角色取最宽范围：`ALL > DEPT_TREE > DEPT/CUSTOM > SELF`；`DEPT_TREE` 用 `sys_dept.ancestor_path LIKE` 前缀匹配后代，未分配部门时一律退化为仅本人，避免越权放大。日志三个接口按 `operator_id`/`user_id` 施加范围。
- 视频子系统公开可见规则仍由 `auth.py:visible_sql` 独立维护（普通用户「本人 OR 已过审公开」，管理员/审核员策略不变），不接入 `@data_scope`，避免上线后用户突然看不到已公开视频。

**视频运营管理迁移（已交付）**：
- 后端：主系统新增 `backend/core/modules/video/{taxonomy,audit,admin}.py`，统一挂 `/api/video-admin`，共 18 条路由，由 `backend/app.py` 直接注册；权限改用 RBAC 码（`video:audit:*` / `video:taxonomy:*` / `video:admin:*`），不再复用视频侧 `require_admin` / `require_auditor`。业务 SQL 与留痕仍落原有 `video_audit_logs` / `tag_audit_logs` / `admin_audit_logs` 等表，视频侧读接口可见同一状态。
- 视频侧收敛：`apps/video` 删除 `AuditCenterPage.vue`、`AdminPage.vue`、`ManageModal.vue`、`useTaxonomy.ts`，移除 `/audit`、`/admin` 路由与顶部入口；`api.ts` 删除 28 个已搬移管理函数。后端删除 `routes/audit_logs.py`、`routes/admin_logs.py`，并从 tags/types/collections/videos/auth/extra 中移除 26 条管理路由。保留普通用户提交标签/类型、查看自己审核结果与通知等日常接口。
- 前端：控制台新增 `/console/video-mgmt/{audit,taxonomy,site}` 三个页面，统一 Element Plus + `@zhaoyifannan/tvue`；菜单 `component_key` 为 `VideoAuditPage` / `TaxonomyManagePage` / `VideoSiteManagePage`，已写入 `schema.sql` 与 `router/dynamic.ts` 白名单。
- 接口防护：两个 Flask 入口的 SPA fallback 对未注册的 `/api/*` 返回 JSON 404，避免误调已移除管理接口时拿到 HTML 200。
- 回归：`backend/video/tests/test_core.py` 增加管理接口路径映射层，24/24 通过；`pnpm typecheck` 3/3、`pnpm build` 3/3 通过；主入口 9 个 video-admin GET 接口均以 admin 身份返回 `code=0`，三个菜单组件键正确下发。
- 迁移后故障修复：`apps/video/vite.config.ts` dev 代理曾遗留 `rewrite` 去掉 `/video`，导致 `/video/api/*` 打到平台 `/api/*` 全部 404，已删除 rewrite 原样转发；`apps/platform/vite.config.ts` preview 代理补 `/api`。另：改动 `backend/app.py` 蓝图注册或 fallback 后必须重启 Flask 进程（Vite 自动 reload，Flask 不会）。

**账号与角色单一来源（已交付）**：账号与角色只在平台 P1 用户管理（`/console/system/user`、`/api/system/users`）维护。其写入统一经 `support.sync_user_roles()`，在同一事务重建 `sys_user_role` 并同步 `users.role` 主角色快照；视频侧 `auth.py` 的 `visible_sql` / `can_audit` / `role_level` 继续读该快照，保持独立公开可见规则不变。站点管理的「用户与角色」Tab 与 `/api/video-admin/admin/users` 三个接口（列表/建账号/改角色）已移除——它们此前绕过 `sys_user_role` 只写快照，是权限不一致的根源；`video:admin:manage` 权限码保留给存储路径重定位。站点页保留数据看板、存储体检与路径重定位、操作审计。验证：P1 改角色为 `user+reviewer` 后 `sys_user_role` 两条关联、`users.role=reviewer`、视频侧 `can_audit=True`。

## 5. 前端设计要点

1. **外壳与子系统分区**：新增 `layout/` 后台外壳；视频页仍走现有 `App.vue/PlayerPage.vue`，以菜单形式嵌入，不强行改成管理表格风格。
2. **动态路由**：后端下发 `sys_menu` 树 → `component_key` 映射本地组件表 → `router.addRoute`；`cache_flag=true` 的页面包 `<keep-alive>`；`link_url` 类型菜单新标签打开；`visible_flag=false` 不下发。
3. **权限指令**：`v-permission="'system:user:create'"` 控制按钮；路由守卫按权限码而非角色名判断，消除 `apps/video/src/main.ts` 中遗留的硬编码。
4. **UI 库决策（已确认）**：管理端采用 **Element Plus + Tailwind 混合**，视频页保持原样。Element Plus 负责表格、表单、树、菜单等复杂控件，Tailwind 负责布局与间距；两者共用 `console-theme.css` 映射既有 `nf-*` 色板，避免第二套配色。P0 已按此方案落地。

## 6. 风险与规避

1. **权限回归风险**：现有审核逻辑与角色层级深度绑定；P0/P1 只做“等价替换 + 回归测试”，不顺便改业务规则。
2. **多角色与单角色快照不一致**：写 `sys_user_role` 时在同一事务内更新 `users.role` 主角色；主角色取优先级 `admin > manager/reviewer > user`。
3. **数据范围误伤**：视频公开可见、审核员看全部视频等既有规则先原样保留，新增范围条件只做交集/并集的显式组合，配单元测试覆盖四角色。
4. **本地权限缓存跨进程不一致**：明确单进程语义，保留替换 Redis 的接口；权限变更后提供“刷新缓存”管理动作兜底。
5. **文件安全**：所有预览/下载走 `storage_key` 白名单解析，拒绝 `..` 与绝对路径穿越；延续 `backend/storage.py` 的路径校验思路。

## 7. 分步执行与确认点

| 步骤 | 交付物 | 需用户确认 |
|---|---|---|
| ① 总体设计（本文档） | 架构、数据模型、分批路线 | 技术栈选型（Element Plus / 手写）、批次顺序 |
| ② P0 基座 | 目录骨架、动态路由、权限入口、菜单 seed | 后台外壳视觉方向、菜单初始结构 |
| ③ P1 组织与权限 | 8 类 CRUD + Excel + RBAC 页面 | 字段口径、按钮权限码命名 |
| ④ P2 基础设施（已交付） | 字典/参数/通知的管理页与接口 | 缓存刷新、发布撤回、已读角标 |
| ⑤ P3 审计与数据权限（已交付） | 三类日志表与审计埋点、数据范围内核、日志查询页 | 脱敏字段清单、角色数据范围口径 |
| ⑥ 视频运营管理迁移（已交付） | 审核/站点/分类管理搬到控制台，视频侧移除入口 | 完整搬移、Element Plus + tvue、移除视频侧入口 |
| ⑦ P4 文件管理 | 文件库与多存储后端 | 存储后端选型、MIME 白名单 |

**设计原则贯穿全程**：响应契约 `code === 0` 不变；`users/videos` 等现有表不删不改语义；新文件使用新语义字段；每次只改结构或只改一层权限，不跨层一次性重写。
