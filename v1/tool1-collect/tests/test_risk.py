# -*- coding: utf-8 -*-
"""risk 层测试: 节奏/卡住/上限"""
import random

from smfetch.risk import RiskController

PACING = {"scroll_wait": [6, 12], "pause_every": 5, "pause_long": [15, 25],
          "max_scrolls": 25, "max_comments": 2000, "stall_limit": 5}
SAFETY = {"max_per_day": 10, "read_only": True}


def make(seed=1, pacing=None, safety=None):
    return RiskController(pacing or dict(PACING), safety or dict(SAFETY),
                          rng=random.Random(seed))


def test_scroll_wait_in_range():
    r = make()
    for _ in range(50):
        w = r.scroll_wait()
        assert 6 <= w <= 12


def test_long_pause_in_range():
    r = make()
    for _ in range(20):
        assert 15 <= r.long_pause() <= 25


def test_pause_every():
    assert make().pause_every() == 5


def test_stall_detection():
    r = make()
    for _ in range(4):
        assert r.on_no_data() is False
    assert r.on_no_data() is True        # 第5次触发
    r.on_new_data()
    assert r.on_no_data() is False       # 重置后重新计数


def test_comment_cap():
    r = make()
    assert r.under_comment_cap(1999) is True
    assert r.under_comment_cap(2000) is False


def test_round_cap():
    r = make()
    assert r.under_round_cap(24) is True
    assert r.under_round_cap(25) is False


def test_daily_limit():
    r = make()
    for _ in range(10):
        r.record_request()
    assert r.daily_limit_hit() is True
    r2 = make()
    for _ in range(9):
        r2.record_request()
    assert r2.daily_limit_hit() is False


def test_read_only_flag():
    cfg = make().s
    assert cfg["read_only"] is True
