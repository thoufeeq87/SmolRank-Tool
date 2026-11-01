from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ChannelResult:
    rank: int
    video_title: str
    channel_title: str
    subscriber_count: int
    view_count: int = 0
    published_date: str = ""
    reach_multiplier: float = 0.0
    is_outlier: bool = False
    is_outdated: bool = False
    is_small: bool = False  # computed locally against our own threshold


@dataclass(frozen=True)
class WinnabilityResult:
    keyword: str
    threshold: int
    winnable: bool
    results: list = field(default_factory=list)
    small_channels: list = field(default_factory=list)
    freshness_opportunity: bool = False
    suggestions: list = field(default_factory=list)

    @property
    def total(self):
        return len(self.results)

    def to_dict(self):
        data = asdict(self)
        data["total"] = self.total
        return data
