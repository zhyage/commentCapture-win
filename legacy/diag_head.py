# -*- coding: utf-8 -*-
"""测试 HEAD 请求 (huggingface_hub 用 HEAD 拿 ETag)"""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def head(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        etag = r.headers.get("ETag")
        print(f"HEAD OK: {r.status} | etag={etag} | final={r.geturl()[:80]}")
        return True
    except Exception as e:
        print(f"HEAD FAIL: {type(e).__name__} {str(e)[:100]}")
        return False


def main():
    print("--- huggingface.co (直连) ---")
    ok1 = head("https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin")
    print("--- hf-mirror.com (镜像) ---")
    ok2 = head("https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/model.bin")
    print()
    if ok1:
        print(">>> 建议: 直接用 huggingface.co (设 HF_ENDPOINT=https://huggingface.co)")
    elif ok2:
        print(">>> 建议: 用 hf-mirror.com 镜像")
    else:
        print(">>> 两个 HEAD 都不行, 需要手动下载方案")


if __name__ == "__main__":
    main()
