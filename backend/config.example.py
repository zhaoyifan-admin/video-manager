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
