"""缩略图生成：ffmpeg 抽帧 + 同视频并发锁 + 缓存清理"""
import os
import subprocess
import threading

from config import FFMPEG_BIN, FFPROBE_BIN, THUMB_DIR, THUMB_WIDTH

_thumb_locks = {}
_thumb_locks_guard = threading.Lock()


def _get_thumb_lock(video_id):
    """同一视频的缩略图生成请求共用一把锁，避免并发重复跑 ffmpeg"""
    with _thumb_locks_guard:
        if video_id not in _thumb_locks:
            _thumb_locks[video_id] = threading.Lock()
        return _thumb_locks[video_id]


def _probe_duration(path):
    if not FFPROBE_BIN:
        return None
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def generate_thumbnail(video_id, path):
    """用 ffmpeg 抽帧生成缩略图，成功返回文件路径，失败返回 None"""
    if not FFMPEG_BIN:
        return None
    duration = _probe_duration(path)
    # 取约 10% 进度处的画面（跳过片头黑屏），上限 5 秒；取不到时长则用 1 秒
    seek = max(0.1, min(duration * 0.1, 5)) if duration and duration > 0 else 1.0
    os.makedirs(THUMB_DIR, exist_ok=True)
    thumb = thumb_path(video_id)
    tmp = thumb + ".tmp.jpg"
    try:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-ss", f"{seek:.2f}", "-i", path, "-frames:v", "1",
             "-vf", f"scale={THUMB_WIDTH}:-2", "-q:v", "5", tmp],
            capture_output=True, timeout=60,
        )
        if os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, thumb)  # 原子替换，避免读到半成品
            return thumb
    except Exception:
        pass
    if os.path.isfile(tmp):
        os.remove(tmp)
    return None


def thumb_path(video_id):
    """某视频缩略图的缓存路径"""
    return os.path.join(THUMB_DIR, f"{video_id}.jpg")


def remove_thumb(video_id):
    """删除某视频的缩略图缓存（存在与否不影响调用方结果）"""
    try:
        if os.path.isfile(thumb_path(video_id)):
            os.remove(thumb_path(video_id))
    except OSError:
        pass


def ensure_generated(video_id, path):
    """缩略图不存在时现场生成（同一视频并发只生成一次），返回最终缓存路径或 None"""
    thumb = thumb_path(video_id)
    if os.path.isfile(thumb):
        return thumb
    with _get_thumb_lock(video_id):
        if not os.path.isfile(thumb):  # 拿到锁后二次确认，前一个请求可能已生成
            generate_thumbnail(video_id, path)
    return thumb if os.path.isfile(thumb) else None
