# -*- coding: utf-8 -*-
"""DeepSeek 客户端 (urllib, 零依赖; 与工具1 correct.py / 工具2 llm.py 同模式)

只做一件事: 发 JSON 请求 → 取回 JSON 对象。重试由调用方控制。
"""
import json
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, cfg: dict):
        ds = (cfg or {}).get("deepseek") or {}
        self.api_key = ds.get("api_key")
        if not self.api_key:
            raise LLMError("缺少 deepseek.api_key 配置")
        self.base_url = (ds.get("base_url") or "https://api.deepseek.com").rstrip("/")
        self.model = ds.get("model") or "deepseek-chat"

    def chat_json(self, system: str, user: str, temperature: float = 0.1,
                  timeout_s: int = 120) -> dict:
        """调用 chat completions, 返回解析后的 JSON 对象"""
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")
        except Exception as e:
            raise LLMError(f"{type(e).__name__}: {str(e)[:150]}")
        try:
            content = resp["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            raise LLMError(f"返回解析失败: {str(e)[:120]}")
