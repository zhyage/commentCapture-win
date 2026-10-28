# -*- coding: utf-8 -*-
"""验证修复: _find_user_by_did 定位 YNHHFB (只测定位+主页校验, 不跑全量)"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect
from smsearch.search import _find_user_by_did


def main():
    ctx, page = connect()
    for did in ["YNHHFB", "55008743593"]:
        print(f"\n===== 定位 {did} =====")
        sec = _find_user_by_did(page, ctx, did)
        print(f"  RESULT sec_uid: {sec}")
        time.sleep(2)


if __name__ == "__main__":
    main()
