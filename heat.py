"""影片热度计算：与宿主 MovieHeatService v6 公式保持一致。

宿主热度在入库后由定时任务统一计算；插件在入库前用同一公式做门槛过滤，
避免把低热度影片带进主库。参考值取当前业务库各互动字段的 P99，公式版本
变更时需要同步更新（宿主见 src/service/catalog/movie_heat_service.py）。
"""

from __future__ import annotations

WATCHED_COUNT_REFERENCE = 1308
WANT_WATCH_COUNT_REFERENCE = 4991
COMMENT_COUNT_REFERENCE = 41
SCORE_NUMBER_REFERENCE = 6291
HEAT_SCALE = 3100


def calculate_heat(
    *,
    watched_count: int = 0,
    want_watch_count: int = 0,
    comment_count: int = 0,
    score_number: int = 0,
) -> int:
    """按 v6 公式计算热度，与宿主 SQL ROUND 行为一致（正数 int(x+0.5)）。"""
    normalized_heat = (
        (7.0 / 34.0) * int(watched_count or 0) / WATCHED_COUNT_REFERENCE
        + (5.0 / 34.0) * int(want_watch_count or 0) / WANT_WATCH_COUNT_REFERENCE
        + (17.0 / 34.0) * int(comment_count or 0) / COMMENT_COUNT_REFERENCE
        + (5.0 / 34.0) * int(score_number or 0) / SCORE_NUMBER_REFERENCE
    )
    return int(normalized_heat * HEAT_SCALE + 0.5)


def movie_heat(detail) -> int:
    """从宿主 JavdbMovieDetail 计算热度。"""
    return calculate_heat(
        watched_count=getattr(detail, "watched_count", 0),
        want_watch_count=getattr(detail, "want_watch_count", 0),
        comment_count=getattr(detail, "comment_count", 0),
        score_number=getattr(detail, "score_number", 0),
    )
