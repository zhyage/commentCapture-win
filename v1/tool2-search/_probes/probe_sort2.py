# -*- coding: utf-8 -*-
"""探测2: 点'综合'(可能是排序下拉) 与 '筛选' tab, 各 dump 展开后的可见内容"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dump_visible(page, label, n=500):
    print(f"\n===== [{label}] 可见文本(前{n}字) =====")
    try:
        t = page.evaluate("() => (document.body.innerText || '').slice(0, 500)")
        print(repr(t))
    except Exception as e:
        print("  失败:", str(e)[:80])


def main():
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=False,
        args=["--start-maximized"], no_viewport=True,
        user_agent=UA, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.douyin.com/search/%E7%BA%A2%E6%B2%B3%E6%96%87%E6%97%85?type=video",
              timeout=90000, wait_until="domcontentloaded")
    time.sleep(5)
    try:
        page.locator("input").first.fill("红河文旅")
        page.locator("input").first.press("Enter")
    except Exception:
        pass
    time.sleep(8)
    dump_visible(page, "初始")

    # 1) 点"综合" tab (可能是排序下拉)
    try:
        page.get_by_text("综合", exact=True).first.click(timeout=4000)
        print("\n>> 已点击'综合'")
    except Exception as e:
        print("点击综合失败:", str(e)[:80])
    time.sleep(3)
    dump_visible(page, "点综合后")
    # 截图
    try:
        page.screenshot(path="probe_sort_after_zonghe.png", full_page=False)
        print("已截图 probe_sort_after_zonghe.png")
    except Exception as e:
        print("截图失败:", str(e)[:80])

    # 2) 点"筛选" tab
    try:
        page.get_by_text("筛选", exact=True).first.click(timeout=4000)
        print("\n>> 已点击'筛选'")
    except Exception as e:
        print("点击筛选失败:", str(e)[:80])
    time.sleep(3)
    dump_visible(page, "点筛选后")
    try:
        page.screenshot(path="probe_sort_after_shaixuan.png", full_page=False)
        print("已截图 probe_sort_after_shaixuan.png")
    except Exception as e:
        print("截图失败:", str(e)[:80])

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
