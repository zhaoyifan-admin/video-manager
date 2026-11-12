"""视频管理系统后端服务 —— 应用入口
技术栈：Flask + PyMySQL + MySQL

结构：
  config.py     连接与路径配置
  db.py         数据库访问层
  responses.py  统一响应 {code, msg, data}
  storage.py    文件路径工具
  thumbnails.py ffmpeg 缩略图
  routes/       各领域路由蓝图（tags / types / videos / media / paths）

启动方式：python app.py（默认 http://127.0.0.1:5000）
"""
import os
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import (
    BASE_DIR, CORS_ORIGINS, DEBUG, HOST, MAX_UPLOAD_BYTES, PORT,
    SECRET_KEY, SESSION_LIFETIME_DAYS,
)
from routes import register_blueprints

# 前端托管目录（生产部署）：npm run build 后直接访问 http://HOST:PORT 即可
DIST_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))


def create_app():
    app = Flask(__name__)
    # 前后端同源部署时不需要 CORS；仅在配置了可信来源时才开放跨域
    if CORS_ORIGINS:
        CORS(app, origins=CORS_ORIGINS, supports_credentials=True)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    if not SECRET_KEY or len(SECRET_KEY) < 32 or "change-me" in SECRET_KEY or "请更换" in SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY 仍是占位符或过弱，请执行 "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\" 生成后写入 backend/config.py"
        )
    app.secret_key = SECRET_KEY
    app.permanent_session_lifetime = timedelta(days=SESSION_LIFETIME_DAYS)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # 缓解跨站携带会话 cookie
    # 若部署在 HTTPS 下，可再加：app.config["SESSION_COOKIE_SECURE"] = True

    # 注册所有业务路由（/api 下）
    register_blueprints(app)

    # ---------- 前端托管（生产部署） ----------
    # 所有业务路由都在 /api 下（优先级更高），这里只兜住前端页面与静态资源
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path and os.path.isfile(os.path.join(DIST_DIR, path)):
            return send_from_directory(DIST_DIR, path)
        # 静态资源缺失时直接 404，不能拿 index.html 冒充 JS/CSS：
        # 否则浏览器按 text/html 收到脚本却报 200，白屏问题很难定位
        if path.startswith("assets/"):
            return jsonify({"code": 1, "msg": "静态资源不存在"}), 404
        # 前端路由（/play/:id、/detail/:id）回退到 index.html，由 vue-router 接管
        return send_from_directory(DIST_DIR, "index.html")

    # ---------- 全局错误处理 ----------
    @app.errorhandler(Exception)
    def handle_error(e):
        if isinstance(e, HTTPException):
            return jsonify({"code": 1, "msg": e.description}), e.code
        if "Access denied" in str(e) or "Can't connect" in str(e):
            return jsonify({"code": 1, "msg": "数据库连接失败：请检查 backend/config.py 中的密码，并确认 MySQL 服务已启动"}), 500
        # 异常原文只写日志，不回显给客户端（避免泄露 SQL、本机路径等）
        app.logger.exception(e)
        return jsonify({"code": 1, "msg": "服务器内部错误，请查看后端日志"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
