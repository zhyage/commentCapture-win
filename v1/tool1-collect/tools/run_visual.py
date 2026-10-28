# -*- coding: utf-8 -*-
"""跑 v0a 视觉特征: 对 data/douyin 下所有已下载视频生成 visual.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smfetch.visual import extract_visual_features  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "douyin"


def main():
    videos = sorted(p for p in DATA.glob("*/video.mp4") if p.stat().st_size > 1_000_000)
    if not videos:
        print("没有可分析的视频 (需先抓取并下载)")
        return
    for vp in videos:
        vid = vp.parent.name
        out = vp.parent / "visual.json"
        print(f">> 分析 {vid} ({vp.stat().st_size/1048576:.1f}MB)...")
        result = extract_visual_features(vp)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        m = result["metrics"]
        print(f"   出镜{int(m['person_presence_ratio']*100)}% | 人脸max={m['face_count_max']} avg={m['face_count_avg']}"
              f" | 自拍分={m['selfie_score']} | 运动={m['dominant']} (抖动{m['shake_index']})")
        print(f"   -> {out}")
    print("完成")


if __name__ == "__main__":
    main()
