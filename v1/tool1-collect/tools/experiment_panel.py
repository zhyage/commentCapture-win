# -*- coding: utf-8 -*-
"""实验: '全部评论'弹层能否突破内嵌评论加载上限(748)

问题: 主页滚动只加载出 748 条顶层评论(984 总)就触底。
假设: 点开「全部评论」弹层后, 在弹层内滚动可能加载更多(全量1937)。

产出: 最终评论数 / 顶层数 / 是否突破 748 / 弹层容器信息
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # v1/

from smfetch.browser import launch
from smfetch.config import load_config, resolve_path
from smfetch.risk import RiskController

BASE = Path(__file__).resolve().parent.parent
cfg = load_config(BASE / "config-test.yaml")
profile = resolve_path(cfg, "profile_dir", BASE)
risk = RiskController(
    {"scroll_wait": [5, 10], "pause_every": 5, "pause_long": [12, 20],
     "max_scrolls": 80, "max_comments": 2500, "stall_limit": 6},
    cfg["safety"])

TARGET = "https://www.douyin.com/video/7447163286870707508"

comments: dict = {}
detail_ok = {"ok": False}


def on_response(resp):
    try:
        url = resp.url
        if "/aweme/v1/web/comment/" in url:
            body = resp.json()
            for c in body.get("comments") or []:
                if c.get("cid"):
                    comments[c["cid"]] = c
        elif "/aweme/v1/web/aweme/detail/" in url and resp.json().get("aweme_detail"):
            detail_ok["ok"] = True
    except Exception:
        pass


def smooth(page):
    try:
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container')
                       || document.scrollingElement || document.body;
            const rem = el.scrollHeight - el.scrollTop - el.clientHeight;
            el.scrollTop += Math.max(150, Math.min(500, Math.ceil(rem / 3)));
        }""")
    except Exception:
        pass


def panel_scroll(page):
    """在弹层/页面内滚动: 优先最大的可滚动容器(弹层通常最大)"""
    try:
        page.evaluate("""() => {
            const els = [...document.querySelectorAll('div')]
                .filter(e => e.scrollHeight > e.clientHeight + 200);
            els.sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
            const el = els[0] || document.scrollingElement || document.body;
            const rem = el.scrollHeight - el.scrollTop - el.clientHeight;
            el.scrollTop += Math.max(200, Math.min(600, Math.ceil(rem / 3)));
        }""")
    except Exception:
        pass


def dump_containers(page):
    try:
        info = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div').forEach(e => {
                if (e.scrollHeight > e.clientHeight + 200) {
                    const r = e.getBoundingClientRect();
                    out.push({cls: (e.className||'').toString().slice(0,80),
                              sh: e.scrollHeight, ch: e.clientHeight,
                              w: Math.round(r.width), h: Math.round(r.height)});
                }
            });
            return out.sort((a,b)=>(b.sh-b.ch)-(a.sh-a.ch)).slice(0,5);
        }""")
        print("可滚动容器(按可滚量):")
        for i in info:
            print("  ", i)
    except Exception:
        pass


def main():
    p, ctx, page = launch(profile, headless=False)
    page.on("response", on_response)
    try:
        page.goto(TARGET, timeout=90000, wait_until="domcontentloaded")
        deadline = time.time() + 90
        while not detail_ok["ok"] and time.time() < deadline:
            time.sleep(4)
            smooth(page)
        print(f"详情ok: {detail_ok['ok']} | 当前评论: {len(comments)}")

        # 1) 点开「全部评论」
        clicked = False
        for sel in (".comment-title",):
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            try:
                loc = page.get_by_text("全部评论", exact=True)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=3000)
                    clicked = True
            except Exception:
                pass
        print("点击'全部评论':", clicked)
        time.sleep(4)
        dump_containers(page)

        # 2) 在弹层内滚动 + 加载, 观察能否突破
        baseline = len(comments)
        for round_no in range(risk.p["max_scrolls"]):
            if not risk.under_comment_cap(len(comments)):
                break
            before = len(comments)
            time.sleep(risk.scroll_wait())
            panel_scroll(page)
            try:  # 展开回复
                loc = page.locator(".comment-reply-expand-btn")
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=2500)
            except Exception:
                pass
            for t in ("查看更多回复", "查看全部回复", "加载更多"):
                try:
                    loc = page.get_by_text(t, exact=True)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click(timeout=2500)
                        break
                except Exception:
                    pass
            if (round_no + 1) % risk.pause_every() == 0:
                time.sleep(risk.long_pause())
            if len(comments) == before:
                if risk.on_no_data():
                    print(">> 连续无新增, 触底停止")
                    break
            else:
                risk.on_new_data()
            print(f"轮{round_no+1}/{risk.p['max_scrolls']}: {len(comments)} 条")

        # 3) 结果
        top = [c for c in comments.values()
               if (c.get("reply_id") or "0") == "0" and (c.get("reply_to_reply_id") or "0") == "0"]
        print("=" * 50)
        print(f"最终: 总{len(comments)} 条 | 顶层 {len(top)} 条 | 基准 {baseline}")
        print(f"结论: {'✅ 突破' + str(len(comments)) if len(comments) > 984 else '❌ 未突破(仍~984)'} "
              f"(顶层{'>' if len(top) > 748 else '<='}748)")
    finally:
        ctx.close()
        p.stop()


if __name__ == "__main__":
    main()
