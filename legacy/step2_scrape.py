# -*- coding: utf-8 -*-
"""
阶段2: 抓取单条视频的 详情(文案/元数据) + 评论
用法: python step2_scrape.py [可选: 短链或视频ID, 默认用配置文件里的短链]
输出: output/video_id.txt, output/json/detail.json, output/json/comments.json

原理: 用真实浏览器打开视频页, 拦截抖音自己的接口响应 (不需要逆向签名)。
只读操作: 滚动加载评论, 绝不点赞/关注/评论。
"""
import json
import random
import re
import sys
import time

from dy_browser import launch
from dyconfig import (SHORT_URL, JSON_DIR, OUT,
                      MAX_SCROLLS, MAX_COMMENTS, SCROLL_WAIT, REPLY_WAIT,
                      PAUSE_EVERY, PAUSE_LONG, STALL_LIMIT, DETAIL_WAIT)


def extract_video_id(url: str):
    m = re.search(r"(?:/video/|/note/|modal_id=|aweme_id=)(\d{15,25})", url or "")
    return m.group(1) if m else None


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else SHORT_URL
    print(f">> 目标: {target}")

    detail = {"ok": False, "aweme": None}
    comments: dict = {}

    p, ctx, page = launch(headless=False)

    def on_response(resp):
        try:
            url = resp.url
            if "/aweme/v1/web/aweme/detail/" in url and not detail["ok"]:
                body = resp.json()
                aw = body.get("aweme_detail") or body.get("aweme") or {}
                if aw.get("aweme_id"):
                    detail["ok"] = True
                    detail["aweme"] = aw
                    print(f">> 已捕获详情: aweme_id={aw.get('aweme_id')}")
            elif "/aweme/v1/web/comment/" in url:
                body = resp.json()
                items = body.get("comments") or []
                for c in items:
                    if c.get("cid"):
                        comments[c["cid"]] = c
                print(f">> 评论接口: 本批{len(items)}条, 累计{len(comments)}条")
        except Exception:
            pass

    page.on("response", on_response)

    # 1) 打开目标页面 (短链会自动跳转到视频页)
    page.goto(target, timeout=90000, wait_until="domcontentloaded")
    video_id = extract_video_id(page.url)
    deadline = time.time() + 30
    while not video_id and time.time() < deadline:
        time.sleep(2)
        video_id = extract_video_id(page.url)

    if not video_id:
        print(f">> 未能提取视频ID (当前地址: {page.url})")
        print(">> 若弹出验证码/登录墙, 请在窗口中手动处理后再看本行输出")
    else:
        (OUT / "video_id.txt").write_text(video_id, encoding="utf-8")
        print(f">> 视频ID: {video_id}")

    # 2) 等待详情接口 (期间可能需手动滑验证码)
    print(">> 等待视频详情数据... (若弹出验证码请手动完成)")
    wait_until = time.time() + DETAIL_WAIT
    while not detail["ok"] and time.time() < wait_until:
        time.sleep(5)
        page.mouse.wheel(0, 300)

    if detail["ok"]:
        aw = detail["aweme"]
        desc = (aw.get("desc") or "")[:120]
        stat = aw.get("statistics") or {}
        author = (aw.get("author") or {}).get("nickname", "?")
        print("-" * 60)
        print(f">> 作者: {author}")
        print(f">> 文案: {desc}")
        print(f">> 数据: 点赞{stat.get('digg_count')} / 评论{stat.get('comment_count')} / 分享{stat.get('share_count')}")

        # 3) 加载评论: 安全模式 - 平滑小步滚动 + 慢节奏 + 随机阅读停顿
        def js_scroll_a_bit():
            """平滑滚动一小步 (约剩余距离1/3, 单步最多500px), 模拟真人滚轮"""
            try:
                page.evaluate("""() => {
                    const el = document.querySelector('.route-scroll-container')
                               || document.scrollingElement || document.body;
                    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
                    const step = Math.max(150, Math.min(500, Math.ceil(remaining / 3)));
                    el.scrollTop += step;
                }""")
                return True
            except Exception:
                return False

        def click_reply_expand():
            """真实点击'展开N条回复'按钮 (必须用trusted事件, 合成点击会被前端忽略)"""
            try:
                loc = page.locator(".comment-reply-expand-btn")
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=3000)
                    return True
            except Exception:
                pass
            return False

        stall = 0
        for i in range(MAX_SCROLLS):
            before = len(comments)
            js_scroll_a_bit()
            time.sleep(random.uniform(*SCROLL_WAIT))          # 6~12秒
            expanded = click_reply_expand()
            if expanded:
                time.sleep(random.uniform(*REPLY_WAIT))       # 3~6秒
            # 每 PAUSE_EVERY 轮做一次较长的"阅读停顿"
            if (i + 1) % PAUSE_EVERY == 0:
                pause = random.uniform(*PAUSE_LONG)
                print(f">> 阅读停顿 {pause:.0f} 秒...")
                time.sleep(pause)
            if len(comments) == before:
                stall += 1
            else:
                stall = 0
            tag = " (展开了回复)" if expanded else ""
            print(f">> 轮 {i+1}/{MAX_SCROLLS}: 评论+回复 {len(comments)} 条{tag}")
            if stall >= STALL_LIMIT:
                print(f">> 已到底(连续{STALL_LIMIT}轮无新增), 安全停止")
                break
            if len(comments) >= MAX_COMMENTS:
                print(f">> 达到上限 {MAX_COMMENTS} 条, 停止")
                break

        # 安全收尾: 停顿后再关闭, 不留急停痕迹
        print(">> 本轮抓取结束, 缓速收尾...")
        time.sleep(random.uniform(5, 10))

        # 4) 若评论仍很少, 打开"全部评论"面板再补一小轮 (同样慢节奏)
        if len(comments) < 100:
            print(">> 评论较少, 尝试打开'全部评论'面板补充(慢速)...")
            try:
                page.locator(".comment-title").first.click(timeout=3000)
                time.sleep(random.uniform(4, 7))
                for i in range(15):
                    before = len(comments)
                    js_scroll_a_bit()
                    time.sleep(random.uniform(*SCROLL_WAIT))
                    click_reply_expand()
                    time.sleep(random.uniform(2, 4))
                    if len(comments) == before and i > 3:
                        break
                    if len(comments) >= MAX_COMMENTS:
                        break
            except Exception as e:
                print(f">> 打开面板失败: {e}")
            time.sleep(random.uniform(4, 8))
        print(f">> 评论+回复累计 {len(comments)} 条")
    else:
        print(">> 未获取到详情数据(可能被风控/验证码卡住), 停止")

    ctx.close()
    p.stop()

    # 4) 保存结果
    (JSON_DIR / "detail.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    (JSON_DIR / "comments.json").write_text(
        json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 60)
    print(f">> 已保存: output/json/detail.json 和 comments.json (共 {len(comments)} 条评论)")
    print(">> 下一步: python step3_download_asr.py")


if __name__ == "__main__":
    main()
