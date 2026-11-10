"""媒体接口：上传 / 播放流 / 缩略图（挂在 /api/videos 下）"""
import os

from flask import Blueprint, g, request, send_file

import db
from auth import require_login, visible_sql
from config import UPLOAD_DIR
from responses import ok, fail
from storage import sanitize_filename, resolve_video_path
from thumbnails import ensure_generated

bp = Blueprint("media", __name__, url_prefix="/api/videos")


@bp.post("/upload")
@require_login
def upload_video_file():
    """接收上传的视频文件；指定 saveDir 时存入该目录（外接硬盘等），否则存入 uploads 目录"""
    file = request.files.get("file")
    if not file or not file.filename:
        return fail("请选择要上传的视频文件")
    name = sanitize_filename(request.form.get("fileName") or file.filename)

    save_dir = (request.form.get("saveDir") or "").strip()
    if save_dir:
        if not os.path.isabs(save_dir) or not os.path.isdir(save_dir):
            return fail("保存路径无效或不存在，请重新选择")
        target_dir = save_dir
    else:
        target_dir = UPLOAD_DIR
        os.makedirs(target_dir, exist_ok=True)

    dest = os.path.join(target_dir, name)
    if os.path.exists(dest):
        # 重名时不改动原文件名，仅在末尾追加 (n) 防止覆盖
        root, ext = os.path.splitext(name)
        n = 1
        while os.path.exists(os.path.join(target_dir, f"{root}({n}){ext}")):
            n += 1
        name = f"{root}({n}){ext}"
        dest = os.path.join(target_dir, name)
    file.save(dest)
    # 自定义目录存绝对路径，uploads 存相对路径（resolve_video_path 两者都兼容）
    stored_path = dest if save_dir else f"uploads/{name}"
    return ok({"filePath": stored_path, "fileName": file.filename})


@bp.get("/<int:video_id>/file")
@require_login
def play_video(video_id):
    """流式返回本地视频文件，支持 Range 请求（可拖动进度条）；本人 / 公开视频 / 超管可播放"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT file_path FROM videos WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    path = resolve_video_path(row["file_path"])
    if not path:
        return fail("文件不存在或路径无效，请检查该视频的「文件路径」字段", 404)
    return send_file(path, conditional=True)


@bp.get("/<int:video_id>/thumb")
@require_login
def video_thumbnail(video_id):
    """返回视频缩略图；尚不存在时现场用 ffmpeg 生成（同一视频并发只生成一次）"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT file_path FROM videos WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    path = resolve_video_path(row["file_path"])
    if not path:
        return fail("源文件不存在或路径无效", 404)
    thumb = ensure_generated(video_id, path)
    if thumb:
        return send_file(thumb, mimetype="image/jpeg", conditional=True)
    return fail("缩略图生成失败（请确认服务器已安装 ffmpeg）", 404)
