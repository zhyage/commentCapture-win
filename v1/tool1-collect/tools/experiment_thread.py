# -*- coding: utf-8 -*-
"""实验: 单线程死磕 261 楼, 确定网页端深度分页的真实上限"""
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
THREAD = "7447168094362059574"   # 261楼

reply_events = []    # (n, has_more, cursor)
detail_ok = {"ok": False}


def on_response(resp):
    try:
        url = resp.url
        if "/comment/list/reply/" in url and THREAD in url:
            body = resp.json()
            reply_events.append((len(body.get("comments") or []),
                                 body.get("has_more"), body.get("cursor")))
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


def click_first_expand(page):
    """点击第一个'展开N条回复'"""
    try:
        loc = page.locator(".comment-reply-expand-btn")
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click(timeout=5000)
            return True
    except Exception:
        pass
    return False


def click_more(page):
    """点击'展开更多' (真实点击)"""
    try:
        loc = page.get_by_text("展开更多", exact=True)
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click(timeout=5000)
            return True
    except Exception:
        pass
    return False


def captured_replies(page):
    """从 DOM 粗略统计该线程当前显示的回复数(仅诊断用)"""
    try:
        return page.evaluate(f"""() => {{
            let n = 0;
            document.querySelectorAll('.comment-item').forEach(() => {{ n++; }});
            return n;
        }}""")
    except Exception:
        return -1


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

        # 找到并展开 261 楼 (第一条评论)
        for i in range(15):
            time.sleep(3)
            smooth(page)
            if page.locator(".comment-reply-expand-btn").count() > 0:
                break
        ok = click_first_expand(page)
        print("展开261楼:", ok)
        time.sleep(5)
        print("回复接口已调用:", len(reply_events))

        # 死磕「展开更多」
        stall = 0
        for i in range(150):
            if not click_more(page):
                print(f">> 第{i+1}次: '展开更多'按钮不存在 → 线程翻尽或受限")
                break
            time.sleep(3 + (i % 3))
            if (i + 1) % 10 == 0:
                pause = 5 + (i % 5)
                print(f">> 停顿 {pause}s ...")
                time.sleep(pause)
            new_events = len(reply_events)
            if new_events == stall and False:
                pass
            # 以接口事件增长判断进展
            if len(reply_events) > (stall + 0) if i == 0 else True:
                pass
            if i % 10 == 9:
                total = sum(e[0] for e in reply_events)
                print(f">> 已点{i+1}次 | 接口累计返回 {total} 条 | 事件{len(reply_events)}")
        # 触底判断在上面已处理; 这里若因按钮消失退出, 再看接口
        print()
        total_replies = sum(e[0] for e in reply_events)
        print("=" * 50)
        print(f"回复接口调用次数: {len(reply_events)}")
        print(f"接口累计返回回复: {total_replies} 条")
        print(f"最后一次: n={reply_events[-1] if reply_events else None}")
        print(f"261楼声明: 261 条")
        print(f"结论: 网页端线程深度上限 = {total_replies} 条")
    finally:
        ctx.close()
        p.stop()


if __name__ == "__main__":
    main()
