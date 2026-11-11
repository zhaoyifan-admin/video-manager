"""路由蓝图注册中心：把各领域路由统一挂到 Flask 应用上"""
from . import paths, tags, types, videos, media, auth, audit_logs, extra

BLUEPRINTS = (
    auth.bp, tags.bp, types.bp, videos.bp, media.bp, paths.bp, audit_logs.bp, extra.bp,
)


def register_blueprints(app):
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
