"""影片互动接口：评分 / 想看清单 / 相关推荐（挂在 /api/videos 下）

与收藏相互独立：收藏是「已收」，评分是量化评价，想看是未来意向。
三者都按用户存储，同一部影片对不同用户互不影响。
复用 videos.py 的序列化链路，避免重复实现可见性之外的字段映射。
"""
from flask import Blueprint, g, request

import db
from auth import require_login, visible_sql
from responses import fail, ok

from .videos import (
    _SELECT_VIDEO,
    attach_engagement,
    attach_favorites,
    serialize_video,
)

bp = Blueprint("engagement", __name__, url_prefix="/api/videos")


def _visible_video(video_id):
    """只接受「当前用户可见且已过审」的影片；不可见时统一按 404 处理"""
    vis_sql, vis_args = visible_sql(g.user)
    return db.query(
        f"SELECT v.id, v.title, v.type_id, v.collection_id FROM videos v "
        f"WHERE v.id = %s AND ({vis_sql}) AND v.audit_status = 1",
        (video_id, *vis_args),
        one=True,
    )


def _stats(video_id):
    """某部影片的评分统计 + 当前用户的评分与想看状态"""
    agg = db.query(
        "SELECT ROUND(AVG(score), 1) AS avg_score, COUNT(*) AS rating_count "
        "FROM video_ratings WHERE video_id = %s",
        (video_id,),
        one=True,
    )
    mine = db.query(
        "SELECT score FROM video_ratings WHERE user_id = %s AND video_id = %s",
        (g.user["id"], video_id),
        one=True,
    )
    wanted = db.query(
        "SELECT 1 FROM video_watchlist WHERE user_id = %s AND video_id = %s",
        (g.user["id"], video_id),
        one=True,
    )
    return {
        "avgScore": float(agg["avg_score"]) if agg and agg["avg_score"] is not None else 0,
        "ratingCount": (agg["rating_count"] if agg else 0) or 0,
        "myScore": mine["score"] if mine else 0,
        "isWantToWatch": bool(wanted),
    }


@bp.get("/<int:video_id>/engagement")
@require_login
def engagement(video_id):
    """详情页加载时拉取评分与想看状态"""
    if not _visible_video(video_id):
        return fail("影片不存在或不可见", 404)
    return ok(_stats(video_id))


@bp.put("/<int:video_id>/rating")
@require_login
def rate_video(video_id):
    """打分 1~5；传 0 表示撤销评分（不是打 0 星）"""
    if not _visible_video(video_id):
        return fail("影片不存在或不可见", 404)
    data = request.get_json(silent=True) or {}
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 5:
        return fail("评分需为 0~5 的整数（0 表示撤销评分）")
    if score == 0:
        db.execute(
            "DELETE FROM video_ratings WHERE user_id = %s AND video_id = %s",
            (g.user["id"], video_id),
        )
    else:
        db.execute(
            "INSERT INTO video_ratings (user_id, video_id, score) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE score = VALUES(score)",
            (g.user["id"], video_id, score),
        )
    return ok(_stats(video_id))


@bp.post("/<int:video_id>/watchlist")
@require_login
def toggle_watchlist(video_id):
    """切换「想看」状态，语义与收藏的 toggle 一致"""
    if not _visible_video(video_id):
        return fail("影片不存在或不可见", 404)
    exists = db.query(
        "SELECT 1 FROM video_watchlist WHERE user_id = %s AND video_id = %s",
        (g.user["id"], video_id),
        one=True,
    )
    if exists:
        db.execute(
            "DELETE FROM video_watchlist WHERE user_id = %s AND video_id = %s",
            (g.user["id"], video_id),
        )
        wanted = False
    else:
        db.execute(
            "INSERT IGNORE INTO video_watchlist (user_id, video_id) VALUES (%s, %s)",
            (g.user["id"], video_id),
        )
        wanted = True
    return ok({**_stats(video_id), "isWantToWatch": wanted})


@bp.get("/<int:video_id>/recommendations")
@require_login
def recommendations(video_id):
    """「看了这个也看」：标签重合度 ×3 + 同类型 ×2 + 同合集 ×2，热度兜底。

    候选限定为当前用户可见且已过审的影片；无标签时仍能按类型 / 合集 / 热度给出结果。
    """
    target = _visible_video(video_id)
    if not target:
        return fail("影片不存在或不可见", 404)
    limit = min(max(request.args.get("limit", 8, type=int) or 8, 1), 20)
    tag_ids = [
        r["tag_id"] for r in db.query(
            "SELECT tag_id FROM video_tags WHERE video_id = %s", (video_id,)
        )
    ]
    tag_in = ",".join(["%s"] * len(tag_ids)) if tag_ids else "NULL"
    vis_sql, vis_args = visible_sql(g.user)
    candidates = db.query(
        f"""SELECT v.id,
                   (SELECT COUNT(*) FROM video_tags vt
                    WHERE vt.video_id = v.id AND vt.tag_id IN ({tag_in})) AS tag_hits,
                   (CASE WHEN %s IS NOT NULL AND v.type_id = %s THEN 1 ELSE 0 END) AS type_hit,
                   (CASE WHEN %s IS NOT NULL AND v.collection_id = %s THEN 1 ELSE 0 END) AS collection_hit
            FROM videos v
            WHERE v.id <> %s AND v.audit_status = 1 AND ({vis_sql})
            ORDER BY (tag_hits * 3 + type_hit * 2 + collection_hit * 2) DESC,
                     v.view_count DESC, v.id DESC
            LIMIT %s""",
        (
            *tag_ids,
            target["type_id"], target["type_id"],
            target["collection_id"], target["collection_id"],
            video_id, *vis_args, limit,
        ),
    )
    if not candidates:
        return ok({"items": []})

    def reason_of(row):
        if row["tag_hits"]:
            return f"共同标签 {row['tag_hits']} 个"
        if row["collection_hit"]:
            return "同一合集"
        if row["type_hit"]:
            return "同类型影片"
        return "热门影片"

    reasons = {row["id"]: reason_of(row) for row in candidates}
    ids = [row["id"] for row in candidates]
    placeholders = ",".join(["%s"] * len(ids))
    rows = db.query(
        f"{_SELECT_VIDEO} WHERE v.id IN ({placeholders}) GROUP BY v.id", ids
    )
    by_id = {r["id"]: r for r in rows}
    items = attach_engagement(attach_favorites([
        serialize_video(by_id[i]) for i in ids if i in by_id
    ]))
    for item in items:
        item["recommendReason"] = reasons.get(item["id"], "")
    return ok({"items": items})
