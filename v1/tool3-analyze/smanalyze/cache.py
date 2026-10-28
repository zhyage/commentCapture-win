# -*- coding: utf-8 -*-
"""标注缓存: JSONL 追加存储, key = hash(text + task_id + prompt_version + model)

作用: ①省钱 ②重跑快 ③保证同一次研究内同一文本标签一致
缓存失效: 换 model 或改任务定义(prompt_ver 变化) → key 变化 → 自动重标
"""
import hashlib
import json
from pathlib import Path


def cache_key(text: str, task_id: str, prompt_version: str, model: str) -> str:
    raw = f"{text}\x00{task_id}\x00{prompt_version}\x00{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class LabelCache:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._map: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                self._map[rec["key"]] = rec
            except Exception:
                continue

    def get(self, key: str) -> dict | None:
        return self._map.get(key)

    def put(self, key: str, record: dict) -> None:
        self._map[key] = record

    def flush(self) -> None:
        """整体重写(去重后), 由主线程调用, 避免并发写冲突"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(r, ensure_ascii=False) for r in self._map.values()]
        self.path.write_text("\n".join(lines), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._map)
