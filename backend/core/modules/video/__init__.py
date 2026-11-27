"""视频运营管理接口（从视频子系统搬移的审核 / 站点管理 / 分类管理）。

三类能力统一挂到主系统 /api/video-admin 前缀，改用 RBAC 权限码鉴权；
视频子系统仅保留日常浏览 / 上传 / 结果查看所需的只读接口。

设计约束：
1. 审核留痕仍写入视频专属日志表（video/tag/type/collection_audit_logs），
   不混入平台 sys_operate_log，语义互不替代；
2. 视频公开可见规则（auth.visible_sql）保持在视频子系统，本模块不触碰；
3. 辅助日志模块留在 backend/video 原位，通过 sys.path 直接复用，不复制代码。
"""
from flask import Blueprint

bp = Blueprint("video_admin", __name__, url_prefix="/api/video-admin")

from .taxonomy import bp as taxonomy_bp  # noqa: E402
from .audit import bp as audit_bp  # noqa: E402
from .admin import bp as admin_bp  # noqa: E402

bp.register_blueprint(taxonomy_bp)
bp.register_blueprint(audit_bp)
bp.register_blueprint(admin_bp)
