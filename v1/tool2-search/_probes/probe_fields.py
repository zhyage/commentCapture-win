# -*- coding: utf-8 -*-
"""聚焦探测: 搜索接口返回的单条结果里, 到底有哪些字段 (desc/作者/视频信息)"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

captured = {}


def on_response(resp):
    if "/aweme/v1/web/search/item/" in resp.url and "captured" not in captured:
        try:
            body = resp.json()
            items = body.get("data") or []
            if items:
                first = items[0]
                aw = first.get("aweme") or first.get("aweme_info") or first
                captured["aweme"] = aw
        except Exception:
            pass


def main():
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=False,
        args=["--start-maximized"], no_viewport=True,
        user_agent=UA, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", on_response)
    page.goto("https://www.douyin.com/search/%E4%BA%91%E5%8D%97%E6%96%87%E6%97%85?type=video",
              timeout=90000, wait_until="domcontentloaded")
    time.sleep(6)
    try:
        box = page.locator("input").first
        box.fill("云南文旅")
        box.press("Enter")
    except Exception as e:
        print("输入失败:", str(e)[:80])
    time.sleep(8)

    aw = captured.get("aweme")
    if not aw:
        print("未捕获到搜索结果")
    else:
        print("=== 搜索单条结果字段 (aweme) ===")
        print("desc:", (aw.get("desc") or "")[:60])
        au = aw.get("author") or {}
        print("author keys:", sorted(au.keys()))
        print("author.nickname:", au.get("nickname"))
        print("author.signature:", au.get("signature"))
        print("author.uid:", au.get("uid"))
        print("author.follower_count:", au.get("follower_count"))
        print("author.total_favorited:", au.get("total_favorited"))
        print("author.sec_uid:", au.get("sec_uid"))
        print()
        print("aweme 顶层是否有 video/music:", "video" in aw, "music" in aw)
        v = aw.get("video") or {}
        print("video keys 数量:", len(v.keys()) if v else 0)
        print("video.play_addr:", bool((v.get("play_addr") or {}).get("url_list")))
        print("video.duration:", (v.get("duration")))
        print()
        print("statistics:", aw.get("statistics"))
        print("create_time:", aw.get("create_time"))
        print("share_url:", (aw.get("share_info") or {}).get("share_url", "")[:60])
        print()
        print("=== 判断: 搜索阶段可拿到的 ===")
        print("文案:", bool(aw.get("desc")))
        print("作者签名:", bool(au.get("signature")))
        print("作者粉丝数:", bool(au.get("follower_count") is not None))
        print("视频直链:", bool((v.get("play_addr") or {}).get("url_list")))

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
