# -*- coding: utf-8 -*-
"""
阶段3: 下载视频 + Whisper 转写口播字幕
用法: python step3_download_asr.py [--model small|medium|large-v3]
      (默认 small; 中文效果更好可选 medium, 首次运行会下载模型)
输出: output/videos/{id}.mp4, output/subtitles/{id}.srt / .txt / .json
"""
import argparse
import json
import os
import sys
from pathlib import Path

# 国内网络: Whisper 模型走 hf-mirror.com 镜像 (必须在导入 faster_whisper 之前设置)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from dy_browser import launch
from dyconfig import JSON_DIR, VIDEO_DIR, SUBTITLE_DIR, OUT, USER_AGENT


def pick_play_urls(aweme: dict):
    """从详情数据里收集所有可用的视频直链, 优先无水印"""
    video = (aweme or {}).get("video") or {}
    candidates = []
    for key in ("play_addr", "play_addr_265", "play_addr_h264", "download_addr"):
        addr = video.get(key) or {}
        candidates += addr.get("url_list") or []
    for br in video.get("bit_rate") or []:
        addr = (br.get("play_addr") or {})
        candidates += addr.get("url_list") or []
    seen, ordered = set(), []
    for u in candidates:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    # 排序: 无水印优先
    ordered.sort(key=lambda u: ("wm" not in u, len(u)), reverse=True)
    return ordered


def download(ctx, url: str, dest: Path) -> bool:
    resp = ctx.request.get(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": "https://www.douyin.com/",
    }, timeout=120000)
    ctype = resp.headers.get("content-type", "")
    if resp.status == 200 and ("video" in ctype or dest.suffix.lower() == ".mp4"):
        if len(resp.body()) > 10000:   # 至少 10KB, 排除错误页
            dest.write_bytes(resp.body())
            return True
    return False


def fmt_time(t: float) -> str:
    h, rem = int(t // 3600), t % 3600
    m, rem = int(rem // 60), rem % 60
    s, ms = int(rem), int((rem % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="small",
                    help="whisper模型: tiny/small/medium/large-v3")
    ap.add_argument("--device", default="cpu",
                    help="cpu 或 cuda (GPU需要nvidia-cublas/cudnn运行库)")
    args = ap.parse_args()

    if not (OUT / "video_id.txt").exists():
        print(">> 没有 video_id.txt, 请先运行 step2_scrape.py")
        sys.exit(1)
    video_id = (OUT / "video_id.txt").read_text(encoding="utf-8").strip()
    detail = json.loads((JSON_DIR / "detail.json").read_text(encoding="utf-8"))
    aw = detail.get("aweme") or {}
    if not aw:
        print(">> detail.json 里没有视频数据")
        sys.exit(1)

    # 1) 下载视频 (无头浏览器 + 已保存登录态, 不需要你盯着)
    p, ctx, _ = launch(headless=True)
    urls = pick_play_urls(aw)
    print(f">> 候选直链 {len(urls)} 个")
    mp4 = VIDEO_DIR / f"{video_id}.mp4"
    ok = False
    if mp4.exists() and mp4.stat().st_size > 1000000:
        print(f">> 视频已存在, 跳过下载: {mp4} ({mp4.stat().st_size / 1024 / 1024:.1f} MB)")
        ok = True
    else:
        for u in urls:
            try:
                print(f">> 尝试下载: {u[:90]}...")
                if download(ctx, u, mp4):
                    print(f">> 下载成功: {mp4} ({mp4.stat().st_size / 1024 / 1024:.1f} MB)")
                    ok = True
                    break
            except Exception as e:
                print(f">> 该地址失败: {e}")
    ctx.close()
    p.stop()
    if not ok:
        print(">> 所有直链均下载失败 (可能需要登录态或触发风控)")
        sys.exit(1)

    # 2) Whisper 转写 (模型下载带重试, 防网络拦截层的间歇性失败)
    print(f">> 转写中 (模型: {args.model}; 首次运行需下载模型, 约几百MB)...")
    from faster_whisper import WhisperModel
    model = None
    for attempt in range(5):
        try:
            model = WhisperModel(args.model, device=args.device, compute_type="int8")
            break
        except Exception as e:
            print(f">> 模型加载失败(第{attempt+1}/5次): {str(e)[:120]}")
            if attempt < 4:
                print(">> 10秒后重试...")
                import time as _t
                _t.sleep(10)
    if model is None:
        print(">> 模型始终无法加载, 请检查网络后重试")
        sys.exit(1)
    segments, info = model.transcribe(str(mp4), language="zh", vad_filter=True)

    segs, lines = [], []
    for s in segments:
        segs.append({"start": round(s.start, 3), "end": round(s.end, 3),
                     "text": s.text.strip()})
        lines.append(f"[{s.start:07.2f} -> {s.end:07.2f}] {s.text.strip()}")

    (SUBTITLE_DIR / f"{video_id}.json").write_text(
        json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
    (SUBTITLE_DIR / f"{video_id}.txt").write_text(
        "\n".join(lines), encoding="utf-8")
    with (SUBTITLE_DIR / f"{video_id}.srt").open("w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            f.write(f"{i}\n{fmt_time(s['start'])} --> {fmt_time(s['end'])}\n{s['text']}\n\n")

    print(f">> 完成! 共 {len(segs)} 条字幕段")
    print(f">> 文件: output/subtitles/{video_id}.srt / .txt / .json")


if __name__ == "__main__":
    main()
