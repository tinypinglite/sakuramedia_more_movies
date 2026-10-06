"""sync 主流程单元测试：使用假 provider/importer/context，不依赖网络与数据库。"""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from sakuramedia_more_movies.settings import MoreMoviesSettings
from sakuramedia_more_movies.sync import run_sync

from src.plugins.types import ImageDownloadError


class FakeReporter:
    def __init__(self):
        self.payloads = []

    def progress_callback(self, payload):
        self.payloads.append(payload)


class FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, message, *args):
        self.records.append(("info", message, args))

    def warning(self, message, *args):
        self.records.append(("warning", message, args))


class FakeProvider:
    host = "example.com"

    def __init__(self, pages, details=None, detail_error=None):
        self.pages = pages
        self.details = details or {}
        self.detail_error = detail_error
        self.list_calls = []
        self.detail_calls = []

    def request_json(self, method, url, **kwargs):
        query = parse_qs(urlparse(url).query)
        movie_type = int(query["filter_by"][0].split(":")[0])
        page = int(query["page"][0])
        self.list_calls.append((movie_type, page))
        result = self.pages.get((movie_type, page))
        if result is None:
            return _list_payload([], page=1)
        if isinstance(result, Exception):
            raise result
        return result

    def get_movie_by_javdb_id(self, javdb_id):
        self.detail_calls.append(javdb_id)
        if self.detail_error is not None:
            raise self.detail_error
        result = self.details.get(javdb_id)
        if isinstance(result, Exception):
            raise result
        return result


class FakeDetail:
    def __init__(self, number, watched=1308, want=4991, comment=41, score=6291):
        self.movie_number = number
        self.watched_count = watched
        self.want_watch_count = want
        self.comment_count = comment
        self.score_number = score


class FakeImporter:
    def __init__(self, errors=None):
        self.errors = errors or {}
        self.imported = []

    def import_movie_if_missing(self, detail):
        self.imported.append(detail.movie_number)
        error = self.errors.get(detail.movie_number)
        if error is not None:
            raise error
        return (None, True)


class FakeMoviesApi:
    def __init__(self, existing=()):
        self.existing = {number.upper() for number in existing}
        self.queries = []

    def find_by_numbers(self, numbers):
        self.queries.append(list(numbers))
        return [
            SimpleNamespace(values={"movie_number": number.upper()})
            for number in numbers
            if number.upper() in self.existing
        ]


class FakeContext:
    def __init__(self, provider, importer, existing=()):
        self.provider = provider
        self.importer = importer
        self.movies = FakeMoviesApi(existing)
        self.logger = FakeLogger()

    def get_task_logger(self, name):
        return self.logger

    def build_javdb_provider(self):
        return self.provider

    def build_catalog_import_service(self):
        return self.importer


def _list_payload(movies, page=1):
    return {"success": 1, "data": {"current_page": page, "movies": movies}}


def _movie(jid, number):
    return {"id": jid, "number": number, "release_date": "2026-10-01"}


def _full_page(page=1):
    return _list_payload(
        [_movie(f"id-{i}", f"NUM-{i:04d}") for i in range(50)], page=page
    )


def _run(
    pages,
    *,
    details=None,
    existing=(),
    min_heat=100,
    detail_error=None,
    errors=None,
):
    provider = FakeProvider(pages, details=details, detail_error=detail_error)
    importer = FakeImporter(errors=errors)
    context = FakeContext(provider, importer, existing=existing)
    config = MoreMoviesSettings(page_delay_ms=0, detail_delay_ms=0, min_heat=min_heat)
    reporter = FakeReporter()
    stats = run_sync(config, reporter, context)
    return stats, provider, importer, reporter


def test_skips_existing_without_detail_request():
    stats, provider, importer, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        existing=["ABC-001"],
    )
    assert stats["scanned"] == 1
    assert stats["skipped"] == 1
    assert stats["imported"] == 0
    assert provider.detail_calls == []
    assert importer.imported == []


def test_imports_new_movie_with_hot_enough_heat():
    stats, provider, importer, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "abc-001")])},
        details={"id-1": FakeDetail("ABC-001")},
    )
    assert stats["imported"] == 1
    assert stats["failed"] == 0
    assert provider.detail_calls == ["id-1"]
    assert importer.imported == ["ABC-001"]


def test_low_heat_is_not_imported():
    stats, _, importer, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        details={"id-1": FakeDetail("ABC-001", watched=0, want=0, comment=0, score=0)},
    )
    assert stats["low_heat"] == 1
    assert stats["imported"] == 0
    assert importer.imported == []


def test_min_heat_zero_imports_low_heat_movie():
    stats, _, importer, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        details={"id-1": FakeDetail("ABC-001", watched=0, want=0, comment=0, score=0)},
        min_heat=0,
    )
    assert stats["imported"] == 1
    assert importer.imported == ["ABC-001"]


def test_image_download_failure_skips_and_waits_next_round():
    stats, _, _, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        details={"id-1": FakeDetail("ABC-001")},
        errors={"ABC-001": ImageDownloadError("image boom")},
    )
    assert stats["image_failed"] == 1
    assert stats["import_failed"] == 0
    assert stats["imported"] == 0
    assert stats["failed"] == 1


def test_import_failure_is_recorded():
    stats, _, _, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        details={"id-1": FakeDetail("ABC-001")},
        errors={"ABC-001": RuntimeError("db boom")},
    )
    assert stats["import_failed"] == 1
    assert stats["imported"] == 0


def test_detail_failure_is_recorded():
    stats, _, importer, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        detail_error=RuntimeError("net boom"),
    )
    assert stats["detail_failed"] == 1
    assert importer.imported == []


def test_full_page_continues_and_empty_page_stops():
    stats, provider, _, _ = _run(
        {(0, 1): _full_page(1), (0, 2): _list_payload([], page=1)},
        existing=[f"NUM-{i:04d}" for i in range(50)],
    )
    assert (0, 1) in provider.list_calls
    assert (0, 2) in provider.list_calls
    assert (0, 3) not in provider.list_calls
    assert stats["pages"] == 1
    assert stats["skipped"] == 50


def test_short_page_stops_type_without_next_request():
    stats, provider, _, _ = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        existing=["ABC-001"],
    )
    assert (0, 2) not in provider.list_calls
    assert (1, 1) in provider.list_calls
    assert (3, 1) in provider.list_calls
    assert stats["pages"] == 1


def test_page_error_stops_type_and_continues_next_type():
    stats, provider, _, _ = _run({(0, 1): RuntimeError("list boom")})
    assert stats["page_failed"] == 1
    assert provider.list_calls == [(0, 1), (1, 1), (3, 1)]


def test_safety_max_pages_guard(monkeypatch):
    from sakuramedia_more_movies import sync as sync_module

    monkeypatch.setattr(sync_module, "SAFETY_MAX_PAGES", 2)
    _, provider, _, _ = _run(
        {(0, 1): _full_page(1), (0, 2): _full_page(2)},
        existing=[f"NUM-{i:04d}" for i in range(50)],
    )
    assert (0, 1) in provider.list_calls
    assert (0, 2) in provider.list_calls
    assert (0, 3) not in provider.list_calls


def test_reports_final_progress():
    stats, _, _, reporter = _run(
        {(0, 1): _list_payload([_movie("id-1", "ABC-001")])},
        details={"id-1": FakeDetail("ABC-001")},
    )
    assert stats["imported"] == 1
    assert reporter.payloads
    assert "完成" in reporter.payloads[-1]["text"]
    assert reporter.payloads[-1]["summary_patch"]["imported"] == 1
