# -*- coding: utf-8 -*-
"""聚焦探测: 挖出搜索页'筛选'按钮的真实结构与排序选项"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dump_els(page, label, keyword="筛选"):
    """打印所有 innerText 含 keyword 的元素"""
    print(f"\n===== [{label}] 含'{keyword}'的元素 =====")
    try:
        hits = page.evaluate(f"""() => {{
            const out = [];
            document.querySelectorAll('div,span,button,li,a,svg').forEach(el => {{
                const t = (el.innerText || '').trim();
                if (t && t.length < 30 && t.includes('{keyword}')) {{
                    const r = el.getBoundingClientRect();
                    out.push({{tag: el.tagName, cls: (el.className||'').toString().slice(0,50),
                              text: t, visible: !!(r.width && r.height),
                              x: Math.round(r.x), y: Math.round(r.y)}});
                }}
            }});
            return out.slice(0, 25);
        }}""")
        for h in hits:
            print("  ", h)
    except Exception as e:
        print("  失败:", str(e)[:100])


def dump_visible_texts(page, label, limit=400):
    print(f"\n===== [{label}] 可见文本(前{limit}字) =====")
    try:
        t = page.evaluate("() => (document.body.innerText || '').slice(0, limit)")
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
        box = page.locator("input").first
        box.fill("红河文旅")
        box.press("Enter")
    except Exception as e:
        print("输入失败:", str(e)[:80])
    time.sleep(8)

    dump_visible_texts(page, "结果页顶部")
    dump_els(page, "结果页")

    # 尝试点击任何可见的"筛选"元素
    clicked = False
    try:
        els = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,button,li').forEach(el => {
                const t = (el.innerText || '').trim();
                const r = el.getBoundingClientRect();
                if (t === '筛选' && r.width && r.height) out.push(el);
            });
            return out.length;
        }""")
        print(f"\n可见'筛选'元素数: {els}")
        if els > 0:
            page.get_by_text("筛选", exact=True).first.click(timeout=4000)
            clicked = True
            print("已点击'筛选'")
    except Exception as e:
        print("点击失败:", str(e)[:100])

    time.sleep(3)
    if clicked:
        dump_visible_texts(page, "点击筛选后")
        # 找排序选项
        for kw in ("点赞", "最新", "综合", "评论", "收藏"):
            try:
                n = page.evaluate(f"""() => {{
                    let c = 0;
                    document.querySelectorAll('div,span,li').forEach(el => {{
                        const t = (el.innerText||'').trim();
                        const r = el.getBoundingClientRect();
                        if (t && t.length < 15 && t.includes('{kw}') && r.width && r.height) c++;
                    }});
                    return c;
                }}""")
                print(f"  可见含'{kw}'的元素: {n}")
            except Exception:
                pass

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
