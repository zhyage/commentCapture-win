# -*- coding: utf-8 -*-
"""从 ModelScope 下载 faster-whisper-medium 模型 (国内直连, 无需VPN)"""
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = "Systran/faster-whisper-medium"
DEST = Path(".cache/hf-local/faster-whisper-medium")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"}

FILES = [
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
    "preprocessor_config.json",
]


def download(url, dest: Path, retries=5):
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        print(f"\r  {dest.name}: {done/1048576:.0f}/{total/1048576:.0f} MB ({pct}%)", end="")
            print()
            tmp.replace(dest)
            return True
        except Exception as e:
            print(f"\n  {dest.name} 第{attempt}次失败: {str(e)[:80]}")
            if attempt < retries:
                time.sleep(5)
    return False


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    # 先探测哪些文件存在
    exists = []
    for f in FILES:
        url = f"https://www.modelscope.cn/models/{REPO}/resolve/master/{f}"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                exists.append(f)
        except Exception:
            print(f"跳过(不存在): {f}")
    print("待下载:", exists)
    ok = True
    for f in exists:
        dest = DEST / f
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"已存在, 跳过: {f} ({dest.stat().st_size/1048576:.0f} MB)")
            continue
        url = f"https://www.modelscope.cn/models/{REPO}/resolve/master/{f}"
        print(f"下载 {f} ...")
        if not download(url, dest):
            ok = False
            print(f"!! {f} 下载失败")
    print()
    if ok:
        print("全部下载完成!")
        for f in sorted(DEST.iterdir()):
            print(f"  {f.name}: {f.stat().st_size/1048576:.1f} MB")
    else:
        print("有文件失败, 请重试")
        sys.exit(1)


if __name__ == "__main__":
    main()
