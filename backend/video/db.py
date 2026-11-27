"""数据库访问层：统一获取连接、执行查询与写入

性能：query / execute 在单个 HTTP 请求内复用同一条连接（挂在 flask.g 上），
并在请求之间用轻量连接池复用，避免每条 SQL 都新建 TCP 连接 + MySQL 认证。
PyMySQL 的纯 Python 握手约 20ms（在调试器下可达 100ms），原先一个视频列表
请求要建 8 次连接，是接口耗时的主要来源，与数据量、索引无关。

兼容性：
- get_conn() 仍返回「独立新建连接」，供 routes/videos.py 里 4 处显式事务使用；
  调用方照常 commit()/rollback()/close()，语义不变，不参与池化。
- 无 Flask 应用上下文时（后台线程、脚本、测试 setup）退化为「临时取用 + 归还」。
- 异常路径会丢弃连接而不是放回池，避免把残留事务 / 坏连接带给下一个请求。
"""
import queue
import threading

import pymysql
from flask import g, has_app_context

from config import DB_CONFIG

POOL_SIZE = 8
_G_KEY = "_db_conn"

_pool = queue.LifoQueue(maxsize=POOL_SIZE)
_count_lock = threading.Lock()
_created = 0


def _new_conn():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def _prepare(conn):
    """调大 group_concat_max_len，避免标签较多时 GROUP_CONCAT 被静默截断。

    放在每次取用时执行：ping(reconnect=True) 重连后会话变量会丢失。"""
    with conn.cursor() as cur:
        cur.execute("SET SESSION group_concat_max_len = 65535")


def _discard(conn):
    """关闭坏连接并释放池配额，不放回池"""
    global _created
    try:
        conn.close()
    except Exception:
        pass
    with _count_lock:
        _created = max(0, _created - 1)


def _acquire():
    """取一条连接：优先复用池中的空闲连接，池空且未达上限时新建"""
    global _created
    try:
        conn = _pool.get_nowait()
    except queue.Empty:
        with _count_lock:
            can_create = _created < POOL_SIZE
            if can_create:
                _created += 1
        if can_create:
            try:
                conn = _new_conn()
            except Exception:
                with _count_lock:
                    _created -= 1
                raise
        else:
            # 所有连接都在使用中：短等，避免无限新建把 MySQL 连接数打满
            conn = _pool.get(timeout=10)
    try:
        conn.ping(reconnect=True)  # 处理 MySQL wait_timeout 之后的断线
        _prepare(conn)
    except Exception:
        _discard(conn)
        raise
    return conn


def _release(conn):
    if getattr(conn, "_vm_broken", False):
        _discard(conn)
        return
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        _discard(conn)


def _mark_broken(conn):
    """异常后标记连接不可用：残留事务不能带回池里复用"""
    conn._vm_broken = True
    if has_app_context() and g.get(_G_KEY) is conn:
        g.pop(_G_KEY, None)  # 同请求内后续调用需重新取一条干净连接
    try:
        conn.rollback()
    except Exception:
        pass


def _borrow():
    """返回 (连接, 是否临时取用)。请求内复用 g 缓存，由 teardown 归还"""
    if has_app_context():
        conn = g.get(_G_KEY)
        if conn is None:
            conn = _acquire()
            setattr(g, _G_KEY, conn)
        return conn, False
    return _acquire(), True


def close_request_conn(exc=None):
    """Flask teardown_appcontext 钩子：把请求内使用的连接归还池中"""
    if not has_app_context():
        return
    conn = g.pop(_G_KEY, None)
    if conn is not None:
        _release(conn)


def get_conn():
    """获取一条独立的新连接（显式事务用；调用方负责 commit/rollback/close）"""
    conn = _new_conn()
    _prepare(conn)
    return conn


def _run(sql, args, write=False):
    conn, temporary = _borrow()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            result = ({"rowcount": cur.rowcount, "lastrowid": cur.lastrowid}
                      if write else cur.fetchall())
        conn.commit()
        return result
    except Exception:
        _mark_broken(conn)
        temporary = True  # 已从 g 摘除，finally 里立即释放（走丢弃分支）
        raise
    finally:
        if temporary:
            _release(conn)


def query(sql, args=None, one=False):
    """执行查询并返回结果列表；one=True 时返回单条记录或 None"""
    rows = _run(sql, args)
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=None):
    """执行写入并返回 {'rowcount', 'lastrowid'}"""
    return _run(sql, args, write=True)
