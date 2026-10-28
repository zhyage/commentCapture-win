# -*- coding: utf-8 -*-
"""诊断脚本: 查看视频页评论区域的DOM结构, 找出真实的翻页按钮/滚动容器"""
import sys
import time

from dy_browser import launch
from dyconfig import SHORT_URL


def main():
    p, ctx, page = launch(headless=True)
    got = {"ok": False}

    def on_resp(resp):
        try:
            if "/aweme/v1/web/aweme/detail/" in resp.url and not got["ok"]:
                body = resp.json()
                if body.get("aweme_detail") or body.get("aweme"):
                    got["ok"] = True
        except Exception:
            pass

    page.on("response", on_resp)
    page.goto(SHORT_URL, timeout=90000, wait_until="domcontentloaded")

    deadline = time.time() + 90
    while not got["ok"] and time.time() < deadline:
        time.sleep(5)
        page.mouse.wheel(0, 300)
    print("DETAIL OK:", got["ok"], "| URL:", page.url[:110])
    time.sleep(6)

    # 1) 可滚动的容器
    scrollables = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('div,section,ul').forEach(el => {
            if (el.scrollHeight > el.clientHeight + 100) {
                const r = el.getBoundingClientRect();
                out.push({tag: el.tagName,
                          cls: (el.className||'').toString().slice(0,90),
                          sh: el.scrollHeight, ch: el.clientHeight,
                          x: Math.round(r.x), y: Math.round(r.y),
                          w: Math.round(r.width), h: Math.round(r.height)});
            }
        });
        return out.slice(0, 25);
    }""")
    print("=== SCROLLABLE CONTAINERS ===")
    for s in scrollables:
        print("  ", s)

    # 2) 含关键词的元素
    hits = page.evaluate("""() => {
        const kws = ['更多评论','查看更多','加载更多','查看回复','展开','全部评论','评论'];
        const out = [];
        document.querySelectorAll('span,div,button,p').forEach(el => {
            const t = (el.innerText||'').trim();
            if (t && t.length < 25 && kws.some(k => t.includes(k))) {
                out.push({tag: el.tagName,
                          cls: (el.className||'').toString().slice(0,70),
                          text: t.slice(0,30)});
            }
        });
        return out.slice(0, 40);
    }""")
    print("=== KEYWORD ELEMENTS ===")
    for h in hits:
        print("  ", h)

    # 3) 粗略统计评论元素
    cnt = page.evaluate("""() => {
        let n = 0;
        document.querySelectorAll('[class*=comment]').forEach(e => {
            const t = (e.innerText||'');
            if (t && t.length > 5 && t.length < 500) n++;
        });
        return n;
    }""")
    print("COMMENT-ISH ELEMENTS:", cnt)

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
