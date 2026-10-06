"""SakuraMedia 更多影片插件入口。"""

from __future__ import annotations

import json
from pathlib import Path

from src.plugins import (
    HOST_API_VERSION,
    PluginContext,
    PluginRegistration,
)
from src.scheduler.contracts import JobDefinition

from .settings import MoreMoviesSettings

__version__ = json.loads(
    Path(__file__).with_name("manifest.json").read_text(encoding="utf-8")
)["version"]
PLUGIN_ID = "sakuramedia_more_movies"
DISPLAY_NAME = "SakuraMedia 更多影片"


def register(context: PluginContext) -> PluginRegistration:
    """声明最新影片同步任务；加载阶段只做装配，不发网络请求。"""
    settings = MoreMoviesSettings.model_validate(dict(context.settings))

    def sync_handler(reporter, _params):
        from .sync import run_sync

        return run_sync(settings, reporter, context)

    return PluginRegistration(
        plugin_id=PLUGIN_ID,
        display_name=DISPLAY_NAME,
        version=__version__,
        host_api_version=HOST_API_VERSION,
        jobs=(
            JobDefinition(
                task_key=f"{PLUGIN_ID}_sync",
                log_name="more-movies-sync",
                cli_name="sync-more-movies",
                cli_help="抓取 JavDB 最新影片，热度达标且主库缺失的入库",
                default_cron="0 6 * * *",
                handler=sync_handler,
            ),
        ),
    )
