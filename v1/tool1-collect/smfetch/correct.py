# -*- coding: utf-8 -*-
"""字幕 LLM 修正 (DeepSeek): 用 video.json 的文案背景修正 ASR 专名/同音错字

原则 (可追溯, 不污染原始数据):
- 原始 ASR 字幕文件不动; 修正结果写独立文件 (subtitles.llm.*)
- 仅依据 字幕文本 + 文案背景 推断; 无依据片段保持原文并追加 "[识别不确定]"
- 温度低(0.2), 要求 JSON 输出; 修正后 timecode 不变
"""
import json
import urllib.request


def correct_segments(segments: list[dict], context: dict, cfg: dict,
                     timeout_s: int = 120) -> dict:
    """调 DeepSeek 修正字幕段。
    segments: [{index,start,end,text}]
    context:  {caption, hashtags, author, publish_time} (video.json 背景)
    cfg:      {"deepseek": {api_key, model, base_url}} 或含该键的完整配置
    返回 {"segments": 修正后[{index,start,end,text}], "raw": 模型原样返回, "note": ""}
    """
    ds = (cfg or {}).get("deepseek") or {}
    api_key = ds.get("api_key")
    if not api_key:
        raise RuntimeError("缺少 deepseek.api_key 配置 (smfetch 需联网做字幕修正)")
    url = (ds.get("base_url") or "https://api.deepseek.com").rstrip("/") + "/chat/completions"
    model = ds.get("model") or "deepseek-chat"

    sys_prompt = """你是口播字幕修正助手。给出一段视频的: (1) 平台文案(描述视频内容/人物/地点);
(2) 语音识别(ASR)产生的字幕段列表, 含时间轴和可能有错/语义不通的文本。

任务: 依据文案背景修正字幕中明显的【专名错误/同音错字/漏字】, 使语义通顺且忠实于原话。
规则:
- 只能利用字幕文本 + 文案背景推断; 不要无中生有添加字幕没有的内容
- 对修正没有把握、文案也给不出线索的片段: 保持原文, 并在该段 text 后追加" [识别不确定]"
- 输出 JSON 对象, 键 "segments": [{index, text}] ; index 必须与输入一一对应
- 不要改时间轴; 不要改动字幕中没有依据的细节
"""
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(
                {"context": context, "segments": segments}, ensure_ascii=False)},
        ],
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        resp = json.loads(r.read().decode("utf-8"))
    raw = resp["choices"][0]["message"]["content"]
    corrected = _merge(segments, raw)
    return {"segments": corrected, "raw": raw,
            "note": f"LLM 修正 (model={model}); 无依据片段保留原文并标注; 属派生可追溯数据"}


def _merge(original: list[dict], llm_raw: str) -> list[dict]:
    """把 LLM 返回的 [{index,text}] 合并回原段时间轴; 解析失败则原样返回"""
    try:
        obj = json.loads(llm_raw)
        fixes = {int(s["index"]): s["text"] for s in obj.get("segments", [])}
    except Exception:
        return [dict(s) for s in original]
    out = []
    for s in original:
        s2 = dict(s)
        t = fixes.get(int(s["index"]))
        if t is not None:
            s2["text"] = str(t).strip()
        out.append(s2)
    return out
