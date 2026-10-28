# -*- coding: utf-8 -*-
"""配置加载与合并: 默认值 < 配置文件 < 运行时覆盖"""
import copy
from pathlib import Path

DEFAULT_CONFIG = {
    "platform": "douyin",
    "profile_dir": "../../.profile",
    "output_dir": "data",
    "pacing": {
        "scroll_wait": [6, 12],
        "pause_every": 5,
        "pause_long": [15, 25],
        "max_scrolls": 250,       # 会话轮次预算: 保证 max_comments 上限能生效
        "max_comments": 2000,     # 单次评论+回复上限(用户确认)
        "stall_limit": 5,
    },
    "safety": {
        "max_per_day": 200,
        "read_only": True,        # 硬约束: 只读
    },
    "asr": {
        "model": "medium",
        "device": "cpu",
        "local_model": "../../.cache/hf-local/faster-whisper-medium",
    },
    "deepseek": {                  # 字幕 LLM 修正 (可选; 无 key 则跳过修正只留原始字幕)
        "api_key": "",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
    },
    "notify": {
        "channel": None,          # None/serverchan/wecom
        "serverchan": {"sendkey": ""},
        "wecom": {"webhook": ""},
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """递归合并: override 覆盖 base"""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None) -> dict:
    """加载配置文件, 与默认值合并。path 为 None 时返回默认值。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if path and Path(path).exists():
        import yaml
        user = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, user)
    return cfg


def resolve_path(cfg: dict, key: str, base_dir: Path) -> Path:
    """配置里的相对路径以配置文件所在目录为基准解析"""
    p = Path(cfg.get(key, "") or "")
    return p if p.is_absolute() else (base_dir / p).resolve()
