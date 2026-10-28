# -*- coding: utf-8 -*-
"""探测4: 记录 search/item/ 请求完整 URL; 点'综合'找排序选项; 看 URL 是否带排序参数"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

req_urls = []


def on_request(req):
    if "/aweme/v1/web/search/item/" in req.url:
        req_urls.append(req.url)


def main():
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=False,
        args=["--start-maximized"], no_viewport=True,
        user_agent=UA, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("request", on_request)
    page.goto("https://www.douyin.com/search/%E7%BA%A2%E6%B2%B3%E6%96%87%E6%97%85?type=video",
              timeout=90000, wait_until="domcontentloaded")
    time.sleep(5)
    try:
        page.locator("input").first.fill("红河文旅")
        page.locator("input").first.press("Enter")
    except Exception:
        pass
    time.sleep(8)
    print(f">> 初始 search/item 请求: {len(req_urls)}")
    if req_urls:
        print("完整URL示例:")
        print(req_urls[0])

    # 找所有含"点赞/最新/评论"的可见元素 (DOM 级, 不依赖 body.innerText)
    def find_sort_items(label):
        return page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,li,button').forEach(el => {
                const t = (el.innerText || '').trim();
                const r = el.getBoundingClientRect();
                if (t && t.length < 15 && r.width && r.height && t !== '' ) out.push(t);
            });
            return [...new Set(out)];
        }""")

    items = find_sort_items("all")
    print(f"\n>> 页面可见短文本: {items}")

    # 点击"综合"(可能展开排序下拉)
    try:
        page.get_by_text("综合", exact=True).first.click(timeout=4000)
        print(">> 已点击'综合'")
    except Exception as e:
        print(f">> 点综合失败: {str(e)[:60]}")
    time.sleep(3)
    items2 = find_sort_items("all")
    print(f">> 点击后可见短文本: {items2}")
    for t in items2:
        if any(k in t for k in ("点赞", "最新", "评论", "综合", "收藏")):
            print(f"   >> 排序候选: {t!r}")

    # 若有"最多点赞"则点击并观察 URL
    for cand in ("最多点赞", "按点赞", "最多评论", "最新发布"):
        try:
            loc = page.get_by_text(cand, exact=True).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3000)
                print(f">> 已点击排序: {cand}")
                time.sleep(5)
                break
        except Exception:
            continue

    print(f"\n>> 最终 search/item 请求: {len(req_urls)}")
    if len(req_urls) > 1:
        print("> URL1:", req_urls[0])
        print("> URL2:", req_urls[-1])

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
