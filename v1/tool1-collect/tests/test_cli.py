# -*- coding: utf-8 -*-
"""CLI 参数解析测试"""
from smfetch.cli import build_parser


def parse(*argv):
    return build_parser().parse_args(list(argv))


def test_fetch_defaults():
    a = parse("fetch", "https://v.douyin.com/xxx/")
    assert a.target == "https://v.douyin.com/xxx/"
    assert a.comments is True          # 默认抓评论
    assert a.subtitle is True          # 默认转写字幕
    assert a.force is False


def test_fetch_flags():
    a = parse("fetch", "url", "--no-comments", "--no-subtitle", "--model", "large-v3", "--device", "cuda")
    assert a.comments is False
    assert a.subtitle is False
    assert a.model == "large-v3"
    assert a.device == "cuda"


def test_batch_attrs():
    """batch 子命令必须暴露 batch_run 依赖的全部属性 (防 Namespace 缺属性bug)"""
    a = parse("batch", "urls.txt")
    for attr in ("comments", "subtitle", "model", "device", "pause", "reset",
                 "no_notify", "dry_run", "per_day", "urls", "force"):
        assert hasattr(a, attr), f"batch 缺少属性 {attr}"
    assert a.comments is True
    assert a.subtitle is True          # 默认转写


def test_global_config_flag():
    a = parse("--config", "x.yaml", "status")
    assert a.config == "x.yaml"
    assert a.cmd == "status"


def test_export_args():
    a = parse("export", "--format", "json", "--scope", "comments")
    assert a.format == "json"
    assert a.scope == "comments"
