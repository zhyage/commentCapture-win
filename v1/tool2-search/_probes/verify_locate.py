# -*- coding: utf-8 -*-
"""验证: 修复后的 _find_user_by_did 能否定位 YNHHFB (只测定位, 不跑全量)"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect
from smsearch.search import _find_user_by_did, _verify_profile_did


def main():
    ctx, page = connect()
    for did in ["YNHHFB", "55008743593"]:
        print(f"\n===== 定位 {did} =====")
        sec = _find_user_by_did(page, ctx, did)
        print(f"  sec_uid: {sec}")
        if sec:
            # 进主页验证 (不翻页)
            page.goto(f"https://www.douyin.com/user/{sec}?from_tab_name=main&showSubTab=video&showTab=post",
                      timeout=90000, wait_until="domcontentloaded")
            time.sleep(7)
            ok = _verify_profile_did(page, did)
            print(f"  主页抖音号校验: {'通过' if ok else '失败'}")
            time.sleep(3)


if __name__ == "__main__":
    main()
