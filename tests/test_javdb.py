from urllib.parse import parse_qs, urlparse

import pytest
from sakuramedia_more_movies.javdb import (
    LatestItem,
    LatestPageError,
    fetch_latest_page,
)


class FakeProvider:
    host = "example.com"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.urls = []

    def request_json(self, method, url, **kwargs):
        self.urls.append((method, url))
        if self.error is not None:
            raise self.error
        return self.payload


def _payload(movies, current_page=1):
    return {"success": 1, "data": {"current_page": current_page, "movies": movies}}


def _movie(jid="id-1", number="abc-001", release="2026-10-01"):
    return {"id": jid, "number": number, "release_date": release}


def test_builds_expected_url_and_parses_items():
    provider = FakeProvider(_payload([_movie()], current_page=2))
    items = fetch_latest_page(provider, 1, 2)
    assert items == [LatestItem("id-1", "ABC-001", "2026-10-01")]

    method, url = provider.urls[0]
    assert method == "GET"
    query = parse_qs(urlparse(url).query)
    assert query["filter_by"] == ["1:t"]
    assert query["sort_by"] == ["release"]
    assert query["order_by"] == ["desc"]
    assert query["page"] == ["2"]
    assert query["limit"] == ["50"]


def test_empty_page_returns_empty_list():
    provider = FakeProvider(_payload([], current_page=1))
    assert fetch_latest_page(provider, 0, 100) == []


def test_none_release_date_is_allowed():
    provider = FakeProvider(_payload([_movie(release=None)]))
    assert fetch_latest_page(provider, 0, 1)[0].release_date is None


def test_non_string_release_date_becomes_none():
    provider = FakeProvider(_payload([_movie(release=20261001)]))
    assert fetch_latest_page(provider, 0, 1)[0].release_date is None


def test_request_error_raises_latest_page_error():
    provider = FakeProvider(error=RuntimeError("boom"))
    with pytest.raises(LatestPageError):
        fetch_latest_page(provider, 0, 1)


@pytest.mark.parametrize(
    "payload",
    [
        {"success": 0, "data": {"current_page": 1, "movies": []}},
        {"success": 1, "data": {"movies": None}},
        {"success": 1, "data": {"current_page": 1, "movies": [_movie(), None]}},
        {"success": 1, "data": {"current_page": 2, "movies": [_movie()]}},
        {"success": 1, "data": {"current_page": 1, "movies": [{"number": "a-1"}]}},
        {"success": 1, "data": {"current_page": 1, "movies": [{"id": "x"}]}},
        {
            "success": 1,
            "data": {"current_page": 1, "movies": [{"id": " ", "number": " "}]},
        },
        {
            "success": 1,
            "data": {
                "current_page": 1,
                "movies": [_movie(jid=f"id-{i}") for i in range(51)],
            },
        },
    ],
)
def test_invalid_payloads_raise(payload):
    with pytest.raises(LatestPageError):
        fetch_latest_page(FakeProvider(payload), 0, 1)
