# -*- coding: utf-8 -*-
"""抖音适配器: Playwright 真实浏览器 + 响应拦截 (免签名逆向)

安全设计: 只读 / 真人节奏(RiskController) / 卡住熔断 / 会话过期检测。
"""
import json
import random
import re
import sys
import time
from pathlib import Path

from ..browser import connect
from ..risk import RiskController
from ..session import SessionExpired, has_login
from .base import PlatformAdapter

VIDEO_URL = "https://www.douyin.com/video/{item_id}"


def _print(msg: str):
    print(msg, flush=True)


class DouyinAdapter(PlatformAdapter):
    platform = "douyin"

    def __init__(self, profile_dir: str | Path, risk: RiskController):
        self.profile_dir = Path(profile_dir)
        self.risk = risk

    # ---------- 登录 ----------
    def login(self, timeout_s: int = 300) -> bool:
        from ..session import login
        _print(">> 请在弹出的浏览器窗口中, 用【小号】扫码登录")
        ok = login(self.profile_dir, timeout_s)
        _print(">> 登录成功" if ok else ">> 登录超时")
        return ok

    # ---------- 解析 ----------
    def resolve(self, target: str) -> str:
        """短链或19位ID → item_id"""
        t = target.strip()
        if re.fullmatch(r"\d{15,25}", t):
            return t
        p, ctx, page = connect()
        try:
            page.goto(t, timeout=90000, wait_until="domcontentloaded")
            deadline = time.time() + 30
            item_id = None
            while time.time() < deadline:
                item_id = _extract_id(page.url)
                if item_id:
                    break
                time.sleep(2)
            if not item_id:
                raise RuntimeError(f"无法从 {t} 解析出视频ID (当前地址: {page.url})")
            return item_id
        finally:
            page.close()
            p.stop()   # 只断开本地驱动, 不关闭常驻浏览器

    # ---------- 抓取 ----------
    def fetch_video(self, item_id: str) -> dict:
        """打开视频页, 拦截详情接口, 返回原始 aweme dict"""
        detail = {"ok": False, "aweme": None}
        p, ctx, page = connect()

        def on_response(resp):
            try:
                url = resp.url
                if "/aweme/v1/web/aweme/detail/" in url and not detail["ok"]:
                    body = resp.json()
                    aw = body.get("aweme_detail") or body.get("aweme") or {}
                    if aw.get("aweme_id"):
                        detail["ok"] = True
                        detail["aweme"] = aw
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(VIDEO_URL.format(item_id=item_id), timeout=90000,
                      wait_until="domcontentloaded")
            deadline = time.time() + 120
            while not detail["ok"] and time.time() < deadline:
                _print(">> 等待视频详情... (若弹出验证码请手动完成)")
                time.sleep(5)
                _smooth_scroll(page)
            if not detail["ok"]:
                if not has_login(ctx):
                    raise SessionExpired("未检测到登录态, 请重新扫码")
                raise RuntimeError("详情接口未响应(可能被风控)")
            return detail["aweme"]
        finally:
            page.close()
            p.stop()   # 只断开本地驱动, 不关闭常驻浏览器

    def fetch_comments(self, item_id: str) -> dict:
        """评论+楼中楼回复。返回 {"comments": {cid: item}, "collected": n}"""
        comments: dict = {}
        detail_ok = {"ok": False}
        p, ctx, page = connect()

        def on_response(resp):
            try:
                url = resp.url
                if "/aweme/v1/web/comment/" in url:      # 顶层列表 + 回复接口
                    body = resp.json()
                    items = body.get("comments") or []
                    for c in items:
                        if c.get("cid"):
                            comments[c["cid"]] = c
                    if items:
                        _print(f">> 评论接口: 本批{len(items)}条, 累计{len(comments)}条")
                elif "/aweme/v1/web/aweme/detail/" in url:
                    if resp.json().get("aweme_detail"):
                        detail_ok["ok"] = True
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(VIDEO_URL.format(item_id=item_id), timeout=90000,
                      wait_until="domcontentloaded")
            # 等详情(期间可处理验证码)
            deadline = time.time() + 120
            while not detail_ok["ok"] and time.time() < deadline:
                time.sleep(5)
                _smooth_scroll(page)
            if not detail_ok["ok"]:
                if not has_login(ctx):
                    raise SessionExpired("未检测到登录态, 请重新扫码")
                raise RuntimeError("详情接口未响应")

            # 评论加载循环: 平滑滚动 + 真实点击展开回复 + 线程分页
            self.risk.on_new_data()
            for round_no in range(999):
                if not self.risk.under_round_cap(round_no):
                    _print(">> 达到轮次上限, 停止")
                    break
                if not self.risk.under_comment_cap(len(comments)):
                    _print(f">> 达到评论上限 {self.risk.p.get('max_comments')}, 停止")
                    break

                before = len(comments)
                time.sleep(self.risk.scroll_wait())
                _smooth_scroll(page)

                # 优先翻已有线程的分页(每轮最多3次), 无待翻线程时才展开新线程
                more_clicked = False
                for _ in range(3):
                    if not _trusted_click_text(page, ("展开更多",)):
                        break
                    more_clicked = True
                    time.sleep(random.uniform(2, 4))
                if not more_clicked:
                    _trusted_click(page, ".comment-reply-expand-btn")
                    time.sleep(random.uniform(2, 4))

                if (round_no + 1) % self.risk.pause_every() == 0:
                    pause = self.risk.long_pause()
                    _print(f">> 阅读停顿 {pause:.0f} 秒...")
                    time.sleep(pause)

                if len(comments) == before:
                    if self.risk.on_no_data():
                        _print(">> 连续无新增, 安全停止")
                        break
                else:
                    self.risk.on_new_data()
                _print(f">> 轮 {round_no+1}: 评论+回复 {len(comments)} 条")

            time.sleep(self.risk.scroll_wait() * 0.8)   # 缓速收尾
            return {"comments": comments, "collected": len(comments)}
        finally:
            page.close()
            p.stop()   # 只断开本地驱动, 不关闭常驻浏览器

    # ---------- 下载 ----------
    def download_video(self, item_id: str, aweme: dict, dest: Path) -> bool:
        urls = _pick_play_urls(aweme)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 1_000_000:
            _print(f">> 视频已存在, 跳过下载: {dest}")
            return True
        p, ctx, page = connect()
        try:
            for u in urls:
                try:
                    resp = ctx.request.get(u, headers={
                        "User-Agent": _UA,
                        "Referer": "https://www.douyin.com/",
                    }, timeout=120000)
                    ctype = resp.headers.get("content-type", "")
                    if resp.status == 200 and ("video" in ctype) and len(resp.body()) > 10000:
                        dest.write_bytes(resp.body())
                        _print(f">> 下载成功: {dest} ({dest.stat().st_size/1048576:.1f} MB)")
                        return True
                except Exception as e:
                    _print(f">> 该地址失败: {e}")
            _print(">> 所有直链下载失败")
            return False
        finally:
            page.close()
            p.stop()   # 只断开本地驱动, 不关闭常驻浏览器


# ---------- 内部工具 ----------
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _extract_id(url: str) -> str | None:
    m = re.search(r"(?:/video/|/note/|modal_id=|aweme_id=)(\d{15,25})", url or "")
    return m.group(1) if m else None


def _smooth_scroll(page, step_max: int = 500):
    """平滑滚动一小步 (JS驱动, 不依赖物理光标)"""
    try:
        page.evaluate(f"""() => {{
            const el = document.querySelector('.route-scroll-container')
                       || document.scrollingElement || document.body;
            const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
            const step = Math.max(150, Math.min({step_max}, Math.ceil(remaining / 3)));
            el.scrollTop += step;
        }}""")
    except Exception:
        pass


def _trusted_click(page, selector: str) -> bool:
    """真实点击(trusted事件); 合成点击会被前端忽略"""
    try:
        loc = page.locator(selector)
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click(timeout=3000)
            return True
    except Exception:
        pass
    return False


def _trusted_click_text(page, texts: tuple) -> bool:
    """按文本真实点击 (线程内'展开更多'等加载控件)"""
    for t in texts:
        try:
            loc = page.get_by_text(t, exact=True)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def _pick_play_urls(aweme: dict) -> list:
    video = (aweme or {}).get("video") or {}
    candidates = []
    for key in ("play_addr", "play_addr_265", "play_addr_h264", "download_addr"):
        addr = video.get(key) or {}
        candidates += addr.get("url_list") or []
    for br in video.get("bit_rate") or []:
        addr = br.get("play_addr") or {}
        candidates += addr.get("url_list") or []
    seen, ordered = set(), []
    for u in candidates:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    ordered.sort(key=lambda u: ("wm" not in u, len(u)), reverse=True)
    return ordered
