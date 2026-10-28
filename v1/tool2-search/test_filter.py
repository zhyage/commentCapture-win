# -*- coding: utf-8 -*-
"""工具2 纯逻辑测试: 解析器 + 硬过滤器"""
import pathlib
import tempfile

import pytest

from smsearch.filter import hard_filter, sort_hits_by_likes
from smsearch.parser import load_request


def _tmp_yaml(content):
    f = pathlib.Path(tempfile.mktemp(suffix=".yaml"))
    f.write_text(content, encoding="utf-8")
    return f


def test_parser_describe_becomes_intents_not_keywords():
    f = _tmp_yaml("keywords: [红河文旅]\ndescribe: 景点介绍, 景点推荐\nmin_likes: 10000\nsort: likes\n")
    req = load_request(f)
    f.unlink()
    assert req["keywords"] == ["红河文旅"]          # describe 不进关键词
    assert req["intents"] == ["景点介绍", "景点推荐"]  # 进意图列表
    assert req["filters"]["min_likes"] == 10000
    assert req["sort"] == "likes"


def test_parser_empty_keywords():
    f = _tmp_yaml("min_likes: 1\n")
    with pytest.raises(ValueError):
        load_request(f)
    f.unlink()


def test_parser_authors_string():
    f = _tmp_yaml("keywords: [a]\nauthors: 红河文旅\n")
    req = load_request(f)
    f.unlink()
    assert req["filters"]["authors"] == ["红河文旅"]


def test_parser_douyin_id_string():
    f = _tmp_yaml("douyin_id: 55008743593\nmin_likes: 1000\n")
    req = load_request(f)
    f.unlink()
    assert req["douyin_ids"] == ["55008743593"]
    assert req["keywords"] == []
    assert req["filters"]["min_likes"] == 1000


def test_parser_douyin_id_list():
    f = _tmp_yaml("douyin_id: [55008743593, 12345]\n")
    req = load_request(f)
    f.unlink()
    assert req["douyin_ids"] == ["55008743593", "12345"]


def test_parser_keywords_and_douyin_id_conflict():
    f = _tmp_yaml("keywords: [云南文旅]\ndouyin_id: 55008743593\n")
    with pytest.raises(ValueError, match="不能同时"):
        load_request(f)
    f.unlink()


def _item(aid, desc, author, likes, ct=1787643036):
    return {"aweme_id": aid, "desc": desc, "author": {"nickname": author},
            "statistics": {"digg_count": likes, "comment_count": 1}, "create_time": ct}


def test_hard_filter_basic():
    ok, matched = hard_filter(
        _item("1", "红河文旅欢迎你", "红河文旅", 20000),
        {"min_likes": 10000, "authors": ["红河文旅"], "after": None,
         "before": None, "min_comments": None})
    assert ok and "min_likes" in matched and "authors" in matched

    ok2, _ = hard_filter(
        _item("2", "别的内容", "其他号", 500),
        {"min_likes": 10000, "authors": ["红河文旅"], "after": None,
         "before": None, "min_comments": None})
    assert not ok2


def test_hard_filter_matched_only_when_set():
    # 没设 min_comments → matched 里不应出现
    ok, matched = hard_filter(
        _item("1", "kw", "x", 1),
        {"min_likes": None, "authors": None, "after": None,
         "before": None, "min_comments": None})
    assert ok
    assert matched == []          # 无任何过滤设置 → 全通过且无匹配项


def test_keywords_not_topic_filter():
    # keywords 只做搜索词, 不做主题硬过滤: 文案不含关键词也通过硬过滤
    ok, matched = hard_filter(
        _item("1", "红河牛牛跳舞名场面", "红河文旅", 1957),
        {"min_likes": 1000, "authors": ["红河文旅"], "after": None,
         "before": None, "min_comments": None})
    assert ok
    assert "topic" not in matched


def test_hard_filter_time():
    ok, _ = hard_filter(
        _item("1", "kw", "x", 1, ct=1787643036),   # 2026-08-25
        {"min_likes": None, "authors": None, "after": "2027-01-01",
         "before": None, "min_comments": None})
    assert not ok


def test_sort_hits_by_likes():
    hits = [
        {"aweme": _item("1", "a", "x", 100), "matched": [], "semantic": "符合"},
        {"aweme": _item("2", "b", "x", 9999), "matched": [], "semantic": "符合"},
        {"aweme": _item("3", "c", "x", 50), "matched": [], "semantic": "符合"},
    ]
    out = sort_hits_by_likes(hits)
    assert [r["aweme"]["aweme_id"] for r in out] == ["2", "1", "3"]
