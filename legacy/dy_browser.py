# -*- coding: utf-8 -*-
"""浏览器启动辅助: 持久化登录态 + 真实浏览器"""
from playwright.sync_api import sync_playwright
from dyconfig import PROFILE, USER_AGENT


def launch(headless: bool = False):
    """启动带持久化登录态的浏览器。
    headless=False 时有可见窗口, 用于登录/滑验证码;
    headless=True 用于纯后台任务(如下载)。
    """
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=headless,
        args=["--start-maximized"] if not headless else [],
        no_viewport=not headless,
        viewport={"width": 1440, "height": 900} if headless else None,
        user_agent=USER_AGENT,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, ctx, page
