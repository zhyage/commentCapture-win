# -*- coding: utf-8 -*-
"""ASR 转写: faster-whisper 封装 (本地模型, CPU/GPU)

策略 (2026-08-28 固化):
- 默认单遍 VAD=True (口播密集视频, 快)
- adaptive 两遍: 第1遍 VAD=True → 语音覆盖率过低(疑似 BGM/现场音导致 VAD 误杀)
  → 第2遍 VAD=False 重跑, 覆盖率更高者胜出
"""
import os
from pathlib import Path

LOW_COVERAGE_THRESHOLD = 0.35   # 语音覆盖率低于此 → VAD 可能误杀, 触发第2遍


def decide_pass(cov1: float, cov2: float | None, threshold: float) -> str:
    """纯决策: 返回 "single"|"pass2"|"keep1"。供单测。"""
    if cov2 is None:
        return "single"
    if cov2 > cov1:
        return "pass2"
    return "keep1"


def _load_and_run(model_path: str, media_path: str, dev: str, language: str,
                  vad_filter: bool, beam_size: int = 5):
    """加载模型并转写一次, 返回 (segments_dicts, coverage, duration)"""
    from faster_whisper import WhisperModel
    model = WhisperModel(model_path, device=dev, compute_type="int8")
    segments, info = model.transcribe(media_path, language=language,
                                      vad_filter=vad_filter, beam_size=beam_size)
    segs = [
        {"index": i + 1, "start": round(s.start, 2), "end": round(s.end, 2),
         "text": s.text.strip()}
        for i, s in enumerate(segments)
    ]
    duration = float(getattr(info, "duration", 0) or 0)
    cov = (sum(min(s["end"], duration) - s["start"] for s in segs) / duration
           if segs and duration > 0 else 0.0)
    return segs, cov, duration


def transcribe(media_path: str | Path,
               model_name: str = "medium",
               device: str = "cpu",
               local_model: str | None = None,
               language: str = "zh",
               vad_filter: bool = True) -> list[dict]:
    """单遍转写 (保留原签名/行为)。返回字幕段列表。GPU 失败自动回退 CPU。"""
    media_path = str(media_path)
    model_path = str(local_model) if local_model else model_name
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    def _run(dev: str):
        segs, _cov, _dur = _load_and_run(model_path, media_path, dev, language, vad_filter)
        return segs

    try:
        return _run(device)
    except Exception as e:
        if device != "cpu":
            print(f">> ASR {device} 失败({str(e)[:60]}), 回退 CPU")
            try:
                return _run("cpu")
            except Exception as e2:
                raise RuntimeError(f"ASR CPU 也失败: {str(e2)[:100]}") from e2
        raise


def transcribe_adaptive(media_path: str | Path,
                        model_name: str = "medium",
                        device: str = "cpu",
                        local_model: str | None = None,
                        language: str = "zh",
                        low_coverage_threshold: float = LOW_COVERAGE_THRESHOLD) -> dict:
    """策略3: 两遍自适应转写。
    第1遍 VAD=True 快扫; 语音覆盖率 < threshold → 第2遍 VAD=False 重跑, 取覆盖率更高者。
    返回 {"segments": [...], "coverage": float, "duration": float, "passes": int,
          "used_vad": bool, "note": str}"""
    media_path = str(media_path)
    model_path = str(local_model) if local_model else model_name
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    def _run_vad(vad: bool):
        # 复用 transcribe 的 GPU→CPU 回退语义, 但需要 coverage, 故在此实现
        try:
            return _load_and_run(model_path, media_path, device, language, vad)
        except Exception as e:
            if device != "cpu":
                print(f">> ASR {device} 失败({str(e)[:60]}), 回退 CPU")
                return _load_and_run(model_path, media_path, "cpu", language, vad)
            raise

    segs1, cov1, dur = _run_vad(True)
    if cov1 >= low_coverage_threshold:
        return {"segments": segs1, "coverage": cov1, "duration": dur,
                "passes": 1, "used_vad": True,
                "note": f"VAD=True 覆盖率 {cov1:.0%}, 未触发第2遍"}
    segs2, cov2, dur2 = _run_vad(False)
    decision = decide_pass(cov1, cov2, low_coverage_threshold)
    if decision == "pass2":
        return {"segments": segs2, "coverage": cov2, "duration": dur2,
                "passes": 2, "used_vad": False,
                "note": f"VAD=False 覆盖率 {cov2:.0%} > {cov1:.0%}, 采用第2遍"}
    return {"segments": segs1, "coverage": cov1, "duration": dur,
            "passes": 2, "used_vad": True,
            "note": f"第2遍未提升({cov2:.0%} <= {cov1:.0%}), 保留 VAD=True"}


def write_subtitles(segments: list[dict], out_dir: str | Path, prefix: str) -> dict:
    """写 srt/txt/json, 返回 {srt, txt, json} 路径"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / f"{prefix}.json",
        "txt": out / f"{prefix}.txt",
        "srt": out / f"{prefix}.srt",
    }
    paths["json"].write_text(
        __import__("json").dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"[{s['start']:07.2f} -> {s['end']:07.2f}] {s['text']}" for s in segments]
    paths["txt"].write_text("\n".join(lines), encoding="utf-8")
    with paths["srt"].open("w", encoding="utf-8") as f:
        for i, s in enumerate(segments, 1):
            f.write(f"{i}\n{_fmt_time(s['start'])} --> {_fmt_time(s['end'])}\n{s['text']}\n\n")
    return {k: str(v) for k, v in paths.items()}


def _fmt_time(t: float) -> str:
    h, rem = int(t // 3600), t % 3600
    m, rem = int(rem // 60), rem % 60
    s, ms = int(rem), int((rem % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
