# -*- coding: utf-8 -*-
"""queue 层测试: 去重/续跑/受阻"""
from smfetch.queue import TaskQueue


def test_add_dedup(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    assert q.add(["https://a.com/1", "https://a.com/1", "  ", "# 注释"]) == 1
    assert q.summary()["total"] == 1


def test_resume_skip_done(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.add(["url1", "url2"])
    first = q.next_pending()
    assert first.target == "url1"
    q.mark_done("url1")
    # 重新加载(模拟重启)
    q2 = TaskQueue(tmp_path / "q.jsonl")
    assert q2.summary() == {"total": 2, "pending": 1, "done": 1, "blocked": 0}
    assert q2.next_pending().target == "url2"


def test_blocked_and_retry(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.add(["url1"])
    q.mark_blocked("url1", "登录过期")
    assert q.summary()["blocked"] == 1
    assert q.next_pending() is None
    q.retry_blocked()
    assert q.summary()["pending"] == 1
    assert q.blocked_list() == []


def test_retry_cap(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.add(["u1", "u2"])
    q.mark_blocked("u1", "e1")
    q.mark_blocked("u2", "e2")
    # u1 已重试3次(上限), u2 1次
    q.items["u1"].retries = 3
    n = q.retry_blocked(max_retries=3)
    assert n == 1                      # 只有 u2 重新入队
    assert q.summary()["pending"] == 1
    assert q.summary()["blocked"] == 1  # u1 保持受阻


def test_persistence_roundtrip(tmp_path):
    p = tmp_path / "q.jsonl"
    q = TaskQueue(p)
    q.add(["u1", "u2"])
    q.mark_done("u1")
    q.mark_blocked("u2", "验证码")
    q3 = TaskQueue(p)
    assert q3.summary()["done"] == 1
    assert q3.summary()["blocked"] == 1
    assert q3.blocked_list()[0].error == "验证码"
    assert q3.blocked_list()[0].retries == 1
