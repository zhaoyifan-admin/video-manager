"""进程内 TTL 缓存：单进程部署下的权限集合缓存。

多进程部署时该缓存不跨进程，权限变更通过 sys_config.permission_version
作为缓存 key 的一部分来失效；后续可替换为 Redis 而不改调用方。
"""
import threading
import time

_store = {}
_lock = threading.Lock()


def remember(key, ttl_seconds, loader):
    """读取缓存；未命中或过期时调用 loader 生成并写入。"""
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = loader()
    with _lock:
        _store[key] = (now + ttl_seconds, value)
    return value


def invalidate_prefix(prefix):
    """按前缀失效，供角色/菜单变更时显式调用。"""
    with _lock:
        for key in [k for k in _store if k.startswith(prefix)]:
            _store.pop(key, None)
