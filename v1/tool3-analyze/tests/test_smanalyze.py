# -*- coding: utf-8 -*-
"""工具3 纯逻辑单测: 百分位/熵/指标计算/四态判定 (无网络)"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smanalyze import stats
from smanalyze.registry import Registry
from smanalyze.verdict import DONE, IMPOSSIBLE, NEED_COLLECT, PARTIAL, judge, judge_all


# ---------- 纯函数 ----------
def test_percentile_basic():
    vals = [1, 2, 3, 4, 5]
    assert stats.percentile(vals, 0.0) == 1.0
    assert stats.percentile(vals, 0.5) == 3.0
    assert stats.percentile(vals, 1.0) == 5.0


def test_percentile_interpolates():
    # 4 个值, p50 落在 2 与 3 之间 → 2.5
    assert stats.percentile([1, 2, 3, 4], 0.5) == 2.5


def test_percentile_edge_cases():
    assert stats.percentile([], 0.5) is None
    assert stats.percentile([7], 0.9) == 7.0


def test_percentile_long_tail_vs_mean():
    """长尾数据: 均值被拉高, 分位更稳健 (DESIGN 教训2)"""
    vals = sorted([1, 1, 2, 2, 3, 10, 500])          # 一个极端值
    mean = sum(vals) / len(vals)
    assert mean > 70                                   # 均值被 500 拉高
    assert stats.percentile(vals, 0.5) == 2.0          # 中位仍反映典型值
    assert stats.percentile(vals, 0.9) > 100           # p90 捕捉尾部


def test_entropy():
    assert stats.entropy([]) is None
    assert stats.entropy(["A", "A", "A"]) == 0.0       # 单一地区 → 熵 0
    assert stats.entropy(["A", "B"]) > 0.6             # 均匀分布 → 熵高


def test_flatten():
    assert stats.flatten("a\nb\r\nc") == "a b c"
    assert len(stats.flatten("x" * 200, limit=10)) == 10


def test_parse_dt():
    assert stats.parse_dt("2024-05-14T18:43:00+08:00") is not None
    assert stats.parse_dt(None) is None
    assert stats.parse_dt("garbage") is None


# ---------- 指标计算 (构造 fixture) ----------
def _make_video(tmp_path: Path, with_reply=True):
    d = tmp_path / "vid1"
    d.mkdir()
    rec = {
        "platform_item_id": "vid1", "caption": "测试文案@某人 #话题",
        "hashtags": ["话题"], "publish_time": "2024-05-14T18:43:00+08:00",
        "author": {"nickname": "测试号", "follower_count": 100,
                   "certification": "官方", "signature": "签名"},
        "stats": {"likes": 1000, "comments": 10, "collects": 5, "shares": 3},
        "media": {"duration_seconds": 30.0},
        "subtitles": {"full_text": "abc", "segments_count": 2, "source": "whisper"},
        "comments": {"collected_count": 3, "platform_total": 10,
                     "top_level_coverage": 0.3},
        "author_engagement": {"replied_comment_count": 1},
    }
    (d / "video.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    comments = [
        {"comment_id": "c1", "parent_id": None, "is_author": False, "text": "好想去",
         "likes": 5, "created_at": "2024-05-14T20:00:00+08:00", "ip_label": "云南",
         "is_hot": True, "author_replied": with_reply},
        {"comment_id": "c2", "parent_id": None, "is_author": False, "text": "太美了?",
         "likes": 1, "created_at": "2024-05-20T20:00:00+08:00", "ip_label": "广东",
         "is_hot": False, "author_replied": False},
    ]
    if with_reply:
        comments.append(
            {"comment_id": "r1", "parent_id": "c1", "is_author": True, "text": "欢迎来玩😀",
             "likes": 0, "created_at": "2024-05-14T20:30:00+08:00", "ip_label": "云南",
             "is_hot": False, "author_replied": False})
    (d / "comments.json").write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")
    return d


def test_video_metrics_basic(tmp_path):
    d = _make_video(tmp_path)
    m = stats.video_metrics(d)
    assert m["video_id"] == "vid1"
    assert m["likes"] == 1000
    assert m["engage_ratio"] == 0.01
    assert m["caption_len"] == len("测试文案@某人 #话题")
    assert m["mention_count"] == 1
    assert m["hashtag_count"] == 1
    assert m["comment_coverage"] == 0.3
    assert m["is_verified"] is True


def test_video_metrics_reply_rate_and_speed(tmp_path):
    d = _make_video(tmp_path)
    m = stats.video_metrics(d)
    # 顶层 2 条, 其中 1 条被作者回复 → 0.5
    assert m["reply_rate"] == 0.5
    assert m["author_reply_n"] == 1
    # 回复发生在评论后 30 分钟
    assert m["reply_speed_p50_min"] == 30.0
    assert m["reply_speed_p25_min"] == 30.0


def test_video_metrics_no_author_reply(tmp_path):
    d = _make_video(tmp_path, with_reply=False)
    m = stats.video_metrics(d)
    assert m["author_reply_n"] == 0
    assert m["reply_rate"] == 0.0
    assert m["reply_speed_p50_min"] is None      # 无配对样本 → None, 不编造


def test_comment_metrics(tmp_path):
    d = _make_video(tmp_path)
    rows = stats.comment_metrics(d)
    assert len(rows) == 3
    top = [r for r in rows if r["level"] == "顶层"]
    assert len(top) == 2
    assert any(r["is_author_reply"] for r in rows)
    # 问句识别
    assert any(r["is_question"] for r in rows)
    # hours_since_publish: c1 在发布后 ~1.3 小时
    c1 = next(r for r in rows if r["comment_id"] == "c1")
    assert 1.0 < c1["hours_since_publish"] < 2.0


# ---------- 四态判定 ----------
@pytest.fixture(scope="module")
def reg():
    return Registry()


def test_registry_loads(reg):
    s = reg.summary()
    assert s["total"] > 40
    assert s["v0"] > 30
    assert reg.get("reply_rate") is not None


def test_registry_resolve_alias(reg):
    assert reg.resolve("官方回复率") == "reply_rate"
    assert reg.resolve("播放量") == "播放量"
    assert reg.resolve("likes") == "likes"


def test_judge_done(reg):
    v = judge("likes", reg, [0.8, 0.9])
    assert v["status"] == DONE


def test_judge_partial_when_low_coverage(reg):
    # 覆盖率中位远低于阈值 → 部分可做
    v = judge("reply_rate", reg, [0.05, 0.08, 0.10])
    assert v["status"] == PARTIAL
    assert "覆盖率" in v["reason"]


def test_judge_impossible(reg):
    v = judge("播放量", reg, [0.8])
    assert v["status"] == IMPOSSIBLE
    assert "接口" in v["reason"]


def test_judge_need_collect(reg):
    v = judge("作品数", reg, [0.8])
    assert v["status"] == NEED_COLLECT


def test_judge_unknown(reg):
    v = judge("某个不存在的需求", reg, [0.8])
    assert v["status"] == IMPOSSIBLE


def test_judge_llm_task_now_partial(reg):
    """v0.2 起标注引擎已实现 → LLM 指标判为"部分可做"(波动/需抽检), 不再是"需补采" """
    v = judge("willingness_level", reg, [0.8])
    assert v["status"] == PARTIAL
    assert "抽检" in v["reason"]


def test_judge_all_and_summary(reg):
    vs = judge_all(["likes", "播放量", "作品数"], reg, [0.8])
    assert len(vs) == 3
    from smanalyze.verdict import summarize
    s = summarize(vs)
    assert len(s[DONE]) == 1 and len(s[IMPOSSIBLE]) == 1 and len(s[NEED_COLLECT]) == 1


# ---------- 请求解析 ----------
def test_load_request(tmp_path):
    from smanalyze.parser import load_request
    f = tmp_path / "r.yaml"
    f.write_text("data_dir: ./d\nmetrics: [likes, 播放量]\ntasks: [willingness_level]\n"
                 "sample: all\ninclude_comments: false\n", encoding="utf-8")
    req = load_request(f)
    assert req["metrics"] == ["likes", "播放量"]
    assert req["tasks"] == ["willingness_level"]
    assert req["include_comments"] is False
