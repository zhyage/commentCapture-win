# -*- coding: utf-8 -*-
"""smfetch v1 - 统一 schema (v0.1)

记录模型 + 派生字段计算 + 序列化。
纯逻辑层, 不依赖浏览器/网络, 可单测。
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

SCHEMA_VERSION = "0.1"


# ---------- 记录模型 ----------

@dataclass
class AuthorProfile:
    """作者画像 (采集时点快照)"""
    id: str = ""
    nickname: str = ""
    certification: str | None = None
    signature: str | None = None
    follower_count: int | None = None    # 粉丝数
    following_count: int | None = None   # 关注数
    favoriting_count: int | None = None  # 喜欢数
    total_favorited: int | None = None   # 获赞总数
    aweme_count: int | None = None       # 作品数(详情接口无, 需抓主页)


@dataclass
class Stats:
    """互动统计 (采集时点快照)"""
    likes: int | None = None     # 点赞数
    comments: int | None = None  # 评论数
    shares: int | None = None    # 转发数
    collects: int | None = None  # 收藏数
    recommends: int | None = None


@dataclass
class MediaInfo:
    type: str = "video"
    duration_seconds: float | None = None
    video_file: str | None = None
    size_bytes: int | None = None


@dataclass
class SubtitlesInfo:
    source: str = "whisper"             # whisper | whisper+llm(有修正版时)
    engine: str = "faster-whisper"
    model: str | None = None
    language: str = "zh"
    segments_count: int = 0
    full_text: str = ""
    segments_file: str | None = None
    # 派生: LLM 修正版 (基于文案背景修正专名, 可追溯; 2026-08-28)
    corrected_file: str | None = None   # subtitles.llm.json 路径
    corrected_note: str = ""            # 说明: 依据/模型/不确定性标注
    asr_note: str = ""                  # 自适应说明 (VAD 两遍是否触发)


@dataclass
class CommentsMeta:
    collected_count: int = 0
    platform_total: int | None = None
    coverage_note: str = ""
    file: str | None = None
    # 覆盖率结构化字段 (派生, v1.1)
    top_level_count: int = 0          # 顶层评论数
    reply_count: int = 0              # 楼中楼回复数
    author_reply_count: int = 0       # 作者回复数
    top_level_coverage: float | None = None   # 顶层覆盖率 ≈ 顶层/平台总数


def compute_coverage(records, platform_total: int | None) -> dict:
    """从评论记录(对象或dict)计算覆盖率统计 (纯函数, 可单测)"""
    top = sum(1 for r in records if not _field(r, "parent_id"))
    replies = len(records) - top
    author_replies = sum(1 for r in records if _field(r, "is_author"))
    top_cov = round(top / platform_total, 4) if platform_total else None
    return {"top_level_count": top, "reply_count": replies,
            "author_reply_count": author_replies, "top_level_coverage": top_cov}


@dataclass
class AuthorEngagement:
    """作者互动聚合 (派生)"""
    total_author_replies: int = 0
    replied_comment_count: int = 0
    comments_with_author_reply: list = field(default_factory=list)


@dataclass
class CommentRecord:
    """评论/回复记录 (扁平 + parent_id 树)"""
    comment_id: str = ""
    parent_id: str | None = None          # 楼中楼指向父评论; 顶层 null
    user_id: str | None = None
    user_nickname: str | None = None
    is_author: bool = False               # 事实: 是否视频作者
    text: str = ""
    likes: int = 0
    reply_count: int | None = None
    created_at: str | None = None
    ip_label: str | None = None
    is_hot: bool = False
    # 派生: 作者是否回复过这条评论
    author_replied: bool = False
    author_reply_ids: list = field(default_factory=list)
    author_reply_count: int = 0


@dataclass
class SubtitleRecord:
    index: int = 0
    start: float = 0.0
    end: float = 0.0
    text: str = ""


@dataclass
class VideoRecord:
    """视频主记录"""
    schema_version: str = SCHEMA_VERSION
    platform: str = ""
    platform_item_id: str = ""
    url: str | None = None
    source_short_url: str | None = None
    collected_at: str = ""
    author: AuthorProfile = field(default_factory=AuthorProfile)
    caption: str | None = None
    hashtags: list = field(default_factory=list)
    publish_time: str | None = None
    stats: Stats = field(default_factory=Stats)
    media: MediaInfo = field(default_factory=MediaInfo)
    subtitles: SubtitlesInfo = field(default_factory=SubtitlesInfo)
    comments: CommentsMeta = field(default_factory=CommentsMeta)
    author_engagement: AuthorEngagement = field(default_factory=AuthorEngagement)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoRecord":
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            platform=d.get("platform", ""),
            platform_item_id=d.get("platform_item_id", ""),
            url=d.get("url"),
            source_short_url=d.get("source_short_url"),
            collected_at=d.get("collected_at", ""),
            author=AuthorProfile(**d.get("author", {})),
            caption=d.get("caption"),
            hashtags=d.get("hashtags", []),
            publish_time=d.get("publish_time"),
            stats=Stats(**d.get("stats", {})),
            media=MediaInfo(**d.get("media", {})),
            subtitles=SubtitlesInfo(**d.get("subtitles", {})),
            comments=CommentsMeta(**d.get("comments", {})),
            author_engagement=AuthorEngagement(**d.get("author_engagement", {})),
        )


# ---------- 工具函数 ----------

def parse_hashtags(caption: str | None) -> list:
    """从文案解析话题标签 (#xxx)"""
    import re
    return re.findall(r"#([^\s#]+)", caption or "")


def ts_to_iso(t) -> str | None:
    if not t:
        return None
    return datetime.fromtimestamp(int(t)).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def build_comment_records(raw_comments: dict[str, dict], author_id: str | None) -> list[CommentRecord]:
    """原始评论 dict(cid->item) → CommentRecord 列表, 推导 parent_id 与 is_author"""
    records = []
    for c in raw_comments.values():
        rid = c.get("reply_id") or "0"
        rrid = c.get("reply_to_reply_id") or "0"
        if rrid != "0":
            parent = rrid
        elif rid != "0":
            parent = rid
        else:
            parent = None
        u = c.get("user") or {}
        uid = u.get("uid")
        records.append(CommentRecord(
            comment_id=c.get("cid"),
            parent_id=parent,
            user_id=uid,
            user_nickname=u.get("nickname"),
            is_author=(uid == author_id),
            text=c.get("text") or "",
            likes=c.get("digg_count") or 0,
            reply_count=c.get("reply_comment_total"),
            created_at=ts_to_iso(c.get("create_time")),
            ip_label=c.get("ip_label"),
            is_hot=bool(c.get("is_hot")),
        ))
    return records


def derive_author_replies(records: list[CommentRecord]) -> None:
    """派生: 标记作者回复过的父评论 (原地修改)"""
    by_parent: dict[str, list[str]] = {}
    for r in records:
        if r.is_author and r.parent_id:
            by_parent.setdefault(r.parent_id, []).append(r.comment_id)
    for r in records:
        aids = by_parent.get(r.comment_id)
        if aids:
            r.author_replied = True
            r.author_reply_ids = aids
            r.author_reply_count = len(aids)


def _field(r, name):
    """兼容 CommentRecord 对象与 dict"""
    return r[name] if isinstance(r, dict) else getattr(r, name)


def compute_author_engagement(records) -> AuthorEngagement:
    author_replies = [r for r in records if _field(r, "is_author")]
    parents = sorted({_field(r, "parent_id") for r in author_replies if _field(r, "parent_id")})
    return AuthorEngagement(
        total_author_replies=len(author_replies),
        replied_comment_count=len(parents),
        comments_with_author_reply=parents,
    )


def build_comment_list(raw_comments: dict[str, dict], author_id: str | None) -> list[dict]:
    """供落盘: 完整推导流程"""
    records = build_comment_records(raw_comments, author_id)
    derive_author_replies(records)
    return [asdict(r) for r in records]


def sort_comments(records: list[dict]) -> list[dict]:
    """树序排列: 顶层在前, 递归挂接子回复; 父不在采集内的'孤儿'兜底追加。
    保证所有记录都出现在导出中, 结构信息保留在 parent_id 列。"""
    by_parent: dict = {}
    for r in records:
        by_parent.setdefault(r["parent_id"], []).append(r)
    out: list = []
    seen: set = set()

    def walk(parent):
        for r in by_parent.get(parent, []):
            if r["comment_id"] in seen:
                continue
            seen.add(r["comment_id"])
            out.append(r)
            walk(r["comment_id"])

    walk(None)
    for r in records:                      # 孤儿兜底 (父评论不在采集内)
        if r["comment_id"] not in seen:
            out.append(r)
    return out
