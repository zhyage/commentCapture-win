# -*- coding: utf-8 -*-
"""把某视频的关键帧拼成网格图, 供人工核验"""
import sys
from pathlib import Path

import cv2

sys.stdout.reconfigure(encoding="utf-8")


def make_sheet(vid_dir: Path, cols: int = 5, thumb_w: int = 240):
    import numpy as np
    kf_dir = vid_dir / "keyframes"
    files = sorted(kf_dir.glob("*.jpg"))
    if not files:
        print("无关键帧")
        return
    rows = (len(files) + cols - 1) // cols
    thumb_h = int(thumb_w * 16 / 9)
    sheet = np.zeros((rows * thumb_h, cols * thumb_w, 3), dtype=np.uint8)
    for i, f in enumerate(files):
        # cv2.imread 对中文路径失败 → 字节解码
        data = np.fromfile(str(f), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            continue
        th = cv2.resize(img, (thumb_w, thumb_h))
        r, c = divmod(i, cols)
        sheet[r * thumb_h:(r + 1) * thumb_h, c * thumb_w:(c + 1) * thumb_w] = th
        cv2.putText(sheet, str(i + 1), (c * thumb_w + 5, r * thumb_h + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    out = vid_dir / f"keyframes_sheet_{vid_dir.name}.jpg"
    _ok, buf = cv2.imencode(".jpg", sheet)
    if _ok:
        out.write_bytes(buf.tobytes())
    print(f"网格图: {out} ({len(files)} 帧, {rows}x{cols})")


if __name__ == "__main__":
    base = Path("data/douyin")
    for d in sorted(base.iterdir()):
        if (d / "keyframes").exists():
            make_sheet(d)
