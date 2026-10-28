# -*- coding: utf-8 -*-
"""策略3(VAD两遍)决策 + LLM字幕修正合并逻辑 纯单测"""
from smfetch.asr import decide_pass
from smfetch.correct import _merge


def test_decide_single_when_high_coverage():
    # 覆盖率达标 → 只跑一遍
    assert decide_pass(0.71, None, 0.35) == "single"


def test_decide_pass2_when_low_coverage_and_improved():
    # 低覆盖率且第2遍更高 → pass2
    assert decide_pass(0.09, 0.71, 0.35) == "pass2"


def test_decide_keep1_when_pass2_not_improved():
    # 第2遍没提升 → 保留第1遍
    assert decide_pass(0.09, 0.05, 0.35) == "keep1"


def test_merge_normal():
    orig = [{"index": 1, "start": 0.0, "end": 2.0, "text": "东玉徽"},
            {"index": 2, "start": 2.0, "end": 4.0, "text": "红河迷的喽"}]
    raw = '{"segments": [{"index": 1, "text": "董宇辉"}, {"index": 2, "text": "红河弥勒"}]}'
    out = _merge(orig, raw)
    assert out[0]["text"] == "董宇辉"
    assert out[1]["text"] == "红河弥勒"
    # 时间轴保留
    assert out[0]["start"] == 0.0 and out[0]["end"] == 2.0


def test_merge_missing_index_keeps_original():
    orig = [{"index": 1, "start": 0.0, "end": 2.0, "text": "东玉徽"}]
    raw = '{"segments": []}'      # LLM 没改任何段
    out = _merge(orig, raw)
    assert out[0]["text"] == "东玉徽"


def test_merge_bad_json_keeps_original():
    orig = [{"index": 1, "text": "x"}]
    out = _merge(orig, "not json at all")
    assert out[0]["text"] == "x"


def test_subtitles_schema_has_corrected_fields():
    from smfetch.schema import SubtitlesInfo
    s = SubtitlesInfo()
    assert s.corrected_file is None
    assert s.asr_note == ""
