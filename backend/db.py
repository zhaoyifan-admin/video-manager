"""数据库访问层：统一获取连接、执行查询与写入"""
import pymysql

from config import DB_CONFIG


def get_conn():
    """获取一个新的数据库连接（DictCursor，查询结果以 dict 返回）

    调大 group_concat_max_len，避免标签较多时 GROUP_CONCAT 被默认的 1024 字节静默截断。"""
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    with conn.cursor() as cur:
        cur.execute("SET SESSION group_concat_max_len = 65535")
    return conn


def query(sql, args=None, one=False):
    """执行查询并返回结果列表；one=True 时返回单条记录或 None"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            rows = cur.fetchall()
        conn.commit()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, args=None):
    """执行写入并返回 {'rowcount', 'lastrowid'}"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            result = {"rowcount": cur.rowcount, "lastrowid": cur.lastrowid}
        conn.commit()
        return result
    finally:
        conn.close()
