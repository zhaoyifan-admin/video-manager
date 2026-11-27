"""中型管理系统唯一外层入口（WSGI）。

目录约定：backend/ 为主系统后端，各子系统后端作为其子目录（如 backend/video/）；
apps/ 为 pnpm monorepo 前端应用，各子系统前端作为其子应用（如 apps/video/）。

URL 分区：
  /                 平台前端（登录 / 管理控制台）
  /api/auth/*       平台登录态（与子系统共享 users 表与会话）
  /api/system/*     平台基座接口（菜单 / 权限）
  /video/           视频子系统前端
  /video/api/*      视频子系统接口

实现：主 Flask 应用负责平台；子系统作为独立 Flask 应用通过
DispatcherMiddleware 挂载到各自路径前缀。新增子系统时在 backend/ 与
apps/ 下各建一个同名应用，并在此处按同样方式挂载即可。
"""
import importlib.util
import os
import sys
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.dispatcher import DispatcherMiddleware

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
VIDEO_BACKEND_DIR = os.path.join(BACKEND_DIR, "video")
PLATFORM_DIST = os.path.join(PROJECT_ROOT, "apps", "platform", "dist")

# 平台内核在 backend/core；子系统内部仍使用 import db / import config 的写法。
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(1, VIDEO_BACKEND_DIR)

import config  # noqa: E402
import db  # noqa: E402
from core import audit  # noqa: E402
from core.modules.system import bp as system_bp  # noqa: E402
from core.modules.log import bp as log_bp  # noqa: E402
from core.modules.video import bp as video_admin_bp  # noqa: E402
from routes import auth_bp  # noqa: E402


def _audit_route(request):
    """把写请求映射为 (module_code, action_code)，仅审计平台 API。"""
    path = request.path
    method = request.method
    if not path.startswith("/api/"):
        return "", ""
    # /api/auth/login → auth:login；/api/system/users → system:user
    parts = [p for p in path[len("/api/"):].split("/") if p]
    if not parts:
        return "", ""
    module = parts[0]
    resource = parts[1] if len(parts) > 1 else ""
    # 只审计平台自身接口；日志查询是 GET，不会进入这里。
    if module not in ("auth", "system") and not path.startswith("/api/logs/"):
        return "", ""
    code = f"{module}:{resource or 'api'}"
    if method == "POST":
        action = "create" if resource and not path.rstrip("/").endswith(("publish", "withdraw", "read", "refresh")) else "action"
        tail = parts[-1] if len(parts) > 2 else ""
        action = tail if tail in ("publish", "withdraw", "read", "refresh", "import") else action
    elif method in ("PUT", "PATCH"):
        action = "update"
    elif method == "DELETE":
        action = "delete"
    else:
        action = method.lower()
    return code, action


def _validate_secret():
    if (not config.SECRET_KEY or len(config.SECRET_KEY) < 32
            or "change-me" in config.SECRET_KEY or "请更换" in config.SECRET_KEY):
        raise RuntimeError(
            "SECRET_KEY 仍是占位符或过弱，请执行 "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\" 生成后写入 "
            "backend/config.py"
        )


def create_platform_app():
    _validate_secret()
    app = Flask(__name__, static_folder=None)
    if config.CORS_ORIGINS:
        CORS(app, origins=config.CORS_ORIGINS, supports_credentials=True)
    app.secret_key = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
    app.permanent_session_lifetime = timedelta(days=config.SESSION_LIFETIME_DAYS)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.teardown_appcontext(db.close_request_conn)

    # 平台登录与基座接口；视频子系统不在此注册，避免路由前缀重复。
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(system_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(video_admin_bp)

    # P3 审计埋点：写操作记操作日志，未捕获异常记异常日志；两者失败都不影响主流程。
    @app.before_request
    def _audit_start():
        from flask import g
        import time
        g._audit_start = time.monotonic()

    @app.after_request
    def _audit_operate(response):
        from flask import request
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            module, action = _audit_route(request)
            if module:
                try:
                    success = response.status_code < 400
                    audit.record_operate(module, action, success)
                except Exception:  # noqa: BLE001 - 审计绝不影响响应
                    pass
        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def platform_spa(path):
        if path and os.path.isfile(os.path.join(PLATFORM_DIST, path)):
            return send_from_directory(PLATFORM_DIST, path)
        if path.startswith("assets/"):
            return jsonify({"code": 1, "msg": "静态资源不存在"}), 404
        if path.startswith("api/"):
            return jsonify({"code": 1, "msg": "接口不存在"}), 404
        return send_from_directory(PLATFORM_DIST, "index.html")

    @app.errorhandler(Exception)
    def handle_error(e):
        if isinstance(e, HTTPException):
            return jsonify({"code": 1, "msg": e.description}), e.code
        if "Access denied" in str(e) or "Can't connect" in str(e):
            return jsonify({
                "code": 1,
                "msg": "数据库连接失败：请检查 backend/config.py 中的密码，并确认 MySQL 服务已启动",
            }), 500
        app.logger.exception(e)
        # P3 异常审计：只记类型与摘要，完整堆栈仍留在服务端日志；未登录用户记 0。
        try:
            audit.record_exception(e)
        except Exception:  # noqa: BLE001 - 审计绝不影响错误响应
            pass
        return jsonify({"code": 1, "msg": "服务器内部错误，请查看后端日志"}), 500

    return app


def load_video_app():
    """按文件路径加载子系统 Flask 应用，避免与根入口 app.py 同名冲突。"""
    path = os.path.join(VIDEO_BACKEND_DIR, "app.py")
    spec = importlib.util.spec_from_file_location("video_subsystem_app", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_app()


app = create_platform_app()
application = DispatcherMiddleware(app, {"/video": load_video_app()})

if __name__ == "__main__":
    from werkzeug.serving import run_simple
    run_simple(
        config.HOST, config.PORT, application,
        use_debugger=config.DEBUG, use_reloader=False,
    )
