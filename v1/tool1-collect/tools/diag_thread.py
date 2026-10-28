# -*- coding: utf-8 -*-
"""诊断: 大回复楼(261条)展开后的内部结构与加载机制"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smfetch.browser import launch
from smfetch.config import load_config, resolve_path

BASE = Path(__file__).resolve().parent.parent
cfg = load_config(BASE / "config-test.yaml")
profile = resolve_path(cfg, "profile_dir", BASE)
TARGET = "https://www.douyin.com/video/7447163286870707508"

comment_events = []   # (url, n, has_more, cursor)
detail_ok = {"ok": False}


def on_response(resp):
    try:
        url = resp.url
        if "/aweme/v1/web/comment/" in url:
            body = resp.json()
            items = body.get("comments") or []
            comment_events.append({
                "url": url[:150],
                "n": len(items),
                "has_more": body.get("has_more"),
                "cursor": body.get("cursor"),
            })
        elif "/aweme/v1/web/aweme/detail/" in url and resp.json().get("aweme_detail"):
            detail_ok["ok"] = True
    except Exception:
        pass


def smooth(page, step=400):
    try:
        page.evaluate(f"""() => {{
            const el = document.querySelector('.route-scroll-container')
                       || document.scrollingElement || document.body;
            el.scrollTop += {step};
        }}""")
    except Exception:
        pass


def dump_key_elements(page, label):
    print(f"\n===== [{label}] 关键元素 =====")
    try:
        hits = page.evaluate("""() => {
            const kws = ['回复','更多','加载','展开','收起','查看'];
            const out = [];
            document.querySelectorAll('span,div,button,p').forEach(el => {
                const t = (el.innerText||'').trim();
                if (t && t.length < 25 && kws.some(k => t.includes(k))) {
                    const r = el.getBoundingClientRect();
                    out.push({tag: el.tagName, cls: (el.className||'').toString().slice(0,60),
                              text: t.slice(0,25), w: Math.round(r.width)});
                }
            });
            return out.slice(0, 40);
        }""")
        for h in hits:
            print("  ", h)
    except Exception as e:
        print("  失败:", e)


def dump_scrollables(page, label):
    print(f"\n===== [{label}] 可滚动容器 =====")
    try:
        info = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div').forEach(e => {
                if (e.scrollHeight > e.clientHeight + 150) {
                    const r = e.getBoundingClientRect();
                    out.push({cls: (e.className||'').toString().slice(0,70),
                              sh: e.scrollHeight, ch: e.clientHeight,
                              w: Math.round(r.width), h: Math.round(r.height)});
                }
            });
            return out.sort((a,b)=>(b.sh-b.ch)-(a.sh-a.ch)).slice(0,6);
        }""")
        for i in info:
            print("  ", i)
    except Exception as e:
        print("  失败:", e)


def main():
    p, ctx, page = launch(profile, headless=False)
    page.on("response", on_response)
    try:
        page.goto(TARGET, timeout=90000, wait_until="domcontentloaded")
        deadline = time.time() + 90
        while not detail_ok["ok"] and time.time() < deadline:
            time.sleep(4)
            smooth(page)
        print("详情ok")

        # 滚动加载顶层评论, 直到出现回复展开按钮
        for i in range(12):
            time.sleep(4)
            smooth(page)
            n_btns = page.locator(".comment-reply-expand-btn").count()
            print(f"滚动{i+1}: 展开按钮 {n_btns} 个")
            if n_btns > 0:
                break

        # 点击第一个(261条大楼)
        print("\n>> 点击第一个展开按钮")
        page.locator(".comment-reply-expand-btn").first.click(timeout=5000)
        time.sleep(5)
        dump_key_elements(page, "展开后")
        dump_scrollables(page, "展开后")
        print("\n评论接口事件:")
        for e in comment_events:
            print("  ", e)

        # 找展开后的新容器(线程面板?), 在里面滚动试试
        print("\n>> 尝试在最大的可滚动容器内滚动 5 轮")
        before = len(comment_events)
        for i in range(5):
            try:
                page.evaluate("""() => {
                    const els = [...document.querySelectorAll('div')]
                        .filter(e => e.scrollHeight > e.clientHeight + 150);
                    els.sort((a,b) => (b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight));
                    const el = els[0] || document.scrollingElement;
                    const rem = el.scrollHeight - el.scrollTop - el.clientHeight;
                    el.scrollTop += Math.max(200, Math.min(500, Math.ceil(rem/3)));
                }""")
            except Exception:
                pass
            time.sleep(4)
        print(f"滚动后接口事件: {len(comment_events)} (此前{before})")
        for e in comment_events[before:]:
            print("  新增:", e)

        dump_key_elements(page, "线程内滚动后")
    finally:
        ctx.close()
        p.stop()


if __name__ == "__main__":
    main()
