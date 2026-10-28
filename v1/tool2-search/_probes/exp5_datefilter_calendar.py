# -*- coding: utf-8 -*-
"""实验5: 1) 日期筛选点击后的 portal/日历组件检查(按 class 特征)
2) 滚动触发 post 接口, 抓响应 create_time 列表, 验证默认排序(最新在前?)"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"


def main():
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.pages[0]

    print("\n===== A. 点击'日期筛选' → 检查 portal/日历组件 =====")
    try:
        loc = page.get_by_text("日期筛选", exact=True).first
        loc.click(timeout=5000)
        time.sleep(2)
        comps = page.evaluate("""() => {
            const out = [];
            // portal 容器
            document.querySelectorAll('.semi-portal, [class*=calendar], [class*=Calendar], [class*=date-picker], [class*=DatePicker], [class*=popover], [class*=dropdown]').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    out.push({cls: (el.className||'').toString().slice(0,120),
                              x: Math.round(r.x), y: Math.round(r.y),
                              w: Math.round(r.width), h: Math.round(r.height),
                              text: (el.textContent||'').trim().slice(0,120)});
                }
            });
            return out;
        }""")
        if comps:
            print("  发现的日历/弹层组件:")
            for c in comps:
                print("   ", json.dumps(c, ensure_ascii=False))
        else:
            print("  (无可见日历/弹层组件 → 点击可能未展开面板)")
        # 全部可见文本关键词再扫一遍(数字日期也算)
        dates = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,td,th,button').forEach(el => {
                const t = (el.textContent||'').trim();
                const r = el.getBoundingClientRect();
                if (/^\\d{1,2}$/.test(t) && r.width > 0 && r.height > 0 && el.children.length === 0) {
                    out.push({n: t, y: Math.round(r.y)});
                }
            });
            return out.slice(0, 40);
        }""")
        if dates:
            print("  页面上的孤立数字(可能是日历日期):", dates[:30])
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception as e:
        print("  异常:", str(e)[:150])

    print("\n===== B. 滚动触发 post 接口, 抓 create_time =====")
    items = []

    def on_resp(resp):
        if "/aweme/v1/web/aweme/post/" in resp.url:
            try:
                body = resp.json()
                for it in (body.get("aweme_list") or []):
                    items.append({
                        "create_time": it.get("create_time"),
                        "desc": (it.get("desc") or "")[:28],
                        "digg": (it.get("statistics") or {}).get("digg_count"),
                    })
            except Exception:
                pass

    page.on("response", on_resp)
    for i in range(4):
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container')
                       || document.querySelector('.LSOoeXZS')
                       || document.scrollingElement;
            el.scrollTop = el.scrollHeight;
        }""")
        time.sleep(3)
    page.remove_listener("response", on_resp)

    if items:
        print(f"  抓到 {len(items)} 条")
        items.sort(key=lambda x: -(x["create_time"] or 0))
        for it in items[:8]:
            from datetime import datetime
            ts = datetime.fromtimestamp(it["create_time"]).strftime("%Y-%m-%d") if it["create_time"] else "?"
            print(f"    {ts} 赞{it['digg']} | {it['desc']}")
        cts = [it["create_time"] for it in items]
        print(f"  create_time 单调递减(最新在前): {cts == sorted(cts, reverse=True)}")
    else:
        print("  (未抓到 post 响应)")

    p.stop()


if __name__ == "__main__":
    main()
