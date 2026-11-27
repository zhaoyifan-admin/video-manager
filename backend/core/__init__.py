"""中型管理平台内核：RBAC、权限缓存与安全入口。

该包位于 backend/core，由唯一入口 backend/app.py 加载；各子系统后端作为
backend/ 的子目录存在（如 backend/video/），前端同理位于 apps/<name>/。
包名使用 core，避免遮蔽 Python 标准库 platform。
"""
