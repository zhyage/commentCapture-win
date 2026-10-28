# -*- coding: utf-8 -*-
"""存量回填: 为 data/douyin 下已有的 video.json 补上覆盖率结构化字段"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smfetch.schema import compute_coverage, compute_author_engagement  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "douyin"


def main():
    n = 0
    for d in sorted(DATA.iterdir()):
        if not d.is_dir():
            continue
        vp, cp = d / "video.json", d / "comments.json"
        if not (vp.exists() and cp.exists()):
            continue
        v = json.loads(vp.read_text(encoding="utf-8"))
        records = json.loads(cp.read_text(encoding="utf-8"))
        pt = (v.get("comments") or {}).get("platform_total")
        cov = compute_coverage(records, pt)
        v["comments"].update({
            "top_level_count": cov["top_level_count"],
            "reply_count": cov["reply_count"],
            "author_reply_count": cov["author_reply_count"],
            "top_level_coverage": cov["top_level_coverage"],
            "collected_count": len(records),
            "coverage_note": (
                f"安全模式采样; 平台总数 {pt}; "
                f"顶层 {cov['top_level_count']} (覆盖率 {cov['top_level_coverage']}), "
                f"回复 {cov['reply_count']}, 作者回复 {cov['author_reply_count']}; "
                f"多次运行按comment_id去重合并"),
        })
        v["author_engagement"] = compute_author_engagement(records).__dict__
        vp.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"回填 {d.name}: 顶层{cov['top_level_count']} 回复{cov['reply_count']} "
              f"作者回复{cov['author_reply_count']} 覆盖率{cov['top_level_coverage']}")
        n += 1
    print(f"完成, 回填 {n} 个视频")


if __name__ == "__main__":
    main()
