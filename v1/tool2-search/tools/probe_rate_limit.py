# -*- coding: utf-8 -*-
"""限流探针: 只打开 1 个账号主页, 看作品接口是否还有数据

背景(2026-09-13): 连续跑 6 小时后, 2025 段第 7 个号起、2026 段全部出现"收集 0 条"
(= 作品接口不返回数据, 疑似软风控/限流)。重跑前先用 1 次主页加载探测, 避免空烧数小时。

用法:
    cd D:\\zhy\\抖音\\v1\\tool2-search
    python tools/probe_rate_limit.py [抖音号]     # 默认 gzslyfzwyh

判读:
    OK    → 接口有数据, 可以开跑
    EMPTY → 收集 0 条, 仍被限流 → 继续冷却, 不要开跑
"""
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from smsearch import service                                  # noqa: E402
from smsearch.search import _find_user_by_did, _has_session   # noqa: E402


def main() -> int:
    did = sys.argv[1] if len(sys.argv) > 1 else "gzslyfzwyh"
    p, b, ctx, page = service.connect()
    print(f">> 探针: {did} | sessionid 在位: {_has_session(ctx)}")

    got = {"items": 0, "has_more": None, "calls": 0}

    def on_response(resp):
        if "/aweme/v1/web/aweme/post/" not in resp.url:
            return
        got["calls"] += 1
        try:
            body = resp.json()
        except Exception:
            return
        got["items"] += len(body.get("aweme_list") or [])
        got["has_more"] = body.get("has_more")

    page.on("response", on_response)
    sec = _find_user_by_did(page, ctx, did)
    if not sec:
        print(">> 定位失败(可能与限流无关, 检查登录态)")
        return 2
    try:
        page.goto(f"https://www.douyin.com/user/{sec}"
                  "?from_tab_name=main&showSubTab=video&showTab=post",
                  timeout=90000, wait_until="domcontentloaded")
        time.sleep(12)
        try:
            page.evaluate("""() => { const el = document.querySelector('.route-scroll-container')
                                      || document.scrollingElement || document.body;
                                    el.scrollTop = el.scrollHeight; }""")
        except Exception:
            pass
        time.sleep(8)
    finally:
        page.remove_listener("response", on_response)

    verdict = "OK" if got["items"] > 0 else "EMPTY"
    print(f">> 作品接口调用 {got['calls']} 次 | 收到作品 {got['items']} 条 | has_more={got['has_more']}")
    print(f">> 判读: {verdict} —— " + ("接口有数据, 可以开跑" if verdict == "OK"
                                      else "收集 0 条, 仍被限流 → 继续冷却, 不要开跑"))
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
