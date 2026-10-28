# 工具3: 数据分析 — 设计文档

> 状态: **v0.1 已实现**(指标库+统计引擎+四态判定+变量表/诚实报告) | 日期: 2026-08-29
> 来源: thinking.md | 定位一句话: **把原始/派生数据加工成"研究可用的变量", 并诚实报告做不了的部分。**

## 0.1 实现状态 (2026-08-29)

```
tool3-analyze/
├── DESIGN.md            ← 本文档
├── metrics.yaml         ← 指标库(95 指标: 94 已实现 + 1 未实现/不可得; v0.2 起)
├── request.example.yaml ← 需求模板
├── smanalyze/           ← 包
│   ├── cli.py           ← metrics | plan | run
│   ├── registry.py      ← 指标库加载/查询/别名解析
│   ├── stats.py         ← 统计引擎(视频层/评论层)
│   ├── verdict.py       ← 四态判定
│   ├── report.py        ← 诚实报告
│   ├── export.py        ← CSV(utf-8-sig)/JSON 输出
│   └── parser.py        ← request.yaml 解析
├── tests/               ← 21 单测(纯逻辑, 无网络) ✅
└── output/              ← 产物(variables_video.csv / variables_comment.csv / variables.json / report.md)
```

实测: 23 视频 → 46 列视频层变量 + 22162 行评论层变量 + 诚实报告。

| 里程碑 | 状态 |
|---|---|
| v0.1 指标库+统计引擎+四态判定+变量表 | ✅ 完成 |
| v0.2 标注引擎(LLM)+缓存+抽检 | ✅ 完成(2026-08-29) |
| ~~v0.3 自由文本需求(LLM 解析→YAML)~~ | ❌ **取消**(见下) |

### v0.3 取消决策 (2026-08-29)

**背景**: 使用场景为"用户 → agent → CLI/skill", 即 agent 是唯一的调用者。

**结论**: 工具不需要内置"自然语言→YAML"能力。理由:
1. **agent 本身就是 LLM**: 让工具再解析一次自然语言 = 同一能力做两遍
2. **工具应保持确定性**: CLI 内置 LLM 会引入不可控层(解析漂移/失败), 出问题时难以区分是 agent 写错 YAML 还是工具解析出错
3. **链路已闭环**: `smanalyze metrics`(能力清单)+ `smanalyze plan`(四态自检)已足够让 agent 正确写 YAML 并自检

**替代方案**: 提供 `SKILL.md`(给 agent 的使用说明书), 而非内置 LLM 解析。

### v0.2 实现细节 (标注引擎)

```
tasks/*.yaml              ← 任务定义(标签体系/提示词/输入字段, 外部可配置)
smanalyze/
├── llm.py                ← DeepSeek 客户端(urllib, JSON 强制, 重试)
├── cache.py              ← JSONL 缓存: key=hash(text+task+prompt_ver+model)
├── tasks.py              ← 任务定义加载/校验/提示词版本指纹
└── label.py              ← 流水线: 抽样→分批→缓存→并发→解析校验→落盘→抽检
config.yaml               ← deepseek + label(batch_size/workers/retries/fail_rate_stop)
```

**已实现的关键设计**:
- **抽样策略显式**: `all`(默认) / `random_n`(固定种子可复现) / `top_likes_n`
- **并发**: `max_workers`(默认 5) + 单批重试(退避) + **失败率熔断**(>20% 停止)
- **缓存**: 命中即跳过调用;换模型或改任务定义(prompt_ver 指纹变化)→ 自动失效重标
- **校验**: index 一一对应 + 标签合法性;非法/缺失记 `null` 并保留 `error`
- **落盘分离**: `labels_<task>.csv`(可追溯: model/prompt_version/cached/ts) + `labels_sample_<task>.md`(抽检)
- **dry-run**: 只估算调用次数与 token, 不调用 API

**实测**(2026-08-29): 22162 条评论全量标注 → 2217 次调用(并发5); 23 视频 → 3 次; 缓存重跑命中率 100%。

---

## 0. 定位与边界 (最高优先级)

### 做什么 (数据加工层)
- 消费工具1 的产出(`tool1-collect/data/douyin/<id>/`), 按需求加工成**分析层变量**
- 两类能力: **统计引擎**(客观计算) + **标注引擎**(语义判断)
- 输出: **变量表** + **诚实报告**(四态判定)
- 通用: 不绑定任何具体研究框架

### 不做什么 (研究实现层)
- 回归 / 双向固定效应 / PSM / DID / Event Study / 稳健性检验 / 内生性处理
  → 属于"另一个工程"(研究端)
- 不产出研究结论, 不下因果判断, 不做理论解释

### 与 AGENTS.md 的一致性
AGENTS.md: "分析类请求只做**为研究准备数据**的部分(补字段、补覆盖率、导出、生成标准派生数据), 不实现研究逻辑本身"。
本工具正是"为研究准备数据"的通用实现: 把数据整理成研究可直接使用的变量表, 研究逻辑留在研究端。

### 通用性约束
- 标注任务的**标签体系外部可配置**(如"意愿分级"的 0-4 定义写在配置里, 不硬编码 ETI)
- 指标以**通用名称**登记(如 `text_first_person_ratio`), 不出现 OTAHI/ETI 等研究专名
- idea.md 仅作为"能力需求来源", 不是实现目标

---

## 1. 数据来源 (工具1 实际产出, 2026-08-29 盘点)

| 来源文件 | 可用字段 |
|---|---|
| `video.json` | `caption` `hashtags[]` `publish_time` `author{id,nickname,certification,signature,follower_count,total_favorited,favoriting_count}` `stats{likes,comments,shares,collects,recommends}` `media.duration_seconds` `subtitles{full_text,segments_count,source,asr_note,corrected_file}` `comments{collected_count,platform_total,top_level_count,reply_count,author_reply_count,top_level_coverage}` `author_engagement{total_author_replies,replied_comment_count}` |
| `comments.json` | `comment_id` `parent_id` `user_id` `user_nickname` **`is_author`** `text` `likes` `reply_count` `created_at` **`ip_label`** `is_hot` `author_replied` `author_reply_ids` `author_reply_count` |
| `subtitles.llm.json` | 修正版字幕段(派生) |
| `visual.json` / `scene.json` | 视觉派生(出镜/人脸/自拍/运动/场景专业度) — **需另跑, 当前多数视频未生成** |
| `keyframes/` | 关键帧图(供人工/VLM 核验) |

> 原则: **指标必须能追溯到上述字段**; 追溯不到的进"做不了/需补采"区, 不硬凑。

---

## 2. 核心机制: 四态判定流程

工具3 对**每一条需求项**给出明确状态。这是"诚实性"的实现机制。

| 状态 | 含义 | 动作 |
|---|---|---|
| ✅ **可做** | 指标库有实现 + 依赖字段存在 + 数据齐全 | 输出值 + 可信度三件套 |
| ⚠️ **部分可做** | 能算, 但数据不完整/方法有局限 | 输出值, **必须附限制条件** |
| 🔶 **需补采** | 指标可实现, 但缺原始数据 | 不输出值, 给补采建议(反馈工具1) |
| ❌ **做不了** | 数据本质不可得或方法不存在 | 说明原因 + 替代路径 |

```
需求项
  ↓ 查指标库
  ├─ 有 ─→ 检查依赖字段是否存在
  │          ├─ 存在 ─→ 检查数据完整性/抽样代表性
  │          │            ├─ 充分 ─→ ✅ 可做
  │          │            └─ 不足 ─→ ⚠️ 部分可做(附限制)
  │          └─ 缺失 ─→ 🔶 需补采
  └─ 无 ─→ 检查数据是否可得
             ├─ 可得 ─→ 🔶 需补采
             └─ 不可得 ─→ ❌ 做不了
```

### 实例 (idea.md 元素判定)

| 需求项 | 判定 | 说明 |
|---|---|---|
| 官方回复率 | ✅ 可做 | `is_author` + `parent_id` 直接算 |
| 回复速度 | ✅ 可做 | `created_at` 差值 |
| ETI 意愿分级 | ⚠️ 部分可做 | 能标, 但仅覆盖采到的评论(如 2010/12068=16.7%), 且抽样策略影响分布 |
| 视频类别 | ⚠️ 部分可做 | 能标, 但 LLM 判断有波动, 需抽检 |
| 作品数 | 🔶 需补采 | 详情接口不返回, 需抓作者主页 |
| 播放量 | ❌ 做不了 | 抖音网页接口不返回; v2 移动端/数据平台 |
| 距离目的地 | ❌ 做不了 | 无用户真实位置; `ip_label` 仅弱近似 |
| 方言精确识别 | ❌ 做不了 | 无方言模型(§17 备选未实施) |
| 工作人员出镜 | ❌ 做不了 | 工具1 v0c 暂停(待 VLM/人工决策) |

### 可信度三件套 (每个输出值必须带)
1. **数据覆盖率**: 如评论 16.7%、顶层覆盖率 0.1378
2. **方法/模型**: 如 `stat:rate` / `llm:deepseek-chat+prompt_v1`
3. **不确定性**: 如"抽样为高赞前15条, 分布不具代表性"

> 教训(2026-08-29 实测): 统计指标看起来"精确"(回复率 0.1%), 但若评论漏采, 数字会失真。**没有覆盖率的数字是假精确。**
> 教训2(分布指标用分位): 回复速度均值 122.6 分钟 vs 中位 11.3 分钟 —— 长尾数据用均值会严重失真。**所有长尾指标(速度/长度/时间间隔)一律输出 p25/p50/p75/p90, 不给均值。**

---

## 3. 指标库规范 (Metric Registry)

指标库是工具3 的**能力边界唯一真相来源**。每个指标登记:

```yaml
- metric_id: reply_rate                 # 唯一标识(英文蛇形)
  name: 官方回复率                      # 中文名
  level: video                         # video | comment
  engine: stat                         # stat | llm | derived
  inputs: [comments.is_author, comments.parent_id]
  method: "被作者回复过的顶层评论数 / 顶层评论总数"
  v0: true                             # v0 是否实现
  reliability: "依赖评论采集覆盖率; 覆盖率低时可能低估"
  notes: ""
```

**字段说明**:
- `level`: 视频级(每视频一行) vs 评论级(每评论一行)
- `engine`: `stat`(纯计算) / `llm`(标注) / `derived`(工具1 已有派生, 仅汇总)
- `v0`: v0 范围标记
- `reliability`: 可信度规则(输出诚实报告时引用)

---

## 4. 统计引擎 — v0 指标清单 (全部实现)

### 4.1 视频层 (每视频一行)

| metric_id | 名称 | 来源 | 备注 |
|---|---|---|---|
| `duration_sec` | 视频时长 | media.duration_seconds | |
| `publish_hour` / `publish_weekday` | 发布时段/星期 | publish_time | |
| `is_holiday` | 是否节假日 | publish_time + 内置日历 | 需内置中国节假日表 |
| `likes` / `comments_n` / `shares` / `collects` / `recommends` | 互动数 | stats.* | |
| `engage_ratio` | 互动率(赞评藏转比) | stats.* | 派生 |
| `caption_len` | 文案字数 | caption | |
| `hashtag_count` | 话题标签数 | hashtags | |
| `mention_count` | @提及数 | caption 正则 | |
| `caption_emoji_count` | 文案 emoji 数 | caption 正则 | |
| `caption_question_count` | 文案问句数 | caption 正则 | |
| `follower_count` / `total_favorited` | 粉丝数/获赞总数 | author.* | |
| `is_verified` / `cert_text` | 是否认证/认证类型 | author.certification | |
| `signature_len` | 签名长度 | author.signature | |
| `comment_coverage` | 评论采集覆盖率 | comments.top_level_coverage | **可信度关键** |
| `author_reply_n` | 官方回复数 | comments.author_reply_count | |
| `reply_rate` | 官方回复率 | is_author + parent_id | 核心 |
| `reply_speed_p25/p50/p75/p90_min` | 回复速度分位 | created_at 差值 | 核心, 单位分钟; **用分位而非均值**(长尾分布, 均值被极端值拉高) |
| `reply_text_len_avg` / `_median` | 官方回复字数 | is_author.text | |
| `reply_emoji_rate` | 回复含 emoji 率 | is_author.text | |
| `reply_at_rate` | 回复含 @ 率 | is_author.text | 直接互动 |
| `author_engaged_comments` | 被官方回复过的评论数 | author_engagement | |
| `comment_text_len_avg` / `_median` | 评论字数 | comments.text | |
| `comment_emoji_rate` / `_question_rate` / `_at_rate` | 评论特征率 | comments.text | |
| `top_reply_ratio` | 顶层/回复比 | parent_id | |
| `hot_comment_ratio` | 热评占比 | is_hot | |
| `ip_region_dist` / `ip_region_entropy` | IP 归属地分布/多样性 | ip_label | 可弱近似"客源地" |
| `comment_velocity_24h` | 发布后24h评论占比 | created_at - publish_time | 传播节奏 |
| `subtitle_len` / `subtitle_segments` | 字幕字数/段数 | subtitles | |

### 4.2 评论层 (每评论一行)
`char_len` `has_emoji` `has_at` `is_question` `likes` `is_hot` `level(顶层|回复)` `ip_label` `hours_since_publish` `is_author_reply` `author_replied`

---

## 5. 标注引擎

### 5.1 标签体系外部可配置
标注任务的**定义与标签体系写在配置文件**里, 不硬编码:

```yaml
# tasks/eti_level.yaml (示例: 意愿分级)
task_id: willingness_level
level: comment
input_field: text
labels:
  0: 无意愿
  1: 兴趣
  2: 明确意愿
  3: 行动意愿
  4: 计划性意愿
prompt_hint: |
  "去过了确实漂亮" = 0(非未来意愿); 纯表情/无意义 = 0
output_schema: {level: int, why: str}
```

### 5.2 关键设计
| 项 | 设计 |
|---|---|
| **抽样策略显式** | 必须指定 `sample: all \| random_n \| top_likes_n`。**默认 all**; 若抽样必须写入诚实报告 |
| **缓存** | 按 `(text_hash, task_id, prompt_version, model)` 缓存, 避免重复调用 |
| **抽检** | 随机抽 N 条(默认 20)输出人工可复核样本; 可选二次标注算一致性 |
| **成本预估** | 执行前打印预计调用次数与 token 量, 需确认(或 `--yes`) |
| **版本记录** | 输出记录 `model` + `prompt_version` + `task_id`, 保证可追溯 |
| **失败降级** | 单条失败不中断, 记 `null` + 原因; 失败率超阈值则停并报告 |

### 5.3 v0 标注任务 (建议 2 个, 验证流水线)
1. `video_category` — 视频类别(枚举可配置)
2. `willingness_level` — 意愿分级(标签可配置, 即 idea.md 的 ETI 形态)

> 教训: 用"点赞最高的 15 条"抽样标注, 得到 L0:14/L1:1 —— **高赞评论偏向吐槽玩梗**, 不代表全体。抽样偏差必须在输出中显式声明。

---

## 6. 输出设计

### 6.1 变量表 (主输出)
```
output/
├── variables_video.csv      每视频一行, 每列一个指标 (+ 标注列 JOIN)
├── variables_comment.csv    每评论一行 (+ 标注列 JOIN)
├── variables.json           同上(JSON, 保留类型)
├── labels_<task>.csv        标注结果(可追溯: model/prompt_ver/cached/why)
├── labels_sample_<task>.md  抽检样本(人工复核)
└── report.md                诚实报告
```

**JOIN 机制**(2026-08-29 实现): `run` 自动读取同目录下 `labels_*.csv`, 按 id 把标注列合并进变量表
(如 `variables_comment.csv` 末尾追加 `willingness_level`), 使研究端拿到"统计+标注"一张表;
`ok=false` 的标注不参与 JOIN。

### 6.2 诚实报告 (report.md)
```markdown
# 分析报告 — <需求摘要>
- 执行时间 / 数据目录 / 视频数 / 评论数

## ✅ 可做 (N 项)
| 指标 | 值 | 覆盖率 | 方法 |

## ⚠️ 部分可做 (N 项)
| 指标 | 值 | **限制** |

## 🔶 需补采 (N 项)
| 指标 | 缺什么 | 建议动作 |

## ❌ 做不了 (N 项)
| 需求 | 原因 | 替代路径 |

## 数据可信度总览
- 评论覆盖率: 中位 X%, 最低 Y%
- 标注任务: 模型/提示词版本, 抽检样本
```

---

## 7. 输入设计 (两种形态都支持)

### 7.1 YAML (结构化, 可复现)
```yaml
data_dir: ../tool1-collect/data/douyin
metrics:
  - reply_rate
  - reply_speed_median
  - comment_text_len_avg
tasks:                        # 标注任务
  - video_category
  - willingness_level
sample: all                   # 抽样策略(显式)
output_dir: ./output
```

### 7.2 自由文本需求 —— 已取消(见 §10 v0.3 取消决策)
> 使用场景为 agent 驱动 CLI, agent 可直接生成 YAML, 无需工具内置 LLM 解析。
> 工具提供 `metrics`(能力清单)+ `plan`(四态自检)+ `SKILL.md`(使用说明)即可让 agent 正确使用。

---

## 8. CLI 规范 (已实现)

```
python -m smanalyze metrics [--json]        # 列出指标库(能力边界)
python -m smanalyze plan <request.yaml>     # 四态判定预览(不计算)
python -m smanalyze run <request.yaml>      # 执行统计引擎 → 变量表+报告
```

> v0.3 将增加 `run --text "..."`(自由文本 → LLM 解析 → YAML → 确认)。

命名: `smanalyze`(与 smfetch/smsearch 同族)。

**依赖**: 统计引擎零新依赖(标准库); 标注引擎用 urllib 调 DeepSeek(与工具1 `correct.py`、工具2 `llm.py` 一致, 不引入新库)。

---

## 9. 与工具1/2 的关系

```
工具2 smsearch ──URL清单──► 工具1 smfetch ──原始+派生数据──► 工具3 smanalyze ──变量表──► 研究工程
                                  ▲                                    │
                                  └──── 缺字段反馈(🔶需补采) ◄──────────┘
```

- 工具3 **只读**工具1 数据, 不修改
- 发现缺字段 → 输出"需补采"清单, 供人工决定是否回工具1 补采(闭环)

---

## 10. v0 范围与里程碑

| 阶段 | 内容 | 状态 |
|---|---|---|
| **v0.1** | 指标库框架 + 统计引擎(§4 全部) + 四态判定 + 变量表/诚实报告 + YAML 输入 | ✅ 已完成(21 测试) |
| **v0.2** | 标注引擎(2 个任务) + 缓存 + 抽检 + 成本预估 | ⏳ |
| **v0.3** | 自由文本需求(LLM 解析 → YAML → 确认) | ⏳ |
| **v1** | 更多指标/任务(按研究端反馈扩展) | ⏳ |

---

## 11. 开放问题

1. 节假日日历的数据源与更新方式(内置表 vs 外部文件)
2. `ip_label` → 地区/距离的近似规则(是否提供"客源地"弱代理变量, 需明确标注不可靠)
3. 标注一致性验证: 是否需要"双模型/双提示词交叉"机制
4. 视频级 vs 评论级变量的连接键(comment 表是否带 video_id 列以便合并)
5. 与 SKILL 的关系: 独立 CLI 还是 skill 的一部分(与工具1/2 保持一致即可)

---

## 12. 决策记录

| 决策 | 结论 |
|---|---|
| 定位 | 数据加工层(变量生成), **不做研究逻辑**(2026-08-29 用户确认) |
| 能力划分 | 统计引擎(可枚举, 零成本) + 标注引擎(LLM 语义) |
| 判定机制 | **四态**: 可做/部分可做/需补采/做不了 |
| 指标库 | 能力边界唯一真相来源; 每指标带 inputs/method/reliability |
| 通用性 | 标签体系外部可配置, 指标通用命名, 不绑研究框架 |
| 诚实性 | 每个值带"覆盖率+方法+不确定性"; 抽样策略必须显式 |
| 输入 | YAML(可复现) + 自由文本(LLM 解析后确认) 双形态 |
| 依赖 | 统计零新依赖; 标注用 urllib + DeepSeek(不引新库) |
