# -*- coding: utf-8 -*-
"""跑 v0c 关键帧提取: data/douyin 下所有视频 → keyframes/*.jpg + keyframes.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smfetch.keyframes import extract_keyframes  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "douyin"


def main():
    videos = sorted(p for p in DATA.glob("*/video.mp4") if p.stat().st_size > 1_000_000)
    if not videos:
        print("没有可分析的视频")
        return
    for vp in videos:
        vid = vp.parent.name
        print(f">> 关键帧提取 {vid} ...")
        result = extract_keyframes(str(vp), vp.parent / "keyframes")
        meta = {k: v for k, v in result.items() if k != "keyframes"}
        (vp.parent / "keyframes.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   镜头 {meta['num_scenes']} 个 → 关键帧 {meta['num_keyframes']} 张"
              f" ({vp.parent / 'keyframes'})")
    print("完成")


if __name__ == "__main__":
    main()
