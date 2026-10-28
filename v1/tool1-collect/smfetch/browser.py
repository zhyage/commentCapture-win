# -*- coding: utf-8 -*-
"""浏览器连接: 复用常驻浏览器 (A1 方案, 与工具2 共享)
- 连接 9222 常驻浏览器 (由 smsearch browser start 启动, 小号登录态)
- 任务完不关闭浏览器; 仅显式 `smsearch browser stop` 才关
- 使用方式: p, ctx, page = connect(); 用完 page.close(); 最后 p.stop()
  (p.stop() 只断开本地 playwright 驱动, 不会关闭常驻浏览器)
"""
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
PORT = 9222


def is_running() -> bool:
    try:
        with urllib.request.urlopen(CDP_URL + "/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_running() -> bool:
    """常驻浏览器未运行则提示 (工具1 不负责启动它, 由 smsearch browser start 管理)"""
    if is_running():
        return True
    print(">> 常驻浏览器未运行! 请先在工具2目录执行:")
    print(">>   smsearch browser start   (或直接复用已打开的浏览器)")
    return False


def connect(profile_dir=None, headless: bool = False):
    """连接常驻浏览器, 返回 (p, ctx, page)。
    - page 为**新开标签页** (避免污染常驻页面; 用完 page.close())
    - 不 close context/browser (常驻); p.stop() 只断开本地驱动
    - 兼容旧签名 (profile_dir/headless 保留, 忽略)。"""
    if not ensure_running():
        raise RuntimeError("常驻浏览器未运行")
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.new_page()
    return p, ctx, page
