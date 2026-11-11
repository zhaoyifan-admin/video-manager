# MySQL 连接配置模板 —— 复制为 config.py 后按本机实际填写
#   cp backend/config.example.py backend/config.py
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "你的MySQL密码",  # ← 必改
    "database": "video_manager",
    "charset": "utf8mb4",
}

# Flask 服务地址
HOST = "127.0.0.1"
PORT = 5000

# 会话密钥：登录态 cookie 的签名密钥，请更换为随机字符串
#   python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = "请更换为随机字符串"
SESSION_LIFETIME_DAYS = 30  # 登录态有效期（天）

# ---------- 安全与运行策略 ----------
# 媒体根目录白名单：上传目录、外接硬盘挂载点、常用媒体目录会自动加入；
# 视频放在其他位置时，在此追加其根目录绝对路径（子目录自动允许）
MEDIA_ROOTS = []

# 允许入库的视频扩展名（路径须落在白名单根内，防止读写任意本机文件）
ALLOWED_VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv",
    ".ts", ".m2ts", ".mpg", ".mpeg", ".rmvb", ".rm", ".3gp", ".ogv",
}

REGISTRATION_ENABLED = True  # 是否开放新用户注册；关闭后仅已有账号可登录
MAX_VIDEOS_PER_USER = 0      # 每个用户最多可入库的视频条数，0 表示不限
DEBUG = False                # 开发调试模式；局域网/公网部署务必保持 False
CORS_ORIGINS = []            # 允许跨域的前端来源；同源部署留空即不启用 CORS

# ---------- 路径与外部工具 ----------
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
THUMB_DIR = os.path.join(BASE_DIR, "thumbs")

FFMPEG_BIN = shutil.which("ffmpeg")
FFPROBE_BIN = shutil.which("ffprobe")
THUMB_WIDTH = 640
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 单文件上传上限 2GB
