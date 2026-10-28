# -*- coding: utf-8 -*-
"""跑 v0b 场景语义: 对 data/douyin 下所有视频生成 scene.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smfetch.scene import extract_scene_features  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "douyin"


def main():
    videos = sorted(p for p in DATA.glob("*/video.mp4") if p.stat().st_size > 1_000_000)
    if not videos:
        print("没有可分析的视频")
        return
    for vp in videos:
        vid = vp.parent.name
        out = vp.parent / "scene.json"
        print(f">> CLIP 场景分析 {vid} ...")
        result = extract_scene_features(str(vp))
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        m = result["metrics"]
        print(f"   专业度均值={m['professional_score_mean']} | 主场景={m['dominant_scene']}")
        print(f"   分布: {m['scene_distribution']}")
        print(f"   -> {out}")
    print("完成")


if __name__ == "__main__":
    main()
