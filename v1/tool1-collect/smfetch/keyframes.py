# -*- coding: utf-8 -*-
"""v0c 关键帧提取: 场景切换检测 (PySceneDetect ContentDetector)

定义(操作化):
- 关键帧 = 每个视觉镜头的起始帧 (内容突变处取一帧代表)
- 目标: 用最少帧覆盖视频全部视觉内容, 供 VLM/人工判断(工作人员出镜/非正式场景)与 v0a/v0b 分数核验

注意: 运行于 ASCII 路径的 3.12 venv (scenedetect 装在 venv312):
    %LOCALAPPDATA%/smfetch/venv312/Scripts/python.exe tools/run_keyframes.py
"""
import json
from pathlib import Path

import cv2


def detect_scenes(video_path: str, threshold: float = 27.0):
    """返回镜头列表 [(start_frame, start_sec, end_frame, end_sec), ...]"""
    from scenedetect import ContentDetector, SceneManager, open_video
    video = open_video(video_path)
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold))
    sm.detect_scenes(video)
    fps = float(video.frame_rate) or 25.0
    scenes = []
    for s in sm.get_scene_list():
        start_f = int(s[0].get_frames())
        end_f = int(s[1].get_frames())
        scenes.append((start_f, round(start_f / fps, 2),
                       end_f, round(end_f / fps, 2)))
    return scenes, fps


def extract_keyframes(video_path: str,
                      out_dir: str | Path,
                      threshold: float = 27.0,
                      max_keyframes: int = 40) -> dict:
    """场景切换检测 → 保存每个镜头的起始帧为 jpg + 返回元数据"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    scenes, fps = detect_scenes(video_path, threshold)
    if not scenes:   # 无场景切换 → 均匀取首帧兜底
        scenes = [(0, 0.0, 0, 0.0)]

    keyframes = []
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    for i, (start_f, start_s, end_f, end_s) in enumerate(scenes[:max_keyframes]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        ok, frame = cap.read()
        if not ok:
            continue
        fname = f"kf_{i+1:03d}_t{start_s:06.2f}.jpg"
        # cv2.imwrite 对中文路径静默失败 → 用字节写
        _ok, buf = cv2.imencode(".jpg", frame)
        if _ok:
            (out / fname).write_bytes(buf.tobytes())
        keyframes.append({
            "index": i + 1, "file": fname,
            "t_sec": start_s, "start_frame": start_f,
            "end_frame": end_f, "end_sec": end_s,
        })
    cap.release()

    return {
        "engine": "v0c-scenedetect-content",
        "threshold": float(threshold),
        "video_fps": round(fps, 2),
        "total_frames": int(total),
        "num_scenes": int(len(scenes)),
        "num_keyframes": int(len(keyframes)),
        "keyframes": keyframes,
    }
