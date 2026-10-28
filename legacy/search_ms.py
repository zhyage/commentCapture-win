# -*- coding: utf-8 -*-
"""在 ModelScope 搜索 faster-whisper 相关仓库"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"}

urls = [
    ("API1", "https://www.modelscope.cn/api/v1/models?PageNumber=1&PageSize=20&Search=faster-whisper"),
    ("API2", "https://www.modelscope.cn/api/v1/models?PageNumber=1&PageSize=20&Name=faster-whisper"),
    ("API3", "https://modelscope.cn/api/v1/models?PageNumber=1&PageSize=20&Search=faster-whisper"),
]

seen = set()
for name, url in urls:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        models = data.get("Data", {}).get("Models") or data.get("models") or data.get("Data") or []
        if isinstance(models, dict):
            models = models.get("Models") or []
        for m in models:
            mid = m.get("Path") or m.get("Id") or m.get("Name") or ""
            if "faster-whisper" in mid.lower() and mid not in seen:
                seen.add(mid)
                print(f"[{name}] {mid}")
        if not models:
            print(f"[{name}] 无结果, 原始keys: {list(data.keys())[:6]}")
    except Exception as e:
        print(f"[{name}] FAIL {str(e)[:90]}")
