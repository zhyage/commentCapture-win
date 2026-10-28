---
name: smanalyze
description: "抖音数据分析/变量加工工具。把工具1采集的原始数据加工成研究可用变量(统计指标+LLM标注), 并诚实报告做不了的部分。触发词: 分析抖音数据/计算回复率/标注意愿/生成变量表/评论标注/smanalyze。"
---

# smanalyze — 数据分析/变量加工 (工具3)

## 用途

消费工具1 的产出, 加工成**研究可用的变量表**:

- **统计引擎**: 客观计算(回复率/回复速度/评论特征/IP分布/时间特征…), 零模型、可复现
- **标注引擎**: LLM 语义标注(如评论意愿分级、视频类别), 标签体系外部可配置
- **四态判定**: 对每条需求给出 可做/部分可做/需补采/做不了 + 原因
- **诚实报告**: 每个值带覆盖率+方法+不确定性

**不做研究逻辑**(回归/PSM/DID 属研究端)。

## 环境

- 目录: `D:\zhy\抖音\v1\tool3-analyze`
- 解释器: `D:\zhy\抖音\.venv\Scripts\python.exe`
- 数据源: `../tool1-collect/data/douyin/<视频ID>/`(**只读**)
- 配置: `config.yaml`(deepseek key / 标注并发/批量/抽检)
- 不依赖浏览器

## 工作流

### 1. 看能力边界(写需求前必做)
```powershell
python -m smanalyze metrics          # 95 指标(v0.2): 哪些已实现/哪些不可得
python -m smanalyze metrics --json   # 机器可读
```

### 2. 写请求文件(参考 `request.example.yaml`)
```yaml
data_dir: ../tool1-collect/data/douyin
metrics:                    # 统计指标(可用 metric_id 或中文名)
  - reply_rate
  - reply_speed_p50_min
  - comment_coverage
tasks:                      # 标注任务(见 tasks/*.yaml)
  - willingness_level
  - video_category
sample: all                 # 抽样策略: all | random_n | top_likes_n
include_comments: true
output_dir: ./output
```

### 3. 四态判定预览(不计算)
```powershell
python -m smanalyze plan request.yaml
```
输出 ✅可做 / ⚠️部分可做 / 🔶需补采 / ❌做不了 —— **先把这个结果给用户看**。

### 4. 执行统计引擎
```powershell
python -m smanalyze run request.yaml
```
产出: `variables_video.csv`(每视频一行)+ `variables_comment.csv`(每评论一行)+ `variables.json` + `report.md`
**自动 JOIN**: 同目录已有 `labels_*.csv` 会被合并进变量表(统计+标注一张表)。

### 5. 执行 LLM 标注
```powershell
python -m smanalyze label request.yaml --dry-run   # 先估算调用次数/token
python -m smanalyze label request.yaml             # 执行
python -m smanalyze label request.yaml --tasks willingness_level --sample random_n --sample-n 20
```
产出: `labels_<task>.csv`(含 label/why/model/prompt_ver/cached)+ `labels_sample_<task>.md`(抽检样本)

## 标注任务设计规范

任务定义在 `tasks/<task_id>.yaml`(外部可配置, 换研究只换配置):

```yaml
task_id: willingness_level
level: comment            # comment | video
input_field: text
labels:                   # 标签体系: 必须互斥且穷尽
  0: 无意愿
  1: 兴趣
  ...
prompt_hint: |            # 判定要点: 写边界案例
  "去过了确实漂亮" = 0(非未来意愿)
max_input_chars: 500      # 超长截断
```

**设计要点**:
- 标签必须 **MECE**(互斥、穷尽), 不确定的放"其他"
- 边界案例写进 `prompt_hint`(这是标注质量的关键)
- **改标签体系/提示词 → prompt_version 变化 → 缓存失效 → 全量重标(有成本)**, 改前告知用户
- 多标签共存的需求 → 拆成多个独立任务(每任务单标签)

## 关键语义与陷阱

| 项 | 说明 |
|---|---|
| **覆盖率是生命线** | 评论是安全模式采样(单条默认上限 2000); 覆盖率低时回复率等会失真。每个值都要带覆盖率 |
| **长尾指标用分位** | 回复速度等输出 p25/p50/p75/p90, **不给均值**(均值被极端值拉高: 实测中位 11 分 vs 均值 122 分) |
| **抽样必须显式** | `all`(默认) / `random_n`(固定种子可复现) / `top_likes_n`(**有偏**: 高赞偏吐槽玩梗) |
| **缓存** | key = hash(text+task+prompt_ver+model); 命中即跳过调用; 保证同研究内标签一致 |
| **并发** | 默认 5 线程; 单批重试退避; 失败率 >20% 熔断停止 |
| **JOIN** | `run` 自动合并 `labels_*.csv`; `ok=false` 的标注不参与 |

## v0.2 新增能力 (2026-09-09, 为 OTAHI 三维补齐)

| 能力 | 位置 | 用法/口径 |
|---|---|---|
| **节假日日历** | `smanalyze/holiday.py` | 国务院口径 2024–2026(含调休); 指标 `is_holiday/holiday_name/is_weekend/is_makeup_workday/is_rest_day`; **未收录年份返回空, 不猜** |
| **视觉接入** | `smanalyze/stats.py` 读 `visual.json` | `visual_present_ratio/face_count_avg/face_count_max/selfie_score/shake_index/camera_motion/video_resolution`; 需先跑工具1 `tools/run_visual.py` |
| **Text Liveness 词典** | `smanalyze/lexicon.yaml` + `stats.py` | 6 维 × 双通道: `tl_cap_*`(仅文案) / `tl_all_*`(文案+字幕) + `tl_index_cap/tl_index_all`; **纯字符串可复现**; 词表 v0.2(新增词标 `# [v0.2]` 可回退), 属研究口径, 改词表需重算(零成本) |
| **文本预处理** | `stats.to_simplified()` / `stats.subtitle_text()` | ① **繁→简归一化**(依赖 `zhconv`, 未装则跳过不报错) ② 字幕取 **LLM 修正版** `subtitles.llm.json`, 缺失回退 `subtitles.json`, 再回退 `full_text`(剥离 SRT 标记); 来源记在 `subtitle_text_source` |
| **因变量派生** | `stats.py: derive_eti()` (run 自动执行) | `etir`(≥1占比) / `strong_etir`(≥3占比) / `eti_mean` / `eti_n`; 依赖 `labels_willingness_level.csv` |
| **视频层多字段输入** | `cli.py: _field_value()` | `input_field: [caption, subtitles.full_text]` 支持点号路径拼接 |

**新增 6 个标注任务**(`tasks/tl_llm_*.yaml`, 视频层二分类+理由):
`tl_llm_first_person` / `tl_llm_colloquial` / `tl_llm_emotion` / `tl_llm_slang` / `tl_llm_meme` / `tl_llm_rhetorical`
—— 与词典指标互补: 词典给"密度"(连续, 可进 PCA/因子), LLM 给"有/无+理由"(可抽检)。

> 研究需求模板见 `request.research.yaml`(idea.md 全变量映射)。

**⚠️ 构念差异(必读, 已写入 report.md)**: `tl_*_meme` 测「引用具体梗」、`tl_llm_meme` 测更宽的「幽默化」(含自嘲/吐槽);
`tl_*_slang` 与 `tl_llm_slang` 同理。**两组不是同一构念, 不可互相替代**——
按 idea.md 的 HCI3「幽默化」优先用 LLM 版, 词典版仅作稳健性对照。

## 能力边界(必须主动告知用户)

| 需求 | 状态 |
|---|---|
| 播放量 | ❌ 抖音网页接口不返回 |
| 距离目的地 | ❌ 无用户位置; `ip_label` 仅弱近似 |
| 方言识别 | ❌ 无方言模型 |
| 工作人员出镜/非专业场景 | ❌ 工具1 视觉判断暂停 |
| 作品数/音乐 | 🔶 工具1 可补采 |
| 节假日 | ✅ 已内置国务院日历 2024–2026(含调休); 未收录年份返回空 |
| 方言 | ❌ 无方言模型(已放弃该维, 不用 LLM 弱判定冒充) |
| 回归/PSM/DID | ⛔ 研究端实现 |

## 常见坑

| 坑 | 说明 |
|---|---|
| 抽样偏差 | 用高赞前 15 条标注 → L0:14/L1:1; 全量或随机才代表分布 |
| LLM 标注波动 | 低温度 + 缓存 + 抽检样本; 必要时改 prompt_hint 重标 |
| 标注失败 | 单条失败记 null 不中断; 失败率高会熔断, 看 `labels_*.csv` 的 error 列 |
| 成本 | 全量标注 22162 条评论 ≈ 2217 次调用 ≈ 1-3 元; 先 `--dry-run` |

## 测试

```powershell
python -m pytest tests    # 40 单测(纯逻辑, 不碰网络)
```
