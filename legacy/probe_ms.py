# -*- coding: utf-8 -*-
"""测试 ModelScope 上 faster-whisper 候选仓库是否存在"""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"}

candidates = [
    "pengzhendong/faster-whisper-medium",
    "pengzhendong/faster-whisper-small",
    "pengzhendong/faster-whisper-large-v3",
    "AI-ModelScope/faster-whisper-medium",
    "Systran/faster-whisper-medium",
    "keepitsimple/faster-whisper-medium",
]

for repo in candidates:
    # 1) 模型页面
    page_url = f"https://www.modelscope.cn/models/{repo}"
    try:
        req = urllib.request.Request(page_url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", "ignore")
            print(f"[{repo}] 页面 OK http={r.status}")
    except Exception as e:
        print(f"[{repo}] 页面 FAIL {str(e)[:60]}")
        continue
    # 2) 文件直链 (config.json)
    file_url = f"https://www.modelscope.cn/models/{repo}/resolve/master/config.json"
    try:
        req = urllib.request.Request(file_url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"      config.json OK http={r.status} len={len(r.read())}")
    except Exception as e:
        print(f"      config.json FAIL {str(e)[:60]}")
