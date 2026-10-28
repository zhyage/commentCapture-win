# -*- coding: utf-8 -*-
"""config 层测试"""
from smfetch import config as C


def test_defaults():
    cfg = C.load_config(None)
    assert cfg["pacing"]["max_comments"] == 2000
    assert cfg["safety"]["read_only"] is True
    assert cfg["notify"]["channel"] is None


def test_merge(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text("pacing:\n  max_comments: 500\nnotify:\n  channel: serverchan\n", encoding="utf-8")
    cfg = C.load_config(f)
    assert cfg["pacing"]["max_comments"] == 500       # 覆盖
    assert cfg["pacing"]["scroll_wait"] == [6, 12]    # 未覆盖保留默认
    assert cfg["notify"]["channel"] == "serverchan"
    assert cfg["safety"]["read_only"] is True


def test_deep_merge_nested():
    out = C.deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 9}})
    assert out["a"] == {"b": 9, "c": 2}


def test_resolve_path(tmp_path):
    cfg = {"output_dir": "data"}
    p = C.resolve_path(cfg, "output_dir", tmp_path)
    assert p == (tmp_path / "data").resolve()
    assert p.is_absolute()
