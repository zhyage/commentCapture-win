# -*- coding: utf-8 -*-
"""DeepSeek LLM 客户端: 批量语义判定 (OpenAI 兼容接口, urllib 零依赖)"""
import json
import urllib.request


def build_prompt(intents: list, captions: list) -> str:
    items = "\n".join(f"[{i}] {c[:200]}" for i, c in enumerate(captions))
    intents_txt = " / ".join(intents) if intents else "(无)"
    return (
        "判断下面每条视频文案是否符合以下意图(任一意图符合即判'符合'):\n"
        f"意图: {intents_txt}\n\n"
        "文案列表:\n"
        f"{items}\n\n"
        "请严格输出 JSON, 格式: "
        '{"judgments": [{"index": 0, "result": "符合|不符合|不确定"}, ...]} '
        "index 对应文案编号, result 三选一。"
    )


def judge_batch(intents: list, captions: list, cfg: dict) -> list:
    """批量判定, 返回与 captions 等长的 ['符合'|'不符合'|'不确定']。
    任何异常都降级为 '不确定' (诚实: 不假装判定成功)。"""
    n = len(captions)
    if n == 0:
        return []
    dc = cfg["deepseek"]
    url = dc["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": dc["model"],
        "messages": [
            {"role": "system", "content": "你是严谨的判定助手, 只输出 JSON, 不输出其他内容。"},
            {"role": "user", "content": build_prompt(intents, captions)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "max_tokens": 1500,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + dc["api_key"]})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as e:
        print(f"  [LLM] 调用失败, 整批降级为不确定: {str(e)[:100]}")
        return ["不确定"] * n

    results = ["不确定"] * n
    for j in parsed.get("judgments", []):
        idx = j.get("index")
        res = j.get("result", "")
        if isinstance(idx, int) and 0 <= idx < n and res in ("符合", "不符合", "不确定"):
            results[idx] = res
    return results
