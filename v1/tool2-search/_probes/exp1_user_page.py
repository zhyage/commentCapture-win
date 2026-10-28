# -*- coding: utf-8 -*-
"""实验1: 红河文旅官方主页 — 探测"作品"排序控件 (最新/最热) 是否存在
在常驻浏览器(CDP 9222)里工作, 只读探测, 不点击。
输出: 页面可见文本片段 / 含关键词元素(含隐藏) / iframe / 可交互控件
"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect

URL = ("https://www.douyin.com/user/MS4wLjABAAAAzV1wNMOd-askb-PxHj8I8lWfvXMgy8MFgLy3g7mLuiM"
       "?from_tab_name=main&showSubTab=video&showTab=post")

KWS = ["最新", "最热", "排序", "作品", "发布", "综合", "点赞", "时间", "video", "post"]


def main():
    ctx, page = connect()
    print(">> 当前 URL:", page.url)
    print(">> 导航到用户主页 ...")
    page.goto(URL, timeout=90000, wait_until="domcontentloaded")
    time.sleep(8)  # 等 SPA 渲染

    print("\n===== A. 页面标题/URL =====")
    print("title:", page.title())
    print("url:", page.url)

    print("\n===== B. 可见短文本 (前 80 个, 去重) =====")
    texts = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('div,span,li,button,a,p,h1,h2,h3').forEach(el => {
            const t = (el.innerText || el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            if (t && t.length <= 24 && r.width > 0 && r.height > 0
                && r.width < 400) {
                // 仅取叶子相近的文本, 避免海量重复
                if (el.children.length <= 3) out.push(t);
            }
        });
        return [...new Set(out)].slice(0, 200);
    }""")
    for t in texts:
        print("  |", t)

    print("\n===== C. 含关键词的元素 (可见+隐藏, 含属性) =====")
    hits = page.evaluate("""(kws) => {
        const out = [];
        const all = document.querySelectorAll('div,span,li,button,a,p,h1,h2,h3,select,input');
        for (const el of all) {
            const t = (el.innerText || el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            const visible = r.width > 0 && r.height > 0;
            const attrs = {};
            for (const a of ['aria-label','title','placeholder','data-e2e','class','id','role','name','value']) {
                const v = el.getAttribute(a);
                if (v && v.length < 120) attrs[a] = v;
            }
            if (t && kws.some(k => t.includes(k))) {
                out.push({text: t.slice(0, 40), visible, x: Math.round(r.x), y: Math.round(r.y),
                          w: Math.round(r.width), h: Math.round(r.height), attrs});
            }
        }
        return out.slice(0, 80);
    }""", KWS)
    for h in hits:
        print(" ", json.dumps(h, ensure_ascii=False))

    print("\n===== D. iframe 清单 =====")
    frames = page.frames
    print("frames count:", len(frames))
    for i, f in enumerate(frames):
        try:
            print(f"  [{i}] {f.url[:120]}")
        except Exception as e:
            print(f"  [{i}] <err {e}>")

    print("\n===== E. select 元素 / 疑似下拉 =====")
    sels = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('select, [role=listbox], [role=menu], [aria-haspopup]').forEach(el => {
            const r = el.getBoundingClientRect();
            out.push({tag: el.tagName, role: el.getAttribute('role'),
                      popup: el.getAttribute('aria-haspopup'),
                      label: (el.getAttribute('aria-label')||el.innerText||'').trim().slice(0,40),
                      visible: r.width>0 && r.height>0,
                      x: Math.round(r.x), y: Math.round(r.y)});
        });
        return out;
    }""")
    for s in sels:
        print(" ", json.dumps(s, ensure_ascii=False))

    print("\n===== 完成 =====")


if __name__ == "__main__":
    main()
