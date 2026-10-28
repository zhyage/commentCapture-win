# -*- coding: utf-8 -*-
"""常驻浏览器服务 (A1 方案)

- 一个独立 Chromium 进程常驻: 固定 profile(.profile) + 调试端口 9222
- 工具通过 CDP 连接复用; 任务完不关, 仅显式 stop 才关
- 识别: 进程路径在 .cache/ms-playwright + 命令行含 --user-data-dir=.profile (与用户浏览器无关)

用法: smsearch browser start|stop|status   (或直接调用本模块函数)
"""
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
PORT = 9222
PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _chrome_exe() -> Path:
    """定位 Playwright 下载的 Chromium 可执行文件"""
    root = Path("D:/zhy/抖音/.cache/ms-playwright")
    hits = sorted(root.glob("chromium-*/chrome-win*/chrome.exe"))
    if not hits:
        raise FileNotFoundError("未找到 Playwright Chromium, 请先安装")
    return hits[0]


def is_running() -> bool:
    try:
        with urllib.request.urlopen(CDP_URL + "/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start() -> bool:
    """启动常驻浏览器(若已运行则跳过)。返回是否已就绪。"""
    if is_running():
        print(">> 常驻浏览器已在运行")
        return True
    exe = _chrome_exe()
    subprocess.Popen([
        str(exe),
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ])
    # 等待端口就绪
    for _ in range(30):
        if is_running():
            print(">> 常驻浏览器已启动 (port 9222)")
            return True
        time.sleep(1)
    print(">> 启动超时, 端口未就绪")
    return False


def stop() -> bool:
    """通过 CDP 关闭常驻浏览器"""
    if not is_running():
        print(">> 常驻浏览器未在运行")
        return True
    try:
        p = sync_playwright().start()
        b = p.chromium.connect_over_cdp(CDP_URL)
        b.close()
        p.stop()
        time.sleep(2)
        print(">> 常驻浏览器已关闭")
        return not is_running()
    except Exception as e:
        print(f">> 关闭失败: {str(e)[:100]}")
        return False


def status() -> dict:
    if not is_running():
        return {"running": False}
    try:
        p = sync_playwright().start()
        b = p.chromium.connect_over_cdp(CDP_URL)
        pages = sum(len(c.pages) for c in b.contexts)
        p.stop()
        return {"running": True, "pages": pages}
    except Exception as e:
        return {"running": True, "connect_error": str(e)[:80]}


def connect():
    """连接常驻浏览器(未运行则先启动)。返回 (p, browser, ctx, page)。
    注意: 调用方不要 close browser —— 常驻浏览器由 stop() 显式关闭。"""
    if not is_running():
        start()
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, b, ctx, page
