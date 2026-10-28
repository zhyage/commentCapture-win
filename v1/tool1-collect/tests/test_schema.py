# -*- coding: utf-8 -*-
"""schema 层黄金数据测试: 用真实抖音数据验证字段映射与派生逻辑"""
from smfetch import schema as S


# ---------- 作者画像 ----------

def test_author_profile_fields(raw_detail):
    a = raw_detail["aweme"]["author"]
    profile = S.AuthorProfile(
        id=a.get("uid"), nickname=a.get("nickname"),
        certification=(__import__("json").loads(a.get("account_cert_info") or "{}") or {}).get("label_text"),
        signature=a.get("signature"),
        follower_count=a.get("follower_count"),
        following_count=a.get("following_count"),
        favoriting_count=a.get("favoriting_count"),
        total_favorited=a.get("total_favorited"),
        aweme_count=a.get("aweme_count"),
    )
    assert profile.nickname == "红河文旅"
    assert profile.follower_count == 151005          # 粉丝数
    assert profile.favoriting_count == 1163          # 喜欢数
    assert profile.total_favorited == 3881508        # 获赞总数
    assert profile.following_count == 0              # 关注数
    assert "红河哈尼族彝族自治州" in (profile.certification or "")


def test_stats_mapping(raw_detail):
    st = raw_detail["aweme"]["statistics"]
    stats = S.Stats(likes=st["digg_count"], comments=st["comment_count"],
                    shares=st["share_count"], collects=st["collect_count"],
                    recommends=st.get("recommend_count"))
    assert stats.likes == 11566
    assert stats.comments == 1937
    assert stats.shares == 548
    assert stats.collects == 243


def test_publish_time(raw_detail):
    t = S.ts_to_iso(raw_detail["aweme"]["create_time"])
    assert t == "2024-12-11T22:37:14+08:00"


def test_hashtags(raw_detail):
    tags = S.parse_hashtags(raw_detail["aweme"]["desc"])
    assert tags == ["交警小熊", "文明交通携手共创", "云南交警", "红河旅游推荐官", "这里是红河"]


# ---------- 评论: parent_id 推导 ----------

def test_comment_counts(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    assert len(records) == 322
    replies = [r for r in records if r.parent_id]
    assert len(replies) == 68           # 楼中楼回复
    author_replies = [r for r in records if r.is_author]
    assert len(author_replies) == 25    # 作者回复


def test_parent_derivation(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    by_id = {r.comment_id: r for r in records}
    # 已知样本: 作者回复 "别想了..." (文本以表情开头, 用 in 匹配)
    author_reply = next(r for r in records if r.is_author and "别想了" in r.text)
    assert author_reply.parent_id == "7447168094362059574"
    parent = by_id[author_reply.parent_id]
    assert parent.text.startswith("红红，你告诉我要怎样才能得到王楚钦")
    assert parent.user_nickname == "限量版👧🏾小乖乖。"


# ---------- 作者互动派生 ----------

def test_author_replied_derivation(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    S.derive_author_replies(records)
    replied = [r for r in records if r.author_replied]
    # 25 条作者回复中, 2 条指向采集外的父评论 → 采集内可标记 23 条
    assert len(replied) == 23
    top = next(r for r in replied if r.comment_id == "7447168094362059574")
    assert top.author_reply_count == 1
    assert len(top.author_reply_ids) == 1


def test_author_engagement(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    S.derive_author_replies(records)
    eng = S.compute_author_engagement(records)
    assert eng.total_author_replies == 25
    assert eng.replied_comment_count == 25
    assert "7447168094362059574" in eng.comments_with_author_reply


# ---------- 序列化 round-trip ----------

def test_video_record_roundtrip(raw_detail):
    v = S.VideoRecord(platform="douyin", platform_item_id="7447163286870707508",
                      author=S.AuthorProfile(id="405032890799566", nickname="红河文旅"))
    d = v.to_dict()
    v2 = S.VideoRecord.from_dict(d)
    assert v2.platform == "douyin"
    assert v2.author.nickname == "红河文旅"


# ---------- 字幕 ----------

def test_subtitle_segments(raw_subtitles):
    segs = [S.SubtitleRecord(index=i + 1, start=s["start"], end=s["end"], text=s["text"])
            for i, s in enumerate(raw_subtitles)]
    assert len(segs) == 13
    assert segs[0].text == "大家好 我是洪大勇"
    assert segs[0].start < segs[1].start


# ---------- 覆盖率 (v1.1) ----------

def test_compute_coverage(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    cov = S.compute_coverage(records, 1937)
    assert cov["top_level_count"] == 254
    assert cov["reply_count"] == 68
    assert cov["author_reply_count"] == 25
    assert abs(cov["top_level_coverage"] - 254 / 1937) < 1e-4


def test_compute_coverage_none_total(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    cov = S.compute_coverage(records, None)
    assert cov["top_level_coverage"] is None


def test_comments_meta_roundtrip_with_coverage():
    m = S.CommentsMeta(collected_count=322, platform_total=1937,
                       top_level_count=254, reply_count=68,
                       author_reply_count=25, top_level_coverage=0.1311)
    d = m.__dict__
    m2 = S.CommentsMeta(**d)
    assert m2.top_level_count == 254
    assert m2.top_level_coverage == 0.1311
