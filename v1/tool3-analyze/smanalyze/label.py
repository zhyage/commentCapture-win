# -*- coding: utf-8 -*-
"""标注流水线: 抽样 → 分批 → 缓存 → 并发调用 → 解析校验 → 落盘 → 抽检

设计要点 (DESIGN §5):
- 抽样策略显式(all / random_n / top_likes_n)
- 缓存保证同一次研究内标签一致
- 并发(max_workers) + 单批重试 + 失败率熔断
- 标签合法性校验; 非法/缺失记 null 并保留原因
- 标注结果单独落盘(labels_*.csv), 可 JOIN 回变量表
"""
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .cache import LabelCache, cache_key
from .llm import DeepSeekClient, LLMError
from .tasks import TaskDef


# ---------- 抽样 ----------
def sample_items(items: list, strategy: str, n: int, rng=None) -> list:
    """items: 待标注列表。strategy: all | random_n | top_likes_n"""
    if strategy == "all" or n <= 0 or len(items) <= n:
        return list(items)
    rng = rng or random.Random(42)          # 固定种子 → 抽样可复现
    if strategy == "random_n":
        return rng.sample(items, n)
    if strategy == "top_likes_n":
        return sorted(items, key=lambda x: -(x.get("likes") or 0))[:n]
    raise ValueError(f"未知抽样策略: {strategy}")


def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]


# ---------- 单批标注 ----------
def label_batch(client: DeepSeekClient, task: TaskDef, batch: list,
                temperature: float, timeout_s: int, max_retries: int) -> list:
    """标注一批; 返回 [{i, label, why, ok, error}] (与 batch 等长)"""
    payload = [{"i": it["i"], "text": (it["text"] or "")[:task.max_input_chars]}
               for it in batch]
    last_err = ""
    for attempt in range(max_retries + 1):
        try:
            out = client.chat_json(task.system_prompt(), task.user_prompt(payload),
                                   temperature=temperature, timeout_s=timeout_s)
            return _parse(out, batch, task)
        except LLMError as e:
            last_err = str(e)[:120]
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))     # 退避重试
    return [{"i": it["i"], "label": None, "why": "", "ok": False,
             "error": f"批次失败: {last_err}"} for it in batch]


def _parse(out: dict, batch: list, task: TaskDef) -> list:
    """校验 LLM 返回: index 对齐 + 标签合法"""
    got = {}
    for item in (out.get("items") or []):
        try:
            got[int(item.get("i"))] = item
        except Exception:
            continue
    results = []
    label_field = "level" if "level" in task.output_fields else task.output_fields[0]
    for it in batch:
        item = got.get(it["i"])
        if not item:
            results.append({"i": it["i"], "label": None, "why": "",
                            "ok": False, "error": "返回缺少该序号"})
            continue
        raw = item.get(label_field)
        if task.is_valid_label(raw):
            results.append({"i": it["i"], "label": str(raw),
                            "why": str(item.get("why", ""))[:200], "ok": True,
                            "error": ""})
        else:
            results.append({"i": it["i"], "label": None, "why": str(item.get("why", ""))[:200],
                            "ok": False, "error": f"非法标签: {raw}"})
    return results


# ---------- 主流程 ----------
def run_labeling(items: list, task: TaskDef, cfg: dict, out_dir: Path,
                 strategy: str = "all", sample_n: int = 0,
                 dry_run: bool = False, progress: bool = True) -> dict:
    """items: [{"id","text","video_id"?,"likes"?}]  (id = comment_id 或 video_id)
    返回 {"rows": [...], "stats": {...}}"""
    lc = (cfg or {}).get("label") or {}
    batch_size = int(lc.get("batch_size", 10))
    workers = max(1, int(lc.get("max_workers", 5)))
    max_retries = int(lc.get("max_retries", 2))
    temperature = float(lc.get("temperature", 0.1))
    timeout_s = int(lc.get("timeout_s", 120))
    fail_stop = float(lc.get("fail_rate_stop", 0.2))
    sample_n = sample_n or int(lc.get("sample_n", 20))

    picked = sample_items(items, strategy, sample_n)
    batches = chunk(list(enumerate(picked, start=1)), batch_size)
    # 每条加序号
    prepared = []
    for idx, it in enumerate(picked, start=1):
        prepared.append({**it, "i": idx})

    cache = LabelCache(out_dir / ".labels_cache.jsonl")
    client = None if dry_run else DeepSeekClient(cfg)
    model = (cfg.get("deepseek") or {}).get("model", "deepseek-chat")

    # 缓存命中
    todo_batches = []
    cached_rows = []
    hits = 0
    for b in chunk(prepared, batch_size):
        need = []
        for it in b:
            k = cache_key(it["text"] or "", task.task_id, task.prompt_version, model)
            rec = cache.get(k)
            if rec and rec.get("ok"):
                hits += 1
                cached_rows.append({
                    "id": rec.get("id", it["id"]), "video_id": rec.get("video_id", it.get("video_id")),
                    "task_id": rec.get("task_id", task.task_id),
                    "label": rec.get("label"), "why": rec.get("why", ""), "ok": True,
                    "error": "", "model": rec.get("model", model),
                    "prompt_version": rec.get("prompt_version", task.prompt_version),
                    "cached": True, "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "text": (it["text"] or "")[:120],
                })
            else:
                need.append(it)
        if need:
            todo_batches.append(need)

    est_calls = len(todo_batches)
    stats = {
        "task_id": task.task_id, "level": task.level,
        "total_items": len(items), "sampled": len(prepared),
        "sample_strategy": strategy, "batch_size": batch_size,
        "workers": workers, "cache_hits": hits,
        "todo_batches": est_calls, "est_calls": est_calls,
        "model": model, "prompt_version": task.prompt_version,
        "dry_run": dry_run,
    }
    if dry_run:
        stats["est_input_tokens"] = int(len(prepared) * 40 + est_calls * 350)
        stats["est_output_tokens"] = int(len(prepared) * 12)
        return {"rows": [], "stats": stats}

    lock = threading.Lock()
    done_batches = [0]
    rows = list(cached_rows)
    failures = 0

    def work(b):
        res = label_batch(client, task, b, temperature, timeout_s, max_retries)
        with lock:
            done_batches[0] += 1
            if progress:
                print(f"   批 {done_batches[0]}/{est_calls} "
                      f"(累计 {len(rows) + len(res)} 条)", flush=True)
        return b, res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(work, b) for b in todo_batches]
        for fut in as_completed(futures):
            b, res = fut.result()
            for it, r in zip(b, res):
                row = {
                    "id": it["id"], "video_id": it.get("video_id"),
                    "task_id": task.task_id, "text": (it["text"] or "")[:120],
                    "label": r["label"], "why": r["why"], "ok": r["ok"],
                    "error": r["error"], "model": model,
                    "prompt_version": task.prompt_version,
                    "cached": False, "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                }
                rows.append(row)
                if not r["ok"]:
                    failures += 1
                else:
                    k = cache_key(it["text"] or "", task.task_id, task.prompt_version, model)
                    cache.put(k, {"key": k, "id": it["id"], "video_id": it.get("video_id"),
                                  "task_id": task.task_id, "label": r["label"],
                                  "why": r["why"], "ok": True, "model": model,
                                  "prompt_version": task.prompt_version})
            if est_calls and failures / max(1, len(rows)) > fail_stop:
                print(f"   !! 失败率过高({failures}/{len(rows)}), 停止后续批次", flush=True)
                for f in futures:
                    f.cancel()
                break

    cache.flush()
    rows.sort(key=lambda r: (r["task_id"], str(r["id"])))
    stats.update({"done": len(rows), "failures": failures,
                  "fail_rate": round(failures / len(rows), 4) if rows else 0.0,
                  "cache_size": len(cache)})
    return {"rows": rows, "stats": stats}


# ---------- 落盘 ----------
def write_labels(rows: list, path: Path) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "video_id", "task_id", "label", "why", "ok", "error",
              "model", "prompt_version", "cached", "ts", "text"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_sample_md(rows: list, task: TaskDef, path: Path, n: int = 20, rng=None) -> None:
    """抽检样本: 随机 n 条, 供人工复核"""
    ok_rows = [r for r in rows if r.get("ok")]
    rng = rng or random.Random(7)
    picked = rng.sample(ok_rows, min(n, len(ok_rows))) if ok_rows else []
    lines = [f"# 标注抽检样本 — {task.name} ({task.task_id})", "",
             f"- 抽样: 随机 {len(picked)} / 成功 {len(ok_rows)} 条",
             f"- 模型: {rows[0]['model'] if rows else '-'} | prompt_ver: {task.prompt_version}",
             f"- 标签体系: {json.dumps(task.labels, ensure_ascii=False)}", "",
             "> 请人工核对以下标注是否正确; 若错误率高, 需调整 prompt_hint 或标签体系后重标。", ""]
    for i, r in enumerate(picked, 1):
        lines += [f"## {i}. [{r['label']}]",
                  f"- 文本: {r['text']}",
                  f"- LLM 理由: {r['why']}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
