# -*- coding: utf-8 -*-
"""notifier 层测试: payload 格式 (mock urllib)"""
import json
import urllib.parse
from unittest import mock

from smfetch.notifier import ServerChanNotifier, WeComNotifier, make_notifier


def test_serverchan_payload():
    n = ServerChanNotifier("TESTKEY")
    fake = mock.Mock()
    fake.read.return_value = b'{"code": 0}'
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = fake
    with mock.patch("urllib.request.urlopen", return_value=ctx) as m:
        assert n.send("标题", "正文") is True
    req = m.call_args[0][0]
    assert "TESTKEY" in req.full_url
    body = req.data.decode()
    assert "title=" in body
    assert "标题" in urllib.parse.unquote(body)


def test_serverchan_failure():
    n = ServerChanNotifier("TESTKEY")
    with mock.patch("urllib.request.urlopen", side_effect=Exception("网络错误")):
        assert n.send("t") is False


def test_wecom_payload():
    n = WeComNotifier("https://example.com/webhook?key=K")
    fake = mock.Mock()
    fake.read.return_value = b'{"errcode": 0}'
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = fake
    with mock.patch("urllib.request.urlopen", return_value=ctx) as m:
        assert n.send("标题", "正文") is True
    req = m.call_args[0][0]
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["msgtype"] == "text"
    assert "标题" in payload["text"]["content"]


def test_make_notifier_from_config():
    cfg = {"notify": {"channel": "serverchan", "serverchan": {"sendkey": "S"}}}
    assert isinstance(make_notifier(cfg), ServerChanNotifier)
    cfg2 = {"notify": {"channel": None}}
    assert make_notifier(cfg2) is None
