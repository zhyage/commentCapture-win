# -*- coding: utf-8 -*-
"""v0b: CLIP 零样本场景语义 (专业/非专业场景)

- 用 CLIP (ViT-B/32) 对每帧与候选场景标签做图文相似度
- professional_score = 专业侧标签概率之和 (连续分, 研究端定阈值)
- 输出 scene.json (与 visual.json 并列的派生数据)

注意: 运行于 ASCII 路径的 3.12 venv (torch/CLIP 装在 venv312):
    %LOCALAPPDATA%/smfetch/venv312/Scripts/python.exe tools/run_scene.py
"""
import cv2

PROFESSIONAL_LABELS = [
    "TV studio", "conference room", "press conference",
    "office", "stage", "exhibition booth",
]
DAILY_LABELS = [
    "street", "tourist attraction", "living room",
    "car interior", "outdoor park", "restaurant",
]
ALL_LABELS = PROFESSIONAL_LABELS + DAILY_LABELS


def load_model(device: str = "cpu"):
    """加载 CLIP ViT-B/32 + 文本特征 (首次运行下载权重 ~350MB)"""
    import open_clip
    import torch
    model, _preprocess, _ = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai", device=device, quick_gelu=True)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    with torch.no_grad():
        text_features = model.encode_text(tokenizer(ALL_LABELS))
        text_features /= text_features.norm(dim=-1, keepdim=True)
    return model, _preprocess, text_features, device


def score_frame(frame_bgr, model, preprocess, text_features, device: str) -> dict:
    import torch
    from PIL import Image
    pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    img = preprocess(pil).unsqueeze(0)
    img = img.to(device)
    with torch.no_grad():
        feats = model.encode_image(img)
        feats /= feats.norm(dim=-1, keepdim=True)
        logits = 100.0 * feats @ text_features.T
        probs = torch.softmax(logits, dim=-1)[0].tolist()
    prof = round(sum(probs[:len(PROFESSIONAL_LABELS)]), 4)
    label = ALL_LABELS[probs.index(max(probs))]
    return {
        "label": label,
        "professional_score": prof,
        "probs": {L: round(p, 4) for L, p in zip(ALL_LABELS, probs)},
    }


def extract_scene_features(video_path: str,
                           sample_fps: float = 1.0,
                           max_frames: int = 300,
                           device: str = "cpu") -> dict:
    model, preprocess, text_features, dev = load_model(device)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(round(fps / sample_fps)))
    if total and total // step > max_frames:
        step = max(1, total // max_frames)

    per_frame, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step != 0:
            idx += 1
            continue
        idx += 1
        r = score_frame(frame, model, preprocess, text_features, dev)
        per_frame.append({"t": round(idx / fps, 2), **r})
    cap.release()

    n = len(per_frame)
    prof_scores = [f["professional_score"] for f in per_frame]
    dist = {}
    for f in per_frame:
        dist[f["label"]] = dist.get(f["label"], 0) + 1
    return {
        "engine": "v0b-clip-vitb32",
        "sampling": {"fps": sample_fps, "frames_analyzed": n},
        "metrics": {
            "professional_score_mean": round(sum(prof_scores) / n, 4) if n else 0.0,
            "professional_score_max": round(max(prof_scores), 4) if n else 0.0,
            "scene_distribution": {k: round(v / n, 4) for k, v in dist.items()},
            "dominant_scene": max(dist, key=dist.get) if dist else None,
        },
        "per_frame": per_frame,
    }
