# -*- coding: utf-8 -*-
"""标注任务定义加载与校验"""
import hashlib
import json
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class TaskDef:
    def __init__(self, d: dict, source: Path | None = None):
        self.raw = d
        self.source = source
        self.task_id: str = d["task_id"]
        self.name: str = d.get("name") or self.task_id
        self.level: str = d.get("level", "comment")          # comment | video
        self.input_field: str = d.get("input_field", "text")
        self.labels = d.get("labels") or {}
        self.output_fields = d.get("output_fields") or ["label"]
        self.prompt_hint: str = d.get("prompt_hint") or ""
        self.max_input_chars: int = int(d.get("max_input_chars", 500) or 500)
        self.prompt_version: str = self._version()

    def _version(self) -> str:
        """任务定义内容指纹 → 用于缓存失效判定"""
        core = json.dumps({
            "labels": self.labels, "hint": self.prompt_hint,
            "fields": self.output_fields, "max": self.max_input_chars,
            "level": self.level, "input": self.input_field,
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(core.encode("utf-8")).hexdigest()[:8]

    def label_values(self) -> list:
        """合法标签值集合(字符串形式)"""
        return [str(k) for k in self.labels.keys()]

    def is_valid_label(self, v) -> bool:
        return str(v) in self.label_values()

    def system_prompt(self) -> str:
        labels = "\n".join(f"  {k} = {v}" for k, v in self.labels.items())
        fields = ", ".join(self.output_fields)
        return (
            f"你是数据标注助手。任务: {self.name}\n"
            f"标签体系(必须从中选择):\n{labels}\n\n"
            f"判定要点:\n{self.prompt_hint}\n\n"
            f"要求:\n"
            f"- 对每条输入给出标签; 输出 JSON 对象 {{\"items\":[{{\"i\":序号, {fields}}}]}}\n"
            f"- i 必须与输入序号一一对应, 不要遗漏或多出\n"
            f"- 只依据输入文本判断, 不要脑补或添加文本中没有的信息\n"
        )

    def user_prompt(self, items: list) -> str:
        """items: [{"i":1,"text":"..."}]"""
        return json.dumps({"items": items}, ensure_ascii=False)


def load_task(task_id_or_path: str | Path) -> TaskDef:
    import yaml
    p = Path(task_id_or_path)
    if not p.exists():
        p = TASKS_DIR / f"{task_id_or_path}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"任务定义不存在: {task_id_or_path}")
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "task_id" not in d:
        raise ValueError(f"任务定义缺少 task_id: {p}")
    return TaskDef(d, p)


def list_tasks() -> list:
    if not TASKS_DIR.exists():
        return []
    return sorted(p.stem for p in TASKS_DIR.glob("*.yaml"))
