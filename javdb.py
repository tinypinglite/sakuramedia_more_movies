"""JavDB 最新影片列表抓取与校验。

列表接口 `/api/v1/movies/tags`：
- `filter_by={type}:t` 只按影片类型过滤，不传月份即返回按发行日期倒序的最新列表；
- 每页固定 50 条，接口硬上限 99 页（第 100 页起返回空列表）；
- 请求走宿主 JavdbProvider，复用其签名头、超时与重试。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlencode

PAGE_SIZE = 50

# (JavDB filter type, 展示名) —— 0 有码 / 1 无码 / 3 FC2
MOVIE_TYPES: tuple[tuple[int, str], ...] = ((0, "有码"), (1, "无码"), (3, "FC2"))


@dataclass(frozen=True)
class LatestItem:
    javdb_id: str
    number: str
    release_date: str | None


class LatestPageError(RuntimeError):
    """列表请求失败或响应结构不合法，本轮停止该类型。"""


def fetch_latest_page(provider, movie_type: int, page: int) -> list[LatestItem]:
    """读取某类型的一页最新列表；请求或结构错误抛 LatestPageError，不当作空页。"""
    params = {
        "filter_by": f"{movie_type}:t",
        "sort_by": "release",
        "order_by": "desc",
        "page": page,
        "limit": PAGE_SIZE,
    }
    url = f"https://{provider.host}/api/v1/movies/tags?{urlencode(params, quote_via=quote, safe=':-')}"
    try:
        payload = provider.request_json("GET", url)
    except Exception as exc:
        raise LatestPageError(
            f"列表请求失败 type={movie_type} page={page}: {exc}"
        ) from exc

    if not isinstance(payload, dict) or payload.get("success") != 1:
        raise LatestPageError(f"列表响应 success!=1 type={movie_type} page={page}")
    data = payload.get("data")
    movies = data.get("movies") if isinstance(data, dict) else None
    if not isinstance(movies, list) or len(movies) > PAGE_SIZE:
        raise LatestPageError(f"列表响应 movies 结构错误 type={movie_type} page={page}")
    if movies and data.get("current_page") != page:
        raise LatestPageError(
            f"列表返回页码与请求不一致 type={movie_type} page={page}"
            f" current_page={data.get('current_page')}"
        )

    items: list[LatestItem] = []
    for movie in movies:
        if not isinstance(movie, dict):
            raise LatestPageError(f"列表影片项不是对象 type={movie_type} page={page}")
        javdb_id = movie.get("id")
        number = movie.get("number")
        if not isinstance(javdb_id, str) or not javdb_id.strip():
            raise LatestPageError(f"列表影片缺少 ID type={movie_type} page={page}")
        if not isinstance(number, str) or not number.strip():
            raise LatestPageError(f"列表影片缺少番号 type={movie_type} page={page}")
        release_date = movie.get("release_date")
        items.append(
            LatestItem(
                javdb_id=javdb_id.strip(),
                number=number.strip().upper(),
                release_date=release_date if isinstance(release_date, str) else None,
            )
        )
    return items
