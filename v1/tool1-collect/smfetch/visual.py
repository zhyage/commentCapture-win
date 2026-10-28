# -*- coding: utf-8 -*-
"""视觉特征提取 v0a (mediapipe solutions + opencv 光流, 运行于 ASCII 路径的 3.12 venv)

mediapipe 1.0.1 的 py3.14 wheel 残缺; 0.10.21 完整但 C++ 内核读不了中文路径,
故本模块须用 ASCII 路径下的 3.12 环境运行, 例如:
    C:/Users/zhy/AppData/Local/smfetch/venv312/Scripts/python.exe tools/run_visual.py

产出派生数据 visual.json:
- 真人出镜比例 / 人脸数量 / 自拍指数 / 镜头运动(静止/平移/手持抖动)

定义(操作化, 供研究端参考, 阈值可调):
- person_presence_ratio: 检测到人体姿态(mediapipe Pose)的帧占比
- face_count_max/avg: 每帧人脸数 (mediapipe FaceDetection, 支持侧脸)
- selfie_score: 最大人脸框相对面积的平均 (自拍特征)
- motion_dominant: 静止/平移/手持 分类
- shake_index: 帧间运动幅度变异系数 (抖动程度)
"""
import math
import os
from pathlib import Path

import cv2
import numpy as np

MOTION_STATIC_PX = 0.20      # 平均运动 < 该值 → 静止
MOTION_PAN_PX = 0.35         # 平均运动 > 该值且方向一致 → 平移


def _analyze_frame(frame_bgr, face_det, pose, frame_area: float) -> dict:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    feats = {"faces": 0, "person": False, "face_ratio": 0.0}
    try:  # 人脸
        fr = face_det.process(rgb)
        if fr.detections:
            feats["faces"] = int(len(fr.detections))
            ratios = []
            for d in fr.detections:
                bb = d.location_data.relative_bounding_box
                ratios.append(float(bb.width * bb.height))
            feats["face_ratio"] = round(float(max(ratios)), 4)
    except Exception:
        pass
    try:  # 人体姿态
        pr = pose.process(rgb)
        if pr.pose_landmarks:
            feats["person"] = True
    except Exception:
        pass
    return feats


def classify_motion(mean_px: float, shake_index: float) -> str:
    """纯函数: 运动分类 (可单测)"""
    if mean_px < MOTION_STATIC_PX:
        return "static"
    if shake_index < 0.6 and mean_px > MOTION_PAN_PX:
        return "pan_tilt"
    return "handheld"


def _motion_stats(video_path: str | Path, sample_fps: float = 1.0,
                  max_pairs: int = 400) -> dict:
    """基于光流的帧间运动统计 (降采样灰度, 320px 宽)"""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(fps / sample_fps)))
    mags = []
    prev_gray = None
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step != 0:
            idx += 1
            continue
        idx += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (320, int(320 * gray.shape[0] / gray.shape[1])))
        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, _ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            mags.append(float(np.mean(mag)))
        prev_gray = gray
        if len(mags) >= max_pairs:
            break
    cap.release()
    if not mags:
        return {"pairs": 0, "mean_px": 0.0, "std_px": 0.0,
                "shake_index": 0.0, "dominant": "unknown"}
    m = np.array(mags)
    mean_px = float(np.mean(m))
    std_px = float(np.std(m))
    shake = float(std_px / (mean_px + 1e-6))
    return {"pairs": len(mags), "mean_px": round(mean_px, 3),
            "std_px": round(std_px, 3), "shake_index": round(shake, 3),
            "dominant": classify_motion(mean_px, shake)}


def extract_visual_features(video_path: str | Path,
                            sample_fps: float = 1.0,
                            max_frames: int = 600) -> dict:
    import mediapipe as mp
    face_det = mp.solutions.face_detection.FaceDetection(
        model_selection=0, min_detection_confidence=0.5)
    pose = mp.solutions.pose.Pose(
        model_complexity=0, min_detection_confidence=0.5)

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    dur = total / fps if fps else 0.0
    frame_area = max(1, w * h)
    step = max(1, int(round(fps / sample_fps)))
    if total and total // step > max_frames:
        step = max(1, total // max_frames)

    per_frame = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step != 0:
            idx += 1
            continue
        idx += 1
        f = _analyze_frame(frame, face_det, pose, frame_area)
        per_frame.append({
            "t": round(idx / fps, 2), "faces": f["faces"],
            "person": f["person"], "face_ratio": f["face_ratio"],
        })
    cap.release()
    face_det.close()
    pose.close()

    n = len(per_frame)
    metrics = {"person_presence_ratio": 0.0, "face_count_max": 0,
               "face_count_avg": 0.0, "selfie_score": 0.0}
    if n:
        metrics["person_presence_ratio"] = round(
            sum(1 for f in per_frame if f["person"]) / n, 4)
        fc = [f["faces"] for f in per_frame]
        metrics["face_count_max"] = max(fc)
        metrics["face_count_avg"] = round(sum(fc) / n, 3)
        ratios = [f["face_ratio"] for f in per_frame if f["face_ratio"] > 0]
        metrics["selfie_score"] = round(
            (sum(ratios) / len(ratios)) if ratios else 0.0, 4)

    motion = _motion_stats(video_path, sample_fps)
    return {
        "engine": "v0a-mediapipe-solutions",
        "sampling": {"fps": sample_fps, "frames_analyzed": n},
        "video_meta": {"duration_seconds": round(dur, 2),
                       "resolution": f"{w}x{h}", "total_frames": total},
        "metrics": {**metrics, **motion},
        "per_frame": per_frame,
    }
