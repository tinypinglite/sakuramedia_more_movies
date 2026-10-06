"""更多影片同步任务：抓 JavDB 最新列表，热度达标且主库缺失的影片入库。

设计要点（与 full_sync_movies 的差异）：
- 单线程顺序执行，无归档层、无图片重试队列、无断点状态；
- 主库查重天然承担"已处理"状态：已入库跳过、低热度下轮重判、失败下轮重试；
- 列表翻到底（接口硬上限 99 页，第 100 页起返回空列表），
  热度阈值可配置（默认 100，0 表示不过滤）；
- 图片下载失败不入库，等下轮自然重试，避免无图影片永久残留。
"""

from __future__ import annotations

import time
from typing import Any

from .heat import movie_heat
from .javdb import MOVIE_TYPES, PAGE_SIZE, LatestPageError, fetch_latest_page
from .progress import SyncProgress
from .settings import MoreMoviesSettings

# 列表接口硬上限 99 页，此值仅作异常保护，正常流程永远到不了。
SAFETY_MAX_PAGES = 200


def _empty_stats() -> dict[str, int]:
    return {
        "pages": 0,
        "scanned": 0,
        "skipped": 0,
        "low_heat": 0,
        "imported": 0,
        "detail_failed": 0,
        "image_failed": 0,
        "import_failed": 0,
        "page_failed": 0,
    }


def _failed_total(stats: dict[str, int]) -> int:
    return stats["detail_failed"] + stats["image_failed"] + stats["import_failed"]


def _existing_numbers(context, numbers: list[str]) -> set[str]:
    """批量查主库已有番号；宿主编号归一化差异由 importer 的存在性兜底。"""
    found = context.movies.find_by_numbers(numbers)
    return {
        str(getattr(snapshot, "values", {}).get("movie_number") or "").upper()
        for snapshot in found
    }


def _process_item(*, provider, importer, config, logger, item, stats) -> None:
    try:
        detail = provider.get_movie_by_javdb_id(item.javdb_id)
    except Exception as exc:
        stats["detail_failed"] += 1
        logger.warning("详情抓取失败 number={} err={}", item.number, exc)
        return

    heat = movie_heat(detail)
    if config.min_heat > 0 and heat < config.min_heat:
        stats["low_heat"] += 1
        return

    # 主项目类型懒 import，避免开发环境静态导入失败。
    from src.plugins.types import ImageDownloadError

    try:
        importer.import_movie_if_missing(detail)
    except ImageDownloadError as exc:
        stats["image_failed"] += 1
        logger.warning(
            "图片下载失败，跳过等下轮重试 number={} err={}", item.number, exc
        )
    except Exception as exc:
        stats["import_failed"] += 1
        logger.warning("入库失败 number={} err={}", item.number, exc)
    else:
        stats["imported"] += 1
        logger.info("已入库 number={} heat={}", item.number, heat)


def _sleep_ms(delay_ms: int) -> None:
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)


def run_sync(config: MoreMoviesSettings, reporter, context) -> dict[str, Any]:
    """入口：APS scheduler / 手动触发调用。返回 stats dict。"""
    logger = context.get_task_logger("more-movies-sync")
    progress = SyncProgress(reporter, logger)
    provider = context.build_javdb_provider()
    importer = context.build_catalog_import_service()
    stats = _empty_stats()

    def summary() -> dict[str, int]:
        return {**stats, "failed": _failed_total(stats)}

    def report(text: str, *, force: bool = False) -> None:
        progress.emit(text, current=stats["scanned"], summary=summary(), force=force)

    report("开始同步 JavDB 最新影片", force=True)
    for movie_type, label in MOVIE_TYPES:
        page = 0
        while True:
            page += 1
            if page > SAFETY_MAX_PAGES:
                logger.warning("超过安全翻页上限 type={} page={}", movie_type, page)
                break
            try:
                items = fetch_latest_page(provider, movie_type, page)
            except LatestPageError as exc:
                stats["page_failed"] += 1
                logger.warning(
                    "列表翻页中断 type={} page={} err={}", movie_type, page, exc
                )
                break
            if not items:
                break
            stats["pages"] += 1

            existing = _existing_numbers(context, [item.number for item in items])
            for item in items:
                stats["scanned"] += 1
                if item.number in existing:
                    stats["skipped"] += 1
                    report(f"{label} 第 {page} 页 · 主库已有 {item.number}")
                    continue
                report(f"{label} 第 {page} 页 · 处理 {item.number}")
                _process_item(
                    provider=provider,
                    importer=importer,
                    config=config,
                    logger=logger,
                    item=item,
                    stats=stats,
                )
                _sleep_ms(config.detail_delay_ms)

            report(
                f"{label} 第 {page} 页完成 · 已入库 {stats['imported']} · "
                f"跳过 {stats['skipped']} · 低热度 {stats['low_heat']}",
            )
            if len(items) < PAGE_SIZE:
                break
            _sleep_ms(config.page_delay_ms)

    final = summary()
    report(
        f"完成 · 检查 {stats['scanned']} 部 · 入库 {stats['imported']} 部 · "
        f"跳过 {stats['skipped']} · 低热度 {stats['low_heat']} · "
        f"失败 {final['failed']} · 图片待补 {stats['image_failed']}",
        force=True,
    )
    logger.info("more_movies sync 完成 stats={}", final)
    return final
