"""任务进度上报：阶段内按时间节流，开始/结束用 force 立即上报。"""

from __future__ import annotations

import time
from typing import Any


class SyncProgress:
    """单阶段任务的进度适配，向 reporter.progress_callback 发送规范文本。"""

    def __init__(self, reporter, logger, *, throttle_seconds: float = 2.0):
        self.reporter = reporter
        self.logger = logger
        self.throttle_seconds = throttle_seconds
        self._summary: dict[str, Any] = {}
        self._last_emit = float("-inf")
        self._last_log = float("-inf")

    def emit(
        self,
        text: str,
        *,
        current: int = 0,
        total: int = 0,
        summary: dict[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        if summary is not None:
            self._summary = dict(summary)
        now = time.monotonic()
        if not force and now - self._last_emit < self.throttle_seconds:
            return
        self._last_emit = now

        text = text[:255]
        if force or now - self._last_log >= 10:
            self.logger.info(text)
            self._last_log = now

        callback = getattr(self.reporter, "progress_callback", None)
        if callback is None:
            return
        callback(
            {
                "text": text,
                "current": current,
                "total": total,
                "summary_patch": dict(self._summary),
            }
        )
