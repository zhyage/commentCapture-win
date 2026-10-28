# -*- coding: utf-8 -*-
"""
通知模块 (可插拔): 用于无人值守时向用户推送提醒
支持渠道:
  - serverchan (Server酱/方糖): 推送到微信
  - wecom (企业微信群机器人): 推送到企业微信群
配置文件: .notify_config.json
用法:
    from notifier import get_notifier
    n = get_notifier()
    n.send("标题", "正文")
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

CFG_FILE = Path(__file__).resolve().parent / ".notify_config.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"}


class BaseNotifier:
    channel = "base"

    def send(self, title: str, body: str = "") -> bool:
        raise NotImplementedError


class ServerChanNotifier(BaseNotifier):
    """Server酱 (方糖) - 推送到微信"""
    channel = "serverchan"
    API = "https://sctapi.ftqq.com/{sendkey}.send"

    def __init__(self, sendkey: str):
        self.sendkey = sendkey

    def send(self, title: str, body: str = "") -> bool:
        url = self.API.format(sendkey=self.sendkey)
        data = urllib.parse.urlencode({
            "title": title,
            "desp": body,
        }).encode("utf-8")
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers=UA)
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                if resp.get("code") == 0:
                    print(f"[notifier] Server酱发送成功: {title}")
                    return True
                print(f"[notifier] Server酱返回异常: {resp}")
                return False
            except Exception as e:
                print(f"[notifier] 第{attempt+1}次发送失败: {str(e)[:100]}")
                if attempt < 2:
                    time.sleep(3)
        return False


class WeComNotifier(BaseNotifier):
    """企业微信群机器人 (预留, 配置 webhook 后可用)"""
    channel = "wecom"

    def __init__(self, webhook: str):
        self.webhook = webhook

    def send(self, title: str, body: str = "") -> bool:
        payload = json.dumps({
            "msgtype": "text",
            "text": {"content": f"{title}\n{body}"},
        }).encode("utf-8")
        try:
            req = urllib.request.Request(self.webhook, data=payload, headers={**UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read().decode("utf-8"))
            ok = resp.get("errcode") == 0
            print(f"[notifier] 企业微信发送{'成功' if ok else '失败'}: {resp}")
            return ok
        except Exception as e:
            print(f"[notifier] 企业微信发送异常: {str(e)[:100]}")
            return False


def get_notifier():
    cfg = json.loads(CFG_FILE.read_text(encoding="utf-8"))
    ch = cfg.get("channel", "serverchan")
    if ch == "serverchan":
        return ServerChanNotifier(cfg["serverchan"]["sendkey"])
    if ch == "wecom":
        if not cfg.get("wecom", {}).get("webhook"):
            raise ValueError("企业微信 webhook 未配置")
        return WeComNotifier(cfg["wecom"]["webhook"])
    raise ValueError(f"未知通知渠道: {ch}")


if __name__ == "__main__":
    n = get_notifier()
    n.send("测试", "notifier 模块自检")
