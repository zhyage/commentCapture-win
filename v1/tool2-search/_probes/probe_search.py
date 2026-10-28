# -*- coding: utf-8 -*-
"""工具2 可行性探测 v2: 走真实搜索路径 (搜索框输入+回车), 记录页面状态与接口"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
KEYWORD = "云南文旅"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

search_calls = []
all_search_urls = set()


def on_response(resp):
    url = resp.url
    if "search" in url.lower():
        all_search_urls.add(url[:160])
        if "aweme" in url:
            try:
                body = resp.json()
                items = body.get("data") or body.get("aweme_list") or []
                rec = {"url": url[:180], "n_items": len(items),
                       "has_more": body.get("has_more"), "cursor": body.get("cursor")}
                if items:
                    first = items[0]
                    aw = first.get("aweme") or first.get("aweme_info") or first
                    rec["first_desc"] = (aw.get("desc") or "")[:40]
                    rec["first_stats"] = aw.get("statistics")
                    rec["first_create_time"] = aw.get("create_time")
                    rec["first_author"] = (aw.get("author") or {}).get("nickname")
                    rec["first_aweme_id"] = aw.get("aweme_id")
                    rec["first_share_url"] = (aw.get("share_info") or {}).get("share_url")
                    rec["first_keys"] = sorted(aw.keys())[:30]
                search_calls.append(rec)
            except Exception:
                pass


def page_snapshot(page, label):
    """记录页面标题与可见文本前 200 字, 判断页面状态"""
    try:
        title = page.title()
        text = page.evaluate("() => (document.body.innerText || '').slice(0, 200)")
        print(f">> [{label}] 标题: {title}")
        print(f">> [{label}] 可见文本: {text!r}")
    except Exception as e:
        print(f">> [{label}] 快照失败: {str(e)[:80]}")


def main():
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=False,
        args=["--start-maximized"], no_viewport=True,
        user_agent=UA, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", on_response)

    # 1) 打开搜索页
    url = f"https://www.douyin.com/search/{KEYWORD}?type=video"
    print(f">> 打开: {url}")
    page.goto(url, timeout=90000, wait_until="domcontentloaded")
    time.sleep(8)
    page_snapshot(page, "初始")
    print(f">> 搜索接口调用: {len(search_calls)}")

    # 2) 找搜索框
    print(">> 页面 input 元素:")
    try:
        inputs = page.locator("input")
        for i in range(min(inputs.count(), 5)):
            ph = inputs.nth(i).get_attribute("placeholder") or ""
            print(f"   input[{i}] placeholder={ph!r}")
    except Exception as e:
        print(f"   定位 input 失败: {str(e)[:80]}")

    # 3) 输入关键词 + 回车
    typed = False
    try:
        box = page.locator("input").first
        box.fill(KEYWORD)
        time.sleep(1)
        box.press("Enter")
        typed = True
        print(">> 已输入关键词并回车")
    except Exception as e:
        print(f">> 输入失败: {str(e)[:100]}")
    time.sleep(8)
    page_snapshot(page, "回车后")
    print(f">> 搜索接口调用: {len(search_calls)}")

    # 4) 排序 tab
    for tab in ("最多点赞", "最新发布"):
        try:
            loc = page.get_by_text(tab, exact=True).first
            if loc.count() > 0 and loc.is_visible():
                print(f">> 点击排序: {tab}")
                loc.click(timeout=5000)
                time.sleep(6)
                page_snapshot(page, f"排序后[{tab}]")
            else:
                print(f">> 排序tab不存在: {tab}")
        except Exception as e:
            print(f">> 点击排序失败 {tab}: {str(e)[:80]}")

    # 5) 滚动翻页
    for i in range(3):
        try:
            page.evaluate("""() => {
                const el = document.querySelector('.route-scroll-container')
                           || document.scrollingElement || document.body;
                el.scrollTop = el.scrollHeight;
            }""")
        except Exception:
            pass
        time.sleep(5)
        print(f">> 滚动 {i+1}/3, 累计调用 {len(search_calls)}")

    # 报告
    print("=" * 60)
    print(f"搜索接口调用: {len(search_calls)}")
    for i, c in enumerate(search_calls[:8]):
        print(f"--- {i+1} ---")
        print(f"  URL: {c['url']}")
        print(f"  n={c['n_items']} has_more={c['has_more']} cursor={c['cursor']}")
        if c.get("first_desc") is not None:
            print(f"  desc={c['first_desc']} | 作者={c['first_author']} | id={c['first_aweme_id']}")
            print(f"  stats={c['first_stats']} | 时间={c['first_create_time']}")
            print(f"  share_url={c.get('first_share_url')}")
    print("--- 所有含 search 的 URL 模式 ---")
    for u in sorted(all_search_urls)[:20]:
        print(f"  {u}")

    ctx.close()
    p.stop()
    print("=" * 60)
    print("探测 v2 结束 (只读)")


if __name__ == "__main__":
    main()
