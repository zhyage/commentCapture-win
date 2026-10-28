# -*- coding: utf-8 -*-
"""诊断: 点击"展开N条回复"后, 抖音实际调用的接口与返回结构"""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from dy_browser import launch
from dyconfig import SHORT_URL


def main():
    p, ctx, page = launch(headless=True)

    comment_urls = []
    reply_items = []
    detail_ok = {"ok": False}

    def on_response(resp):
        url = resp.url
        if "comment" in url.lower():
            comment_urls.append(url)
            try:
                body = resp.json()
                items = body.get("comments") or []
                if items:
                    rids = set((c.get("reply_id") or "0") for c in items)
                    print(f"  [响应] {url[:110]}")
                    print(f"         条数={len(items)} reply_id集合={rids}")
                    reply_items.extend(items)
            except Exception:
                pass
        if "/aweme/v1/web/aweme/detail/" in url and not detail_ok["ok"]:
            try:
                if resp.json().get("aweme_detail"):
                    detail_ok["ok"] = True
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(SHORT_URL, timeout=90000, wait_until="domcontentloaded")

    # 等详情
    deadline = time.time() + 90
    while not detail_ok["ok"] and time.time() < deadline:
        time.sleep(4)
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container') || document.scrollingElement || document.body;
            el.scrollTop += 400;
        }""")
    print("detail ok:", detail_ok["ok"])

    # 滚动几轮加载顶层评论
    for i in range(8):
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container') || document.scrollingElement || document.body;
            el.scrollTop = el.scrollHeight;
        }""")
        time.sleep(3)

    # 点击第一个"展开N条回复"
    clicked = page.evaluate("""() => {
        const btns = document.querySelectorAll('.comment-reply-expand-btn');
        if (btns.length) { btns[0].click(); return btns[0].innerText; }
        return null;
    }""")
    print("点击了:", clicked)

    # 等待回复接口
    time.sleep(10)

    print()
    print("=== 所有 comment 相关 URL ===")
    for u in comment_urls:
        print("  ", u[:130])

    print()
    print(f"=== 通过拦截拿到的含回复数据条目: {len(reply_items)} ===")
    if reply_items:
        for c in reply_items[:3]:
            print(json.dumps({
                "cid": c.get("cid"), "reply_id": c.get("reply_id"),
                "reply_to_reply_id": c.get("reply_to_reply_id"),
                "text": (c.get("text") or "")[:40],
                "user": (c.get("user") or {}).get("nickname"),
            }, ensure_ascii=False))

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
