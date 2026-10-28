# -*- coding: utf-8 -*-
"""通知层: 微信提醒 (Server酱 / 企业微信), 可插拔"""
import json
import time
import urllib.parse
import urllib.request
from typing import Protocol

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"}


class Notifier(Protocol):
    def send(self, title: str, body: str = "") -> bool: ...


class ServerChanNotifier:
    """Server酱(方糖): 推送到微信"""
    channel = "serverchan"
    API = "https://sctapi.ftqq.com/{sendkey}.send"

    def __init__(self, sendkey: str):
        self.sendkey = sendkey

    def send(self, title: str, body: str = "") -> bool:
        data = urllib.parse.urlencode({"title": title, "desp": body}).encode("utf-8")
        url = self.API.format(sendkey=self.sendkey)
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers=UA)
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                return resp.get("code") == 0
            except Exception:
                if attempt < 2:
                    time.sleep(3)
        return False


class WeComNotifier:
    """企业微信群机器人 (webhook)"""
    channel = "wecom"

    def __init__(self, webhook: str):
        self.webhook = webhook

    def send(self, title: str, body: str = "") -> bool:
        payload = json.dumps({"msgtype": "text", "text": {"content": f"{title}\n{body}"}},
                             ensure_ascii=False).encode("utf-8")
        try:
            req = urllib.request.Request(self.webhook, data=payload,
                                         headers={**UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read().decode("utf-8"))
            return resp.get("errcode") == 0
        except Exception:
            return False


def make_notifier(cfg: dict) -> Notifier | None:
    """按配置创建通知器; 未配置返回 None (静默)"""
    ch = (cfg.get("notify") or {}).get("channel")
    if ch == "serverchan":
        key = (cfg.get("notify") or {}).get("serverchan", {}).get("sendkey", "")
        return ServerChanNotifier(key) if key else None
    if ch == "wecom":
        hook = (cfg.get("notify") or {}).get("wecom", {}).get("webhook", "")
        return WeComNotifier(hook) if hook else None
    return None
