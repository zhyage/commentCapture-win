# -*- coding: utf-8 -*-
"""pytest fixtures: 黄金数据 (来自真实抖音采集)"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 使 smfetch 可导入

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def raw_detail():
    return load("detail.json")          # {"aweme": {...}}


@pytest.fixture(scope="session")
def raw_comments():
    return load("comments.json")        # {cid: item}


@pytest.fixture(scope="session")
def raw_subtitles():
    return load("subtitles.json")       # [{start,end,text}]


@pytest.fixture(scope="session")
def author_id(raw_detail):
    return raw_detail["aweme"]["author"]["uid"]


@pytest.fixture(scope="session")
def fixture_video_id():
    return (FIXTURES / "video_id.txt").read_text(encoding="utf-8").strip()
