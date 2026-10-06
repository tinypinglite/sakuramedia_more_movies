from pydantic import BaseModel, ConfigDict, Field


class MoreMoviesSettings(BaseModel):
    """更多影片插件私有配置（plugins.settings.sakuramedia_more_movies）。"""

    model_config = ConfigDict(extra="forbid")

    page_delay_ms: int = Field(default=350, ge=0, title="翻页间隔（毫秒）")
    detail_delay_ms: int = Field(default=0, ge=0, title="详情请求间隔（毫秒）")
    min_heat: int = Field(
        default=100,
        ge=0,
        title="入库热度阈值",
        description="热度低于该值的影片不入库，0 表示不过滤",
    )
