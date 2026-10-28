# -*- coding: utf-8 -*-
"""指标库 (Metric Registry): 能力边界的唯一真相来源

metrics.yaml 声明指标元数据; stats.py 提供实现。
本模块负责加载/查询/别名解析, 供 verdict(四态判定) 与 cli 使用。
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent      # tool3-analyze/
REGISTRY_FILE = BASE / "metrics.yaml"

# 中文名 → metric_id 别名(便于自由文本/中文需求匹配)
_ALIAS = {
    "回复率": "reply_rate",
    "官方回复率": "reply_rate",
    "回复速度": "reply_speed_p50_min",
    "回复字数": "reply_text_len_avg",
    "粉丝数": "followers",
    "点赞": "likes",
    "点赞数": "likes",
    "评论数": "comments_n",
    "收藏": "collects",
    "转发": "shares",
    "视频时长": "duration_sec",
    "发布时间": "publish_date",
    "文案字数": "caption_len",
    "话题标签": "hashtag_count",
    "覆盖率": "comment_coverage",
    "评论覆盖率": "comment_coverage",
    "评论字数": "comment_len_avg",
    "热评占比": "hot_comment_ratio",
    "地区多样性": "ip_region_entropy",
    "意愿分级": "willingness_level",
    "旅游意愿": "willingness_level",
    "视频类别": "video_category",
    "真实性": "is_authenticity",
    "社会临场感": "is_social_presence",
    "字幕字数": "subtitle_len",
    "播放量": "播放量",
    "距离": "距离目的地",
}


class Registry:
    def __init__(self, path: Path | str | None = None):
        import yaml
        p = Path(path) if path else REGISTRY_FILE
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        self.version = raw.get("version", "0")
        self.metrics = {m["metric_id"]: m for m in (raw.get("metrics") or [])}
        self.not_available = raw.get("not_available") or []

    # --- 查询 ---
    def get(self, metric_id: str) -> dict | None:
        return self.metrics.get(metric_id)

    def resolve(self, name: str) -> str:
        """需求项(可能是中文/别名) → metric_id"""
        if name in self.metrics:
            return name
        return _ALIAS.get(name, name)

    def by_level(self, level: str) -> list:
        return [m for m in self.metrics.values() if m.get("level") == level]

    def v0_metrics(self) -> list:
        return [m for m in self.metrics.values() if m.get("v0")]

    def find_not_available(self, name: str) -> dict | None:
        for item in self.not_available:
            if name == item["requirement"] or name in item["requirement"]:
                return item
        return None

    def summary(self) -> dict:
        from collections import Counter
        c = Counter(m.get("engine") for m in self.metrics.values())
        return {
            "version": self.version,
            "total": len(self.metrics),
            "v0": len(self.v0_metrics()),
            "by_engine": dict(c),
            "by_level": {lv: len(self.by_level(lv)) for lv in ("video", "comment")},
            "not_available": len(self.not_available),
        }
