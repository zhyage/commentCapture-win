# -*- coding: utf-8 -*-
"""回归测试: 日期过滤值必须可 JSON 序列化

事故背景(2026-09-13):
    `after: 2024-01-01` 被 YAML 解析成 datetime.date → `json.dumps(request)` 抛
    TypeError → 工具2 在**爬完 3.5 小时后**才崩在写 results.json 这一步,
    urls.txt 从未写出, 63 条命中与 5000+ 条收集记录全部丢失。
    (2026-08-27 那次用 after/before = null(可序列化), 所以没暴露)

本文件锁定该回归: 解析结果必须是 JSON 安全的, 且日期过滤行为不变。
"""
import json
from datetime import date, datetime

import pytest

from smsearch.filter import hard_filter
from smsearch.parser import _iso_date, load_request


def _write(tmp_path, content):
    p = tmp_path / "request.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ---------- _iso_date 归一化 ----------
def test_iso_date_from_date_object():
    assert _iso_date(date(2024, 1, 1)) == "2024-01-01"


def test_iso_date_from_datetime_object():
    assert _iso_date(datetime(2024, 1, 1, 12, 30)) == "2024-01-01"


def test_iso_date_passthrough_and_none():
    assert _iso_date("2024-01-01") == "2024-01-01"
    assert _iso_date(None) is None
    assert _iso_date("") is None


# ---------- 解析结果必须 JSON 安全(本次事故的核心) ----------
def test_request_with_dates_is_json_serializable(tmp_path):
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: 2024-01-01\nbefore: 2024-12-31\n"))
    assert req["filters"]["after"] == "2024-01-01"
    assert req["filters"]["before"] == "2024-12-31"
    json.dumps(req, ensure_ascii=False)             # 修复前这里抛 TypeError


def test_request_with_null_dates_is_json_serializable(tmp_path):
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: null\nbefore: null\n"))
    assert req["filters"]["after"] is None
    json.dumps(req, ensure_ascii=False)


def test_result_payload_shape_is_serializable(tmp_path):
    """模拟 cli 写 results.json 的结构"""
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: 2025-01-01\nbefore: null\n"))
    payload = {"request": req, "results": [], "per_account": []}
    json.dumps(payload, ensure_ascii=False)


# ---------- 日期过滤行为不变 ----------
def _aw(ts, likes=5000):
    return {"create_time": ts, "statistics": {"digg_count": likes},
            "author": {"nickname": "某文旅"}}


def _ts(y, m, d):
    return int(datetime(y, m, d).timestamp())


def test_date_filter_still_works_with_iso_strings(tmp_path):
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: 2024-01-01\nbefore: 2024-12-31\n"))
    f = req["filters"]
    assert hard_filter(_aw(_ts(2024, 6, 1)), f)[0] is True
    assert hard_filter(_aw(_ts(2023, 12, 31)), f)[0] is False
    assert hard_filter(_aw(_ts(2025, 1, 1)), f)[0] is False


def test_date_filter_boundaries_inclusive(tmp_path):
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: 2024-01-01\nbefore: 2024-12-31\n"))
    f = req["filters"]
    assert hard_filter(_aw(_ts(2024, 1, 1)), f)[0] is True
    assert hard_filter(_aw(_ts(2024, 12, 31)), f)[0] is True


def test_after_only(tmp_path):
    req = load_request(_write(tmp_path, "douyin_id: [abc]\nafter: 2026-01-01\n"))
    f = req["filters"]
    assert f["before"] is None
    assert hard_filter(_aw(_ts(2025, 6, 1)), f)[0] is False
    assert hard_filter(_aw(_ts(2026, 6, 1)), f)[0] is True
