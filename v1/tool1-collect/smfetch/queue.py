# -*- coding: utf-8 -*-
"""批量队列: JSONL 持久化, 断点续跑, 受阻清单"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

STATES = ("pending", "done", "blocked")


@dataclass
class QueueItem:
    target: str                       # 短链或ID
    state: str = "pending"
    error: str = ""
    retries: int = 0
    updated_at: str = ""

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class TaskQueue:
    """按 target 去重; done 跳过; blocked 保留待重试"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.items: dict[str, QueueItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                self.items[d["target"]] = QueueItem(**d)
            except Exception:
                continue

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(asdict(v), ensure_ascii=False) for v in self.items.values()]
        self.path.write_text("\n".join(lines), encoding="utf-8")

    # --- 操作 ---
    def add(self, targets: list[str]) -> int:
        """加入队列, 已存在(任意状态)的不重复添加。返回新增数。"""
        added = 0
        for t in targets:
            t = t.strip()
            if not t or t.startswith("#"):
                continue
            if t in self.items:
                continue
            self.items[t] = QueueItem(target=t, updated_at=QueueItem.now())
            added += 1
        self._save()
        return added

    def next_pending(self) -> QueueItem | None:
        for item in self.items.values():
            if item.state == "pending":
                return item
        return None

    def mark_done(self, target: str) -> None:
        if target in self.items:
            self.items[target].state = "done"
            self.items[target].updated_at = QueueItem.now()
            self._save()

    def mark_blocked(self, target: str, error: str = "") -> None:
        if target in self.items:
            it = self.items[target]
            it.state = "blocked"
            it.error = error[:300]
            it.retries += 1
            it.updated_at = QueueItem.now()
            self._save()

    def retry_blocked(self, max_retries: int | None = None) -> int:
        """受阻清单重新入队。max_retries: 超过重试次数的保持受阻。返回重新入队数"""
        n = 0
        for it in self.items.values():
            if it.state == "blocked":
                if max_retries is not None and it.retries >= max_retries:
                    continue
                it.state = "pending"
                it.error = ""
                it.updated_at = QueueItem.now()
                n += 1
        self._save()
        return n

    def reset(self) -> None:
        self.items.clear()
        self._save()

    # --- 查询 ---
    def summary(self) -> dict:
        c = {"total": 0, "pending": 0, "done": 0, "blocked": 0}
        for it in self.items.values():
            c["total"] += 1
            c[it.state] = c.get(it.state, 0) + 1
        return c

    def blocked_list(self) -> list[QueueItem]:
        return [it for it in self.items.values() if it.state == "blocked"]
