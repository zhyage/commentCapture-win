# -*- coding: utf-8 -*-
"""标注流水线纯逻辑单测 (不调用 API)"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smanalyze.cache import LabelCache, cache_key
from smanalyze.label import _parse, chunk, sample_items, write_labels, write_sample_md
from smanalyze.tasks import TaskDef, list_tasks, load_task


# ---------- 缓存 key ----------
def test_cache_key_stable():
    a = cache_key("文本", "task", "v1", "m")
    b = cache_key("文本", "task", "v1", "m")
    assert a == b and len(a) == 32


def test_cache_key_changes_on_any_component():
    base = cache_key("文本", "task", "v1", "m")
    assert cache_key("文本2", "task", "v1", "m") != base
    assert cache_key("文本", "task2", "v1", "m") != base
    assert cache_key("文本", "task", "v2", "m") != base     # 提示词版本变化
    assert cache_key("文本", "task", "v1", "m2") != base    # 换模型


def test_cache_roundtrip(tmp_path):
    c = LabelCache(tmp_path / "c.jsonl")
    k = cache_key("x", "t", "v", "m")
    assert c.get(k) is None
    c.put(k, {"key": k, "label": "1"})
    c.flush()
    c2 = LabelCache(tmp_path / "c.jsonl")
    assert c2.get(k)["label"] == "1"


# ---------- 抽样 ----------
def _items(n, likes=None):
    return [{"id": f"i{i}", "text": f"t{i}", "likes": (likes[i] if likes else 0)}
            for i in range(n)]


def test_sample_all():
    items = _items(10)
    assert len(sample_items(items, "all", 3)) == 10      # all 不截断


def test_sample_random_n_deterministic():
    items = _items(100)
    a = sample_items(items, "random_n", 10)
    b = sample_items(items, "random_n", 10)
    assert len(a) == 10
    assert [x["id"] for x in a] == [x["id"] for x in b]   # 固定种子可复现


def test_sample_top_likes():
    items = _items(5, likes=[1, 100, 50, 3, 20])
    top = sample_items(items, "top_likes_n", 2)
    assert [x["id"] for x in top] == ["i1", "i2"]


def test_sample_unknown_strategy():
    with pytest.raises(ValueError):
        sample_items(_items(3), "bad", 1)


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


# ---------- 任务定义 ----------
def test_list_tasks():
    ts = list_tasks()
    assert "willingness_level" in ts and "video_category" in ts


def test_task_def_labels():
    t = load_task("willingness_level")
    assert t.level == "comment"
    assert t.is_valid_label("0") and t.is_valid_label(4)
    assert not t.is_valid_label("9")


def test_task_prompt_version_changes_with_definition():
    d1 = {"task_id": "x", "labels": {"0": "a"}, "prompt_hint": "h1"}
    d2 = {"task_id": "x", "labels": {"0": "a"}, "prompt_hint": "h2"}
    assert TaskDef(d1).prompt_version != TaskDef(d2).prompt_version


def test_task_system_prompt_contains_labels():
    t = load_task("willingness_level")
    sp = t.system_prompt()
    assert "计划性意愿" in sp and "判定要点" in sp


# ---------- 解析校验 ----------
class _Task:
    task_id = "t"
    output_fields = ["level", "why"]
    labels = {"0": "a", "1": "b"}

    def is_valid_label(self, v):
        return str(v) in self.labels


def test_parse_ok():
    batch = [{"i": 1}, {"i": 2}]
    out = {"items": [{"i": 1, "level": 0, "why": "r1"},
                     {"i": 2, "level": 1, "why": "r2"}]}
    res = _parse(out, batch, _Task())
    assert [r["label"] for r in res] == ["0", "1"]
    assert all(r["ok"] for r in res)


def test_parse_missing_index():
    batch = [{"i": 1}, {"i": 2}]
    out = {"items": [{"i": 1, "level": 0}]}
    res = _parse(out, batch, _Task())
    assert res[0]["ok"] is True
    assert res[1]["ok"] is False and "缺少" in res[1]["error"]


def test_parse_invalid_label():
    batch = [{"i": 1}]
    out = {"items": [{"i": 1, "level": 9, "why": "x"}]}
    res = _parse(out, batch, _Task())
    assert res[0]["ok"] is False and "非法标签" in res[0]["error"]


def test_parse_extra_index_ignored():
    batch = [{"i": 1}]
    out = {"items": [{"i": 1, "level": 1}, {"i": 99, "level": 0}]}
    res = _parse(out, batch, _Task())
    assert len(res) == 1 and res[0]["ok"]


# ---------- 落盘 ----------
def test_write_labels_and_sample(tmp_path):
    rows = [{"id": "c1", "video_id": "v1", "task_id": "t", "label": "1",
             "why": "w", "ok": True, "error": "", "model": "m",
             "prompt_version": "pv", "cached": False, "ts": "now", "text": "文本1"},
            {"id": "c2", "video_id": "v1", "task_id": "t", "label": "0",
             "why": "w2", "ok": True, "error": "", "model": "m",
             "prompt_version": "pv", "cached": True, "ts": "now", "text": "文本2"}]
    p = tmp_path / "labels.csv"
    write_labels(rows, p)
    content = p.read_text(encoding="utf-8-sig")
    assert "c1" in content and "willingness" not in content

    t = load_task("willingness_level")
    md = tmp_path / "sample.md"
    write_sample_md(rows, t, md, n=2)
    text = md.read_text(encoding="utf-8")
    assert "抽检样本" in text and "文本1" in text


# ---------- JOIN 标注到变量表 ----------
def test_load_label_maps_and_join(tmp_path):
    from smanalyze.cli import _join_labels, _load_label_maps
    rows = [{"id": "c1", "video_id": "v1", "task_id": "willingness_level",
             "label": "2", "why": "", "ok": True, "error": "", "model": "m",
             "prompt_version": "pv", "cached": False, "ts": "t", "text": "x"},
            {"id": "c2", "video_id": "v1", "task_id": "willingness_level",
             "label": None, "why": "", "ok": False, "error": "非法", "model": "m",
             "prompt_version": "pv", "cached": False, "ts": "t", "text": "y"}]
    write_labels(rows, tmp_path / "labels_willingness_level.csv")

    maps = _load_label_maps(tmp_path)
    assert maps["willingness_level"] == {"c1": "2"}      # ok=False 的被排除

    variables = [{"comment_id": "c1", "char_len": 5}, {"comment_id": "c2", "char_len": 6}]
    added = _join_labels(variables, "comment_id", maps)
    assert added == 1
    assert variables[0]["willingness_level"] == "2"
    assert "willingness_level" not in variables[1]        # 无标注 → 不填


def test_join_labels_idempotent(tmp_path):
    from smanalyze.cli import _join_labels
    maps = {"t": {"a": "1"}}
    rows = [{"id": "a", "t": "already"}]
    assert _join_labels(rows, "id", maps) == 0            # 已有列 → 跳过
