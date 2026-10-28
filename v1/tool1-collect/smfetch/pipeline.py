# -*- coding: utf-8 -*-
"""管线编排: 单条抓取 / 批量 / 导出 (CLI 的实干层)"""
import sys
from datetime import datetime
from pathlib import Path

from . import asr
from .adapters.douyin import DouyinAdapter
from .config import resolve_path
from .export import comments_to_csv, video_summary_csv, write_json
from .notifier import make_notifier
from .queue import TaskQueue
from .risk import RiskController
from .schema import (CommentsMeta, SubtitleRecord, SubtitlesInfo, VideoRecord,
                     build_comment_list, compute_author_engagement,
                     compute_coverage, parse_hashtags, ts_to_iso)
from .session import SessionExpired


def _item_dir(output: Path, item_id: str) -> Path:
    d = output / "douyin" / item_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_video_record(aweme: dict, item_id: str, source_short_url: str | None = None) -> VideoRecord:
    """原始 aweme → VideoRecord (不含评论/字幕, 由后续填充)"""
    import json as _json
    author = aweme.get("author") or {}
    stats = aweme.get("statistics") or {}
    cert = (_json.loads(author.get("account_cert_info") or "{}") or {}).get("label_text")
    from .schema import AuthorProfile, MediaInfo, Stats
    return VideoRecord(
        platform="douyin",
        platform_item_id=item_id,
        url=f"https://www.douyin.com/video/{item_id}",
        source_short_url=source_short_url,
        collected_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        author=AuthorProfile(
            id=author.get("uid"), nickname=author.get("nickname"),
            certification=cert, signature=author.get("signature"),
            follower_count=author.get("follower_count"),
            following_count=author.get("following_count"),
            favoriting_count=author.get("favoriting_count"),
            total_favorited=author.get("total_favorited"),
            aweme_count=author.get("aweme_count"),
        ),
        caption=aweme.get("desc"),
        hashtags=parse_hashtags(aweme.get("desc")),
        publish_time=ts_to_iso(aweme.get("create_time")),
        stats=Stats(likes=stats.get("digg_count"), comments=stats.get("comment_count"),
                    shares=stats.get("share_count"), collects=stats.get("collect_count"),
                    recommends=stats.get("recommend_count")),
        media=MediaInfo(duration_seconds=round((aweme.get("video") or {}).get("duration", 0) / 1000, 1)),
        comments=CommentsMeta(platform_total=stats.get("comment_count")),
    )


def fetch_one(cfg: dict, base: Path, target: str,
              with_comments: bool = True, with_subtitle: bool = False,
              with_video: bool | None = None,
              model: str | None = None, device: str | None = None,
              force: bool = False) -> dict:
    """抓单条, 落盘, 返回摘要"""
    profile = resolve_path(cfg, "profile_dir", base)
    output = resolve_path(cfg, "output_dir", base)
    risk = RiskController(cfg["pacing"], cfg["safety"])
    adapter = DouyinAdapter(profile, risk)

    item_id = adapter.resolve(target)
    out_dir = _item_dir(output, item_id)

    record_path = out_dir / "video.json"
    if record_path.exists() and not force:
        print(f">> 已存在, 跳过 (--force 可重抓): {record_path}")
        record = VideoRecord.from_dict(_load_json(record_path))
    else:
        aweme = adapter.fetch_video(item_id)
        record = build_video_record(aweme, item_id, source_short_url=target)
        write_json(record.to_dict(), record_path)
        print(f">> 详情已保存: {record_path}")

    if with_comments:
        comments_path = out_dir / "comments.json"
        if comments_path.exists() and not force:
            print(">> 评论已存在, 跳过")
            records = _load_json(comments_path)
            collected = len(records)
        else:
            res = adapter.fetch_comments(item_id)
            records = build_comment_list(res["comments"], record.author.id)
            collected = res["collected"]
            write_json(records, comments_path)
        record.comments.collected_count = collected
        record.comments.file = str(comments_path)
        # 覆盖率结构化写入 (v1.1)
        cov = compute_coverage(records, record.comments.platform_total)
        record.comments.top_level_count = cov["top_level_count"]
        record.comments.reply_count = cov["reply_count"]
        record.comments.author_reply_count = cov["author_reply_count"]
        record.comments.top_level_coverage = cov["top_level_coverage"]
        record.comments.coverage_note = (
            f"安全模式采样; 平台总数 {record.comments.platform_total}; "
            f"顶层 {cov['top_level_count']} (覆盖率 {cov['top_level_coverage']}), "
            f"回复 {cov['reply_count']}, 作者回复 {cov['author_reply_count']}; "
            f"多次运行按comment_id去重合并")
        record.author_engagement = compute_author_engagement(records)
        write_json(record.to_dict(), record_path)

    # 视频文件与字幕转写解耦: with_video=None 时沿用旧行为(跟随 with_subtitle)
    if with_video is None:
        with_video = with_subtitle
    if with_video or with_subtitle:
        mp4 = out_dir / "video.mp4"
        if not (mp4.exists() and mp4.stat().st_size > 1_000_000):
            aweme = adapter.fetch_video(item_id)
            if not adapter.download_video(item_id, aweme, mp4):
                raise RuntimeError("视频下载失败")
        record.media.video_file = str(mp4)
        record.media.size_bytes = mp4.stat().st_size
        write_json(record.to_dict(), record_path)

    if with_subtitle:
        mp4 = out_dir / "video.mp4"
        # 策略3: 两遍自适应 (VAD 误杀自动降阈值)
        ad = asr.transcribe_adaptive(
            mp4,
            model_name=model or (cfg["asr"] or {}).get("model", "medium"),
            device=device or (cfg["asr"] or {}).get("device", "cpu"),
            local_model=resolve_path(cfg["asr"], "local_model", base)
            if (cfg["asr"] or {}).get("local_model") else None,
        )
        segs = ad["segments"]
        paths = asr.write_subtitles(segs, out_dir, "subtitles")
        record.subtitles = SubtitlesInfo(
            model=model or (cfg["asr"] or {}).get("model"),
            segments_count=len(segs),
            full_text="\n".join(f"[{s['start']:07.2f} -> {s['end']:07.2f}] {s['text']}" for s in segs),
            segments_file=paths["json"],
            asr_note=ad["note"],
        )
        # 派生: LLM 修正版 (默认开; 有 deepseek key 才执行)
        if (cfg.get("deepseek") or {}).get("api_key"):
            try:
                from . import correct as _correct
                cctx = {"caption": record.caption, "hashtags": record.hashtags,
                        "author": (record.author.nickname if record.author else None),
                        "publish_time": record.publish_time}
                cres = _correct.correct_segments(segs, cctx, cfg)
                llm_paths = asr.write_subtitles(cres["segments"], out_dir, "subtitles.llm")
                record.subtitles.source = "whisper+llm"
                record.subtitles.corrected_file = llm_paths["json"]
                record.subtitles.corrected_note = cres["note"]
                print(f">> 字幕修正版已保存: {llm_paths['srt']}")
            except Exception as e:
                print(f">> 字幕 LLM 修正跳过: {str(e)[:100]}")
        write_json(record.to_dict(), record_path)
        print(f">> 字幕已保存: {paths['srt']} ({ad['note']})")

    print(">> 完成:", record.platform_item_id,
          f"| 文案: {(record.caption or '')[:30]}"
          f"| 评论: {record.comments.collected_count}/{record.comments.platform_total}"
          f"| 字幕段: {record.subtitles.segments_count}")
    return {"item_id": item_id, "status": "done"}


def batch_run(cfg: dict, base: Path, urls_path: str | Path, opts) -> dict:
    """无人值守批量: 队列/续跑/受阻/通知"""
    profile = resolve_path(cfg, "profile_dir", base)
    output = resolve_path(cfg, "output_dir", base)
    q = TaskQueue(output / ".queue.jsonl")
    if opts.reset:
        q.reset()
    else:
        # 受阻项重新入队(重试上限内), 实现"修复后重跑自动补抓"
        requeued = q.retry_blocked(max_retries=3)
        if requeued:
            print(f">> 受阻项重新入队 {requeued} 条")
    added = q.add(Path(urls_path).read_text(encoding="utf-8").splitlines())
    print(f">> 新增 {added} 条, 队列: {q.summary()}")

    if opts.dry_run:
        return {"dry_run": True, "summary": q.summary()}

    notifier = make_notifier(cfg) if not opts.no_notify else None
    risk = RiskController(cfg["pacing"], cfg["safety"])
    adapter = DouyinAdapter(profile, risk)
    processed = 0
    while (item := q.next_pending()):
        if risk.daily_limit_hit():
            print(">> 达到单日限额, 停止")
            if notifier:
                notifier.send("smfetch: 单日限额", f"已达上限 {cfg['safety']['max_per_day']} 条, 批次暂停")
            break
        try:
            print(f">> 处理: {item.target}")
            fetch_one(cfg, base, item.target,
                      with_comments=opts.comments,
                      with_subtitle=opts.subtitle,
                      model=opts.model, device=opts.device,
                      force=getattr(opts, "force", False))
            q.mark_done(item.target)
            risk.record_request()
        except SessionExpired as e:
            q.mark_blocked(item.target, f"登录过期: {e}")
            if notifier:
                notifier.send("smfetch: 登录过期", f"{item.target}\n请重新扫码后重跑: smfetch login")
            print(">> 登录过期, 已标记受阻。请运行 smfetch login 后重跑")
            break                      # 全局问题, 停批次
        except Exception as e:
            q.mark_blocked(item.target, str(e)[:200])
            print(f">> 失败: {item.target} -> {str(e)[:100]}")
            if notifier:
                notifier.send("smfetch: 单条受阻", f"{item.target}\n{str(e)[:100]}")
            if opts.pause:
                break                  # 用户要求暂停
        processed += 1

    blocked = q.blocked_list()
    if blocked:
        print(">> 受阻清单:")
        for b in blocked:
            print(f"   {b.target} | {b.error}")
    if notifier:
        notifier.send("smfetch: 批次结束",
                      f"队列: {q.summary()}\n受阻 {len(blocked)} 条")
    return {"summary": q.summary()}


def export_all(cfg: dict, base: Path, fmt: str = "csv", scope: str = "all") -> None:
    """把 data/ 下所有视频数据导出汇总"""
    output = resolve_path(cfg, "output_dir", base)
    videos_dir = output / "douyin"
    records, comments_all = [], []
    for d in sorted(videos_dir.glob("*")):
        vp = d / "video.json"
        if vp.exists():
            records.append(_load_json(vp))
        cp = d / "comments.json"
        if cp.exists():
            comments_all.extend(_load_json(cp))
    if fmt == "csv":
        if scope in ("videos", "all"):
            video_summary_csv(records, output / "export_videos.csv")
            print(f">> videos: {output / 'export_videos.csv'} ({len(records)} 条)")
        if scope in ("comments", "all"):
            comments_to_csv(comments_all, output / "export_comments.csv")
            print(f">> comments: {output / 'export_comments.csv'} ({len(comments_all)} 条)")
    else:
        write_json({"videos": records, "comments": comments_all}, output / "export_all.json")
        print(f">> json: {output / 'export_all.json'}")


def _load_json(path: Path) -> dict | list:
    import json
    return json.loads(path.read_text(encoding="utf-8"))
