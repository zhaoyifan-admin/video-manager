# -*- coding: utf-8 -*-
"""影库 · 新电脑一键安装程序

在项目根目录执行（Windows 可直接双击 install.bat）：

    py setup.py
    py setup.py --mysql-password 你的MySQL密码 --admin-password 你的强密码 --with-ffmpeg

一次运行自动完成：环境检查 -> Python 虚拟环境与后端依赖 -> backend/config.py
-> 建库建表(schema.sql) -> 超管账号 -> 平台与视频两套前端构建 -> ffmpeg(可选) -> 冒烟验收。

目录约定：backend/ 为主系统后端（含 core/ 与各子系统目录），apps/ 为 pnpm monorepo
前端应用目录；视频子系统分别位于 backend/video/ 与 apps/video/。

设计原则：
- 幂等：可反复运行，不覆盖 config.py 中已有的自定义配置，不清空已有数据，
  不重复创建超管；已装好的依赖与构建产物会自动跳过或安全重建。
- 不启动长期服务：验收用 Flask test_client 在进程内完成，不占用 5000/9000 端口，
  也不会干扰已经由 PyCharm / Vite 启动的实例。
- 不擅自安装系统级运行时（Python/Node/MySQL），只做检测并给出可复制的安装命令。
"""

from __future__ import annotations

import argparse
import ast
import glob
import importlib.util
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN_BACKEND = ROOT / "backend"
BACKEND = MAIN_BACKEND / "video"
VIDEO_FRONTEND = ROOT / "apps" / "video"
PLATFORM_FRONTEND = ROOT / "apps" / "platform"
MAIN_ENTRY = MAIN_BACKEND / "app.py"
VENV_DIR = BACKEND / "venv"
VENV_PY = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CONFIG_FILE = MAIN_BACKEND / "config.py"
CONFIG_EXAMPLE = MAIN_BACKEND / "config.example.py"
REQUIREMENTS = MAIN_BACKEND / "requirements.txt"
SCHEMA = BACKEND / "schema.sql"
DIST = VIDEO_FRONTEND / "dist"
PLATFORM_DIST = PLATFORM_FRONTEND / "dist"
DB_NAME = "video_manager"
TOTAL = 8


# ---------------------------------------------------------------- 输出与命令

def step(n, msg):
    print("\n[%d/%d] %s" % (n, TOTAL, msg), flush=True)


def ok(msg):
    print("    [OK] " + msg, flush=True)


def warn(msg):
    print("    [!]  " + msg, flush=True)


def die(msg):
    print("\n[FAIL] " + msg, flush=True)
    print("        修复后重新运行即可，已完成的步骤不会重复执行。", flush=True)
    sys.exit(1)


def run(argv, cwd=None, env=None, capture=False, check=True):
    """跨平台执行命令。Windows 上 npm/winget 多为 .cmd，需经 cmd.exe 才能启动。"""
    argv = [str(a) for a in argv]
    kwargs = dict(cwd=cwd, env=env, text=True, errors="replace")
    if os.name == "nt":
        command = subprocess.list2cmdline(argv)
        kwargs["shell"] = True
    else:
        command = argv
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = subprocess.run(command, **kwargs)
    if check and result.returncode != 0:
        if capture:
            print((result.stdout or "")[-2000:])
            print((result.stderr or "")[-2000:])
        die("命令失败（退出码 %d）：%s" % (result.returncode, " ".join(argv)))
    return result


def build_parser():
    p = argparse.ArgumentParser(
        description="影库新电脑一键安装（首次只需回答一次 MySQL 密码）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mysql-host", default="127.0.0.1", help="MySQL 地址")
    p.add_argument("--mysql-port", type=int, default=3306, help="MySQL 端口")
    p.add_argument("--mysql-user", default="root", help="MySQL 用户")
    p.add_argument("--mysql-password", default=None,
                   help="MySQL 密码；不填则依次读取 MYSQL_PWD 环境变量、已有 config.py，最后才交互询问")
    p.add_argument("--admin-password", default="admin123",
                   help="首次创建超管 admin 时使用的密码；建议一并设置强密码")
    p.add_argument("--with-ffmpeg", action="store_true",
                   help="缺少 ffmpeg/ffprobe 时尝试用 winget 自动安装（需联网）")
    p.add_argument("--skip-frontend", action="store_true", help="跳过前端依赖安装与构建")
    p.add_argument("--no-verify", action="store_true", help="跳过最后的冒烟验收")
    return p


# ---------------------------------------------------------- 0. 引导虚拟环境

def is_venv_python():
    try:
        return os.path.normcase(os.path.realpath(sys.executable)) == \
               os.path.normcase(os.path.realpath(str(VENV_PY)))
    except OSError:
        return False


def bootstrap():
    """用系统 Python 建好 backend/venv 后，切换回 venv 解释器重跑本脚本。"""
    print("[准备] 切换到 backend/venv 运行环境...", flush=True)
    if not VENV_PY.exists():
        if not REQUIREMENTS.exists():
            die("缺少 backend/requirements.txt")
        print("    [OK] 创建虚拟环境 " + str(VENV_DIR), flush=True)
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if not VENV_PY.exists():
        die("虚拟环境创建失败：%s 不存在。请确认 Python 安装时勾选了 pip/venv。" % VENV_PY)
    print("    [OK] 安装后端依赖 flask / flask-cors / pymysql / waitress", flush=True)
    run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(REQUIREMENTS)])
    env = os.environ.copy()
    env["VIDEO_MANAGER_INSTALLER"] = "1"
    result = subprocess.run(
        [str(VENV_PY), str(Path(__file__).resolve())] + sys.argv[1:],
        cwd=str(ROOT), env=env,
    )
    sys.exit(result.returncode)


# ------------------------------------------------------------ 1. 前置检查

def check_prereqs(args):
    if sys.version_info < (3, 10):
        die("需要 Python 3.10 以上（推荐 3.12+），当前 %s" % sys.version.split()[0])
    ok("Python " + sys.version.split()[0])
    if not args.skip_frontend:
        node = shutil.which("node")
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not node or not npm:
            die("未找到 Node.js / npm。请先安装 Node 18+：winget install OpenJS.NodeJS.LTS")
        version = run([node, "-v"], capture=True).stdout.strip()
        major = int(re.sub(r"\D", "", version.split(".")[0]) or 0)
        if major < 18:
            die("需要 Node 18+，当前 %s" % version)
        ok("Node %s / npm 已就绪" % version)
    else:
        ok("已指定 --skip-frontend，跳过 Node 检查")
    try:
        with socket.create_connection((args.mysql_host, args.mysql_port), timeout=4):
            pass
    except OSError as exc:
        die("连不上 MySQL %s:%s（%s）。请确认 MySQL 服务已启动、端口正确。"
            % (args.mysql_host, args.mysql_port, exc))
    ok("MySQL %s:%s 端口可连接" % (args.mysql_host, args.mysql_port))


def connect_db(args, password, database=None):
    import pymysql
    return pymysql.connect(
        host=args.mysql_host, port=args.mysql_port, user=args.mysql_user,
        password=password, database=database, charset="utf8mb4",
        autocommit=True, connect_timeout=8, cursorclass=pymysql.cursors.DictCursor,
    )


def load_config_module():
    spec = importlib.util.spec_from_file_location("_vm_install_config", CONFIG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_password(args):
    if args.mysql_password:
        return args.mysql_password, "命令行参数"
    if os.environ.get("MYSQL_PWD"):
        return os.environ["MYSQL_PWD"], "环境变量 MYSQL_PWD"
    if CONFIG_FILE.exists():
        try:
            value = load_config_module().DB_CONFIG.get("password")
            if value:
                return value, "已有 backend/config.py"
        except Exception:
            pass
    import getpass
    try:
        value = getpass.getpass("    请输入 MySQL %s 密码（只输入一次，不回显）: " % args.mysql_user)
    except (EOFError, KeyboardInterrupt):
        die("未获取到 MySQL 密码")
    if not value:
        die("MySQL 密码不能为空。可用 --mysql-password 传入，或直接交互输入。")
    return value, "交互输入"


# ------------------------------------------------------------ 2. 配置文件

def ensure_config(args, password):
    if not CONFIG_EXAMPLE.exists():
        die("缺少 backend/config.example.py，无法生成配置模板")
    if CONFIG_FILE.exists():
        text = CONFIG_FILE.read_text(encoding="utf-8")
        changed = False
        if args.mysql_password:
            text, count = re.subn(
                r'("password"\s*:\s*)("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')',
                lambda m: m.group(1) + json.dumps(password, ensure_ascii=False),
                text, count=1,
            )
            changed = changed or count > 0
        match = re.search(r"^SECRET_KEY\s*=\s*(.+?)\s*$", text, re.M)
        secret = ""
        if match:
            try:
                secret = ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                secret = ""
        if not isinstance(secret, str) or len(secret) < 32 or "请更换" in secret or "change-me" in secret:
            text = re.sub(
                r"^SECRET_KEY\s*=\s*.+$",
                lambda m: "SECRET_KEY = " + json.dumps(secrets.token_hex(32)),
                text, count=1, flags=re.M,
            )
            changed = True
        if changed:
            CONFIG_FILE.write_text(text, encoding="utf-8")
            ok("已同步 backend/config.py（密码 / 随机 SECRET_KEY）")
        else:
            ok("backend/config.py 已存在且有效，保留你的自定义配置")
    else:
        text = CONFIG_EXAMPLE.read_text(encoding="utf-8")
        replacements = [
            (r'("host"\s*:\s*)"[^"]*"', json.dumps(args.mysql_host)),
            (r'("port"\s*:\s*)\d+', str(args.mysql_port)),
            (r'("user"\s*:\s*)"[^"]*"', json.dumps(args.mysql_user)),
            (r'("password"\s*:\s*)"你的MySQL密码"', json.dumps(password, ensure_ascii=False)),
            (r'(SECRET_KEY\s*=\s*)"请更换为随机字符串"', json.dumps(secrets.token_hex(32))),
        ]
        for pattern, value in replacements:
            text, count = re.subn(pattern, lambda m: m.group(1) + value, text, count=1)
            if count != 1:
                warn("配置模板有一项未匹配到：%s（请检查 %s）" % (pattern, CONFIG_EXAMPLE.name))
        CONFIG_FILE.write_text(text, encoding="utf-8")
        ok("已生成 backend/config.py（填入数据库密码 + 随机 64 位 SECRET_KEY）")


# ------------------------------------------------------------ 3. 建库建表

def find_mysql_cli():
    found = shutil.which("mysql")
    if found:
        return found
    if os.name == "nt":
        for drive in "CDEFGH":
            for pattern in (
                "%s:\\Program Files\\MySQL\\*\\bin\\mysql.exe" % drive,
                "%s:\\Program Files (x86)\\MySQL\\*\\bin\\mysql.exe" % drive,
            ):
                for path in glob.glob(pattern):
                    if Path(path).is_file():
                        return path
    for path in ("/usr/local/mysql/bin/mysql", "/opt/homebrew/bin/mysql", "/usr/bin/mysql"):
        if Path(path).is_file():
            return path
    return None


def split_sql(text):
    """把 schema.sql 拆成单条语句（正确处理注释、引号与字符串内的分号）。"""
    statements, buf = [], []
    in_single = in_double = in_backtick = False
    i, length = 0, len(text)
    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""
        if not (in_single or in_double or in_backtick) and (ch == "#" or (ch == "-" and nxt == "-")):
            end = text.find("\n", i)
            if end == -1:
                break
            i = end
            continue
        if ch == "'" and not in_double and not in_backtick:
            if in_single and nxt == "'":
                buf.append("''")
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        if ch == ";" and not (in_single or in_double or in_backtick):
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def apply_schema_via_pymysql(args, password):
    conn = connect_db(args, password)
    try:
        with conn.cursor() as cur:
            for index, statement in enumerate(split_sql(SCHEMA.read_text(encoding="utf-8")), 1):
                try:
                    cur.execute(statement)
                except Exception as exc:
                    die("schema.sql 第 %d 条语句执行失败：%s\n         语句片段：%s"
                        % (index, exc, statement[:120].replace("\n", " ")))
    finally:
        conn.close()


def apply_schema(args, password):
    sql = SCHEMA.read_text(encoding="utf-8")
    if "CREATE DATABASE" not in sql:
        die("backend/schema.sql 内容异常：缺少 CREATE DATABASE")
    cli = find_mysql_cli()
    if cli:
        env = os.environ.copy()
        env["MYSQL_PWD"] = password  # 密码不出现在命令行
        with SCHEMA.open("r", encoding="utf-8") as handle:
            result = subprocess.run(
                [cli, "-h", args.mysql_host, "-P", str(args.mysql_port), "-u", args.mysql_user,
                 "--default-character-set=utf8mb4"],
                stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, errors="replace", env=env,
            )
        if result.returncode == 0:
            ok("已执行 schema.sql（mysql 客户端，幂等建表 / 补列）")
            return
        warn("mysql 客户端执行失败，改用 PyMySQL 直接执行：%s"
             % (result.stderr or "").strip()[:200])
    else:
        warn("未找到 mysql 客户端，改用 PyMySQL 直接执行 schema.sql")
    apply_schema_via_pymysql(args, password)
    ok("已执行 schema.sql（PyMySQL 逐句，幂等建表 / 补列）")


# ------------------------------------------------------------ 4. 超管账号

def ensure_admin(args, password):
    from werkzeug.security import generate_password_hash
    conn = connect_db(args, password, DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM information_schema.tables "
                        "WHERE table_schema = %s", (DB_NAME,))
            tables = cur.fetchone()["c"]
            if tables == 0:
                die("数据库 %s 里没有表，建库步骤未生效" % DB_NAME)
            cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
            if cur.fetchone():
                ok("超管 admin 已存在，保留原密码不覆盖")
            else:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    ("admin", generate_password_hash(args.admin_password), "admin"),
                )
                ok("已创建超管 admin（schema.sql 不含种子账号，由安装程序补建）")
            return tables
    finally:
        conn.close()


# ------------------------------------------------------------ 5. 前端

def ensure_frontend(args):
    if args.skip_frontend:
        warn("已指定 --skip-frontend，跳过前端依赖与构建")
        return
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if not pnpm:
        die("未找到 pnpm，请先执行 npm install -g pnpm@10.11.0 或 corepack enable")
    # pnpm workspace 在仓库根目录安装一次、turbo 在根目录统一编排构建。
    node_modules = ROOT / "node_modules"
    if node_modules.is_dir() and (node_modules / ".pnpm").is_dir():
        ok("前端依赖已就绪，跳过安装")
    else:
        run([pnpm, "install"], cwd=str(ROOT))
        ok("前端 pnpm install 完成")
    run([pnpm, "build"], cwd=str(ROOT))
    for dist, label in ((PLATFORM_DIST, "中型管理平台"), (DIST, "视频子系统")):
        index = dist / "index.html"
        assets = list((dist / "assets").glob("*.js")) if (dist / "assets").is_dir() else []
        if not index.is_file() or not assets:
            die("%s 前端构建产物不完整：缺少 index.html 或 assets/*.js" % label)
        ok("%s 前端构建完成（1 个 index.html + %d 个 JS 资源）" % (label, len(assets)))


# ------------------------------------------------------------ 6. ffmpeg

def ensure_ffmpeg(args):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if args.with_ffmpeg and not (ffmpeg and ffprobe):
        winget = shutil.which("winget")
        if winget and os.name == "nt":
            print("    正在用 winget 安装 ffmpeg（首次需联网，请稍候）...", flush=True)
            result = run([winget, "install", "--id", "Gyan.FFmpeg", "-e",
                          "--accept-source-agreements", "--accept-package-agreements"],
                         check=False)
            if result.returncode == 0:
                ok("ffmpeg 安装命令已完成；需重新打开终端并重启后端才会被探测到")
                return
            warn("winget 安装未成功，可稍后手动执行：winget install --id Gyan.FFmpeg -e")
        else:
            warn("本机没有 winget，无法自动安装 ffmpeg")
    if ffmpeg and ffprobe:
        ok("ffmpeg / ffprobe 已就绪")
    else:
        warn("未检测到 ffmpeg / ffprobe：不影响启动，但入库不抽封面、播放页不做编码探测")
        warn("可运行 py setup.py --with-ffmpeg，或手动安装后重启后端")


# ------------------------------------------------------------ 7. 验收

def verify(args, admin_password):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("management_root_entry", MAIN_ENTRY)
    root_entry = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(root_entry)
    except Exception as exc:
        die("根入口导入失败：%s" % exc)
    from werkzeug.test import Client
    client = Client(root_entry.application)
    failures = []

    def check(name, condition):
        if condition:
            ok(name)
        else:
            failures.append(name)
            print("    [FAIL] " + name, flush=True)

    response = client.get("/")
    check("首页 / 返回 200 且是前端页面",
          response.status_code == 200 and b'id="app"' in response.data)
    response = client.get("/login")
    check("前端路由 /login 回退到 index.html",
          response.status_code == 200 and b'id="app"' in response.data)
    js_files = list((PLATFORM_DIST / "assets").glob("*.js")) if (PLATFORM_DIST / "assets").is_dir() else []
    if js_files:
        response = client.get("/assets/" + js_files[0].name)
        check("静态 JS 资源可访问且 MIME 正确",
              response.status_code == 200 and "javascript" in (response.content_type or ""))
    response = client.get("/video/")
    check("视频子系统 /video/ 返回 200",
          response.status_code == 200 and b'id="app"' in response.data)
    response = client.get("/api/auth/config")
    check("/api/auth/config 返回 code 0",
          response.status_code == 200 and response.get_json().get("code") == 0)

    logged_in = False
    response = client.post("/api/auth/login",
                           json={"username": "admin", "password": admin_password})
    logged_in = response.status_code == 200 and response.get_json().get("code") == 0
    if logged_in:
        ok("超管登录接口返回 code 0")
        response = client.get("/api/auth/me")
        me = response.get_json().get("data") or {}
        check("登录态 /api/auth/me 返回当前账号", me.get("username") == "admin")
        if me.get("role") != "admin":
            # 已有库里账号角色可能由用户在「站点管理」调整过（例如另设超管），安装程序不擅自改回
            warn("账号 admin 当前角色为 %s（可能已人工调整），脚本不改动角色" % me.get("role"))
        response = client.get("/api/system/menus")
        check("平台接口 /api/system/menus 返回 code 0",
              response.status_code == 200 and response.get_json().get("code") == 0)
        response = client.get("/video/api/videos")
        check("视频子系统接口 /video/api/videos 可查询",
              response.status_code == 200 and response.get_json().get("code") == 0)
    else:
        warn("超管密码已不是本次设置的值（可能已改密），跳过登录态校验；账号存在性已在数据库确认")

    if failures:
        die("验收未通过：%s" % "、".join(failures))
    ok("冒烟验收全部通过（进程内 test_client，未启动或重启任何服务）")


# ------------------------------------------------------------ 汇总

def summary(args, tables, admin_password):
    print("\n" + "=" * 62, flush=True)
    print("安装完成", flush=True)
    print("=" * 62, flush=True)
    print("  数据库    : %s（%s 张表，幂等，未清空任何已有数据）" % (DB_NAME, tables), flush=True)
    print("  超管账号  : admin / %s" % ("你设置的密码" if args.admin_password != "admin123" else "admin123"), flush=True)
    print("  配置文件  : backend\\config.py（全系统共用，随机 SECRET_KEY，DEBUG=False）", flush=True)
    print("  前端产物  : frontend\\dist（平台） + frontend\\video\\dist（子系统），共用一套配置", flush=True)
    print("", flush=True)
    print("  启动入口  : backend\\video\\venv\\Scripts\\python.exe backend\\app.py（唯一外层入口）", flush=True)
    print("  平台入口  : http://127.0.0.1:5000/（登录 / 控制台）", flush=True)
    print("  视频子系统: http://127.0.0.1:5000/video/", flush=True)
    print("  开发前端  : cd frontend && npm run dev       ->  http://localhost:9000（平台）", flush=True)
    print("              cd frontend && npm run dev:video  ->  http://localhost:9001（视频）", flush=True)
    print("              （Vite 只监听 IPv6 localhost，写 127.0.0.1 连不上）", flush=True)
    print("", flush=True)
    print("  待办      : 1) 立即修改 admin 默认密码；2) 按需要设置", flush=True)
    print("              REGISTRATION_ENABLED / MEDIA_ROOTS；3) 局域网访问用", flush=True)
    print("              cd backend && video\\venv\\Scripts\\python.exe -m waitress --host=0.0.0.0 --port=5000 app:application", flush=True)
    print("=" * 62, flush=True)
    if admin_password == "admin123":
        warn("当前仍是默认超管密码 admin123，请登录后在「站点管理」尽快改密")


def main():
    args = build_parser().parse_args()
    if not is_venv_python():
        bootstrap()

    step(1, "检查运行环境（Python / Node / MySQL）")
    check_prereqs(args)

    step(2, "确认 MySQL 连接与配置")
    password, source = resolve_password(args)
    try:
        conn = connect_db(args, password)
        conn.close()
    except Exception as exc:
        die("MySQL 连接失败（%s）：%s\n        密码来源：%s。可用 --mysql-password 指定正确密码。"
            % (type(exc).__name__, str(exc)[:200], source))
    ok("MySQL 认证成功（密码来源：%s）" % source)
    ensure_config(args, password)

    step(3, "执行 backend/schema.sql 建库建表（幂等）")
    apply_schema(args, password)

    step(4, "确保超管账号存在")
    tables = ensure_admin(args, password)

    step(5, "安装 pnpm workspace 依赖并构建 apps/*/dist")
    ensure_frontend(args)

    step(6, "检查 ffmpeg / ffprobe（可选）")
    ensure_ffmpeg(args)

    step(7, "创建运行目录")
    for folder in (BACKEND / "uploads", BACKEND / "thumbs"):
        folder.mkdir(parents=True, exist_ok=True)
    ok("backend/uploads 与 backend/thumbs 已就绪")

    step(8, "冒烟验收（进程内，不启动服务）")
    if args.no_verify:
        warn("已指定 --no-verify，跳过验收")
    else:
        verify(args, args.admin_password)

    summary(args, tables, args.admin_password)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。", flush=True)
        sys.exit(130)
