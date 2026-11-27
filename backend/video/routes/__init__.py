"""视频子系统路由注册中心。

url_prefix 为空时按蓝图原始 /api 前缀注册（子系统独立运行）；
传入 /video/api 时作为中型管理平台的子系统挂载，全部接口自动加前缀。
平台自身的 /api/system 与 /api/auth 由根入口 app.py 单独注册。

审核中心 / 站点管理 / 标签类型管理已移至主系统（/api/video-admin/*），
视频子系统只注册日常浏览、上传、播放、审核结果与个人中心所需接口。
"""
from . import (
    paths, tags, types, videos, media, auth, extra, playlists, collections, engagement,
)

auth_bp = auth.bp

BLUEPRINTS = (
    auth.bp, tags.bp, types.bp, videos.bp, media.bp, paths.bp, extra.bp,
    playlists.bp, collections.bp, engagement.bp,
)


def register_blueprints(app, url_prefix=None):
    for bp in BLUEPRINTS:
        if not url_prefix:
            app.register_blueprint(bp)
            continue
        own_prefix = bp.url_prefix or ""
        app.register_blueprint(
            bp,
            name=f"video_{bp.name}",
            url_prefix=f"{url_prefix}{own_prefix}",
        )
