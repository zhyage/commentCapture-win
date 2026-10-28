# -*- coding: utf-8 -*-
"""export 层测试: CSV 导出 (中文/emoji 编码)"""
import csv
import json
from pathlib import Path

from smfetch import schema as S
from smfetch.export import comments_to_csv, video_summary_csv


def _build_records(raw_comments, author_id):
    records = S.build_comment_records(raw_comments, author_id)
    S.derive_author_replies(records)
    return [S.asdict(r) for r in records]


def test_comments_csv_encoding_and_order(raw_comments, author_id, tmp_path):
    records = _build_records(raw_comments, author_id)
    out = tmp_path / "comments.csv"
    comments_to_csv(records, out)
    text = out.read_text(encoding="utf-8-sig")
    assert "红河文旅" in text                       # 中文
    assert "限量版👧🏾小乖乖。" in text                # emoji
    # 行数 = 表头 + 322
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 322
    assert rows[0]["comment_id"] == "7447168094362059574"
    assert rows[0]["is_author"] == "0"
    # 顶层在前
    assert rows[0]["parent_id"] == ""


def test_comments_csv_author_rows(raw_comments, author_id, tmp_path):
    records = _build_records(raw_comments, author_id)
    out = tmp_path / "c.csv"
    comments_to_csv(records, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    author_rows = [r for r in rows if r["is_author"] == "1"]
    assert len(author_rows) == 25
    assert author_rows[0]["user_nickname"] == "红河文旅"
    assert author_rows[0]["parent_id"]  # 作者回复必有父


def test_video_summary_csv(tmp_path):
    v = S.VideoRecord(platform="douyin", platform_item_id="1",
                      author=S.AuthorProfile(nickname="红河文旅", follower_count=151005,
                                             total_favorited=3881508),
                      caption="有\n换行", stats=S.Stats(likes=1),
                      comments=S.CommentsMeta(collected_count=5))
    out = tmp_path / "videos.csv"
    video_summary_csv([v.to_dict()], out)
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 1
    assert rows[0]["author_nickname"] == "红河文旅"
    assert rows[0]["stats_likes"] == "1"
    assert "换行" in rows[0]["caption"]            # 换行被替换为空格
