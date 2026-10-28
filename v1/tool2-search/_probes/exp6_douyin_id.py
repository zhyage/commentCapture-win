# -*- coding: utf-8 -*-
"""实验6: 抖音号 → 用户主页 可行性探测
流程: 搜索框输入 55008743593 → 回车 → 点 tab「用户」→ 拦截用户搜索接口
检查: 1) 响应里抖音号字段(short_id/unique_id) 2) sec_uid 是否可得 3) DOM 结果
"""
import io
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
DID = "55008743593"
SEARCH_HOME = "https://www.douyin.com/"


def main():
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.pages[0]

    # 记录搜索相关接口响应
    search_resps = []

    def on_resp(resp):
        u = resp.url
        if any(k in u for k in ("/aweme/v1/web/discover/search/",
                                "/aweme/v1/web/search/",
                                "user/search", "search/user")):
            try:
                body = resp.json()
                search_resps.append({"url": u, "body": body})
            except Exception:
                pass

    page.on("response", on_resp)

    print(">> 当前 URL:", page.url)
    print(">> 回首页 ...")
    page.goto(SEARCH_HOME, timeout=60000, wait_until="domcontentloaded")
    time.sleep(4)

    print(">> 搜索框输入抖音号:", DID)
    try:
        box = page.locator("input").first
        box.fill(DID)
        time.sleep(1)
        box.press("Enter")
    except Exception as e:
        print("!! 输入失败:", str(e)[:120])
        p.stop()
        return
    time.sleep(7)

    print(">> 当前 URL:", page.url)

    # 点击 tab「用户」
    print(">> 尝试点击 tab「用户」...")
    clicked = False
    for selector in [
        lambda: page.get_by_text("用户", exact=True).first,
        lambda: page.locator('[data-e2e="user-tab"], [data-e2e="search-user-tab"]').first,
    ]:
        try:
            loc = selector()
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=5000)
                clicked = True
                print(">> 已点击'用户' tab")
                break
        except Exception:
            continue
    if not clicked:
        print(">> 未找到'用户' tab (可能已在用户结果页)")
    time.sleep(6)

    # 检查拦截到的搜索接口
    print("\n===== A. 拦截到的搜索接口响应 =====")
    for r in search_resps:
        m = re.match(r"https?://[^/]+(/[^?]*)", r["url"])
        path = m.group(1) if m else r["url"]
        print(f"  {path}")
        body = r["body"]
        users = body.get("user_list") or body.get("data") or []
        for u in users[:5]:
            uu = u.get("user_info") or u
            print(json.dumps({
                "nickname": uu.get("nickname"),
                "short_id": uu.get("short_id"),
                "unique_id": uu.get("unique_id"),
                "sec_uid": (uu.get("sec_uid") or "")[:50],
                "uid": uu.get("uid"),
                "signature": (uu.get("signature") or "")[:40],
            }, ensure_ascii=False))

    # 即使没拦到接口, 也从 DOM/URL 找线索
    print("\n===== B. 页面可见用户卡片 =====")
    cards = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[href*="/user/"], [data-e2e*="user"], [class*="user-card"]').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                out.push({href: (el.getAttribute('href')||'').slice(0,100),
                          cls: (el.className||'').toString().slice(0,60),
                          text: (el.textContent||'').trim().slice(0,60)});
            }
        });
        return out.slice(0, 20);
    }""")
    for c in cards:
        print("  ", json.dumps(c, ensure_ascii=False))

    print("\n===== C. 当前 URL 是否已含 sec_uid =====")
    m = re.search(r"/user/([A-Za-z0-9_\-\.]+)", page.url)
    if m:
        print("  已进入用户页 sec_uid:", m.group(1)[:60])
        print("  完整:", page.url[:160])

    p.stop()


if __name__ == "__main__":
    main()
