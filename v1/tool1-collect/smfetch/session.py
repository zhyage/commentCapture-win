# -*- coding: utf-8 -*-
"""会话管理: 登录 / 过期检测 (共享常驻浏览器)"""
import time
from pathlib import Path

from .browser import connect

LOGIN_COOKIE_NAMES = ("sessionid", "sessionid_ss")


class SessionExpired(Exception):
    """登录态失效, 需要重新扫码"""


def has_login(ctx) -> bool:
    """检查浏览器上下文是否有有效登录 cookie"""
    names = {c["name"] for c in ctx.cookies()}
    return bool(names & set(LOGIN_COOKIE_NAMES))


def login(profile_dir: str | Path, timeout_s: int = 300) -> bool:
    """在常驻浏览器中打开抖音, 等待扫码登录。成功返回 True。不关闭浏览器。"""
    p, ctx, page = connect()
    try:
        page.goto("https://www.douyin.com/", timeout=90000, wait_until="domcontentloaded")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if has_login(ctx):
                return True
            time.sleep(3)
        return False
    finally:
        page.close()
        p.stop()   # 只断开本地驱动, 不关闭常驻浏览器
