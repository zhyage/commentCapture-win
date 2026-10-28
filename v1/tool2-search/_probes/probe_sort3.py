# -*- coding: utf-8 -*-
"""探测3: 搜索内容在哪个 frame? 进 frame 挖排序控件"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PROFILE = Path("D:/zhy/抖音/.profile")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


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

    # 1) 列出所有 frame
    print("=== 页面 frames ===")
    for i, fr in enumerate(page.frames):
        print(f"  [{i}] {fr.url[:120]}")

    # 2) 找含搜索内容的 frame (含'筛选'或'综合'或结果文本)
    target = None
    for fr in page.frames:
        try:
            t = fr.evaluate("() => (document.body ? document.body.innerText : '')")
            if t and ("筛选" in t or "综合" in t or "红河文旅" in t):
                print(f">>> 候选 frame: {fr.url[:120]} 文本含关键词")
                print(f"    前400字: {t[:400]!r}")
                if "筛选" in t:
                    target = fr
                    break
        except Exception:
            continue

    if not target:
        print("!! 未找到含'筛选'的 frame")
        # 检查 shadow root
        try:
            roots = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) out.push(el.tagName + '.' + (el.className||'').toString().slice(0,40));
                });
                return out.slice(0, 10);
            }""")
            print("shadow roots:", roots)
        except Exception as e:
            print("shadow 检查失败:", str(e)[:80])
    else:
        # 3) 在目标 frame 里点'综合' (排序下拉?) 和 '筛选'
        for tab in ("综合", "筛选"):
            try:
                el = target.get_by_text(tab, exact=True).first
                if el.count() > 0:
                    el.click(timeout=4000)
                    print(f"\n>> 已在frame点击'{tab}'")
                    time.sleep(3)
                    t2 = target.evaluate("() => document.body.innerText")
                    print(f"    展开后文本(含tab附近): ")
                    idx = t2.find("综合")
                    print(repr(t2[max(0, idx-50):idx+400]))
            except Exception as e:
                print(f"  点击{tab}失败: {str(e)[:80]}")

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
