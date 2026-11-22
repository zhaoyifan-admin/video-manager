"""媒体接口：上传 / 播放流 / 缩略图 / 媒体信息（挂在 /api/videos 下）"""
import json
import os
import re
import subprocess

from flask import Blueprint, Response, g, request, send_file

import db
from auth import require_login, visible_sql
from config import FFMPEG_BIN, FFPROBE_BIN, UPLOAD_DIR
from responses import ok, fail
from storage import (
    ALLOWED_SUBTITLE_EXTS,
    has_video_ext,
    is_remote_url,
    is_within,
    resolve_asset_path,
    resolve_video_path,
    sanitize_filename,
    validate_media_path,
)
from thumbnails import schedule_generation, thumb_path

bp = Blueprint("media", __name__, url_prefix="/api/videos")

# 缩略图尚未生成时的占位图：让首屏立刻有内容，后台异步补图
_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
    '<rect width="640" height="360" fill="#181818"/>'
    '<text x="320" y="185" fill="#555" font-size="20" text-anchor="middle" '
    'font-family="sans-serif">封面生成中…</text></svg>'
)


@bp.post("/upload")
@require_login
def upload_video_file():
    """接收上传的视频文件；指定 saveDir 时存入该目录（外接硬盘等），否则存入 uploads 目录"""
    file = request.files.get("file")
    if not file or not file.filename:
        return fail("请选择要上传的视频文件")
    name = sanitize_filename(request.form.get("fileName") or file.filename)
    if not has_video_ext(name):
        return fail("仅支持上传视频文件（mp4 / mkv / mov / avi / webm 等）")

    save_dir = (request.form.get("saveDir") or "").strip()
    if save_dir:
        if not os.path.isabs(save_dir) or not os.path.isdir(save_dir):
            return fail("保存路径无效或不存在，请重新选择")
        if not is_within(save_dir):
            return fail("保存目录不在允许的媒体目录内，请在 config.py 的 MEDIA_ROOTS 中登记")
        target_dir = os.path.realpath(save_dir)
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
        f"SELECT file_path FROM videos v WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    path = resolve_video_path(row["file_path"])
    if not path:
        return fail("源文件不存在或路径不在允许的媒体目录内，请检查磁盘挂载与 MEDIA_ROOTS 配置", 404)
    return send_file(path, conditional=True)


@bp.get("/<int:video_id>/thumb")
@require_login
def video_thumbnail(video_id):
    """返回视频缩略图；未生成时立即返回占位图并在后台异步生成，不阻塞首屏"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT file_path FROM videos v WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    thumb = thumb_path(video_id)
    if os.path.isfile(thumb):
        return send_file(thumb, mimetype="image/jpeg", conditional=True)

    path = resolve_video_path(row["file_path"])
    if not path:
        return fail("源文件不存在或路径无效", 404)
    if not FFMPEG_BIN:
        return fail("缩略图生成失败（请确认服务器已安装 ffmpeg）", 404)
    schedule_generation(video_id, path)
    return Response(
        _PLACEHOLDER_SVG,
        mimetype="image/svg+xml",
        headers={"X-Thumb-Pending": "1", "Cache-Control": "no-store"},
    )


# 浏览器原生 <video> 普遍可直接解码的编码；其他编码需要转码
_BROWSER_VIDEO_CODECS = {"h264", "vp8", "vp9", "av1"}
_BROWSER_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis", "flac"}


@bp.get("/<int:video_id>/media-info")
@require_login
def media_info(video_id):
    """用 ffprobe 探测源文件编码，供播放失败时给出明确原因（MKV/HEVC 等浏览器不兼容）"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT file_path FROM videos v WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row:
        return fail("视频不存在", 404)
    if is_remote_url(row["file_path"]):
        return ok({"available": False, "reason": "外链视频由浏览器直接播放"})
    path = resolve_video_path(row["file_path"])
    if not path:
        return fail("源文件不存在或路径无效", 404)
    if not FFPROBE_BIN:
        return ok({"available": False, "reason": "服务器未安装 ffprobe，无法探测编码"})
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
            capture_output=True, text=True, timeout=20,
        )
        info = json.loads(out.stdout or "{}")
    except Exception:
        return ok({"available": False, "reason": "编码探测失败"})

    video_codecs, audio_codecs = [], []
    for s in info.get("streams", []):
        codec = (s.get("codec_name") or "").lower()
        if s.get("codec_type") == "video" and codec:
            video_codecs.append(codec)
        elif s.get("codec_type") == "audio" and codec:
            audio_codecs.append(codec)
    incompatible = [c for c in video_codecs if c not in _BROWSER_VIDEO_CODECS]
    incompatible += [c for c in audio_codecs if c not in _BROWSER_AUDIO_CODECS]
    fmt = info.get("format") or {}
    return ok({
        "available": True,
        "compatible": not incompatible,
        "videoCodecs": video_codecs,
        "audioCodecs": audio_codecs,
        "container": (fmt.get("format_name") or "").split(",")[0],
        "duration": float(fmt.get("duration") or 0),
        "incompatible": incompatible,
    })


@bp.get("/<int:video_id>/subtitle")
@require_login
def video_subtitle(video_id):
    """返回 WebVTT 字幕；.srt 会做一次轻量格式转换供浏览器 <track> 使用"""
    vis_sql, vis_args = visible_sql(g.user)
    row = db.query(
        f"SELECT subtitle_path FROM videos v WHERE id = %s AND {vis_sql}",
        (video_id, *vis_args),
        one=True,
    )
    if not row or not row["subtitle_path"]:
        return fail("未设置字幕", 404)
    path = resolve_asset_path(row["subtitle_path"], ALLOWED_SUBTITLE_EXTS)
    if not path:
        return fail("字幕文件不存在或路径无效", 404)
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    except OSError:
        return fail("字幕文件读取失败", 404)
    if path.lower().endswith(".srt"):
        text = "WEBVTT\n\n" + re.sub(
            r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text
        )
    return Response(text, mimetype="text/vtt; charset=utf-8")
