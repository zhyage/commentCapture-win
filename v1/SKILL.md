---
name: douyin-research-pipeline
description: "抖音研究数据流水线编排。当用户提供研究文档(研究设计/变量清单/论文提纲)需要采集并加工抖音数据时使用: 澄清需求 → 工具2搜索取URL → 工具1采集原始数据 → 工具3加工成研究变量。触发词: 抖音数据采集/研究数据/活人感/旅游意愿/评论分析/官方账号数据/OTAHI/ETI。"
---

# 抖音研究数据流水线 — 编排说明

## 用途

用户在**任何项目**里提出"需要抖音数据做研究"时,按本说明驱动三个独立工具:

```
用户的研究文档(如 idea.md 形态)
   ↓ ① 澄清(分批向用户提问)
   ↓ ② 规划(账号/范围/变量/标注任务)
   ↓ ③ 执行
      工具2 smsearch  → urls.txt(视频URL清单)
      工具1 smfetch   → data/douyin/<id>/ (详情/评论/视频/字幕)
      工具3 smanalyze → variables_*.csv + labels_*.csv + 诚实报告
   ↓ ④ 交付(变量表 + 诚实报告)
```

**本工程不做研究分析**(回归/PSM/DID 属研究端)。只负责把数据采全、加工成研究可用变量。

## 输入形态速查(用户想要什么 → 用哪个模式)

| 用户想要 | 入口 | 说明 |
|---|---|---|
| **某账号的全部作品** | 工具2 **抖音号模式**(`douyin_id: [55008743593]`) | 定位主页 → **全量翻页该号所有作品**(不排序、一条不落) → 过滤 |
| 按关键词找视频 | 工具2 **关键词模式**(`keywords: [...]`) | 平台搜索 + 按点赞排序, 只翻有限页(非穷举) |
| 已有 URL/ID 清单 | 直接**工具1** `smfetch batch urls.txt` | 跳过工具2 |
| 只做分析 | 直接**工具3**(数据已在 `data/douyin/`) | 跳过工具1/2 |

> ⚠️ 关键词模式**不是穷举**(平台搜索结果有限); 要"某账号全集"必须用抖音号模式。

## 环境(硬编码路径, 勿猜)

| 项 | 值 |
|---|---|
| 工程根 | `D:\zhy\抖音` |
| 解释器 | `D:\zhy\抖音\.venv\Scripts\python.exe` |
| 工具1 采集 | `D:\zhy\抖音\v1\tool1-collect`(smfetch) |
| 工具2 搜索 | `D:\zhy\抖音\v1\tool2-search`(smsearch) |
| 工具3 加工 | `D:\zhy\抖音\v1\tool3-analyze`(smanalyze) |
| 数据目录 | `D:\zhy\抖音\v1\tool1-collect\data\douyin\<视频ID>\` |
| 登录态 | `D:\zhy\抖音\.profile`(小号, 勿动) |
| 常驻浏览器 | CDP 端口 9222 |

**每次调用前必须设置的环境变量 + 解释器变量**(PowerShell 变量不跨进程: **每开一个新 shell 都要重跑这三行**):
```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='D:\zhy\抖音\.cache\ms-playwright'
$env:TMP='D:\zhy\抖音\.cache\tmp'; $env:TEMP='D:\zhy\抖音\.cache\tmp'
$py = 'D:\zhy\抖音\.venv\Scripts\python.exe'      # 下文命令统一用 $py
```

**其他前置条件**:
| 项 | 位置/说明 |
|---|---|
| LLM API key(语义判定/标注) | 工具2 `config.yaml` 与 工具3 `config.yaml` 的 `deepseek.api_key`(已配置) |
| 视觉管线解释器 | `%LOCALAPPDATA%\smfetch\venv312\Scripts\python.exe`(py3.12 ASCII 路径, 原生库要求) |
| 字幕模型(离线) | `D:\zhy\抖音\.cache\hf-local\faster-whisper-medium` |
| 单日采集限额 | 工具1 `config.yaml` → `safety.max_per_day`(默认 200) |

### 细节去哪找(本 skill 只讲编排; 工具细节在各工具 skill)

| 想知道 | 读(绝对路径) |
|---|---|
| smfetch 命令/参数/坑 | `D:\zhy\抖音\v1\tool1-collect\SKILL.md` |
| smsearch 命令/请求字段/坑 | `D:\zhy\抖音\v1\tool2-search\SKILL.md` |
| smanalyze 命令/95 个指标/标注规范/坑 | `D:\zhy\抖音\v1\tool3-analyze\SKILL.md` |
| 指标库(能力边界唯一真相) | `D:\zhy\抖音\v1\tool3-analyze\metrics.yaml`, 或跑 `smanalyze metrics` |
| 请求模板(字段含义) | `D:\zhy\抖音\v1\tool2-search\request.example.yaml`(搜索)<br>`D:\zhy\抖音\v1\tool3-analyze\request.example.yaml`(分析) |
| 数据 schema/字段含义 | `D:\zhy\抖音\v1\tool1-collect\DESIGN.md`(§6) |
| 各工具设计决策 | 各目录 `DESIGN.md` |
| 工程整体状态/待办 | `D:\zhy\抖音\PROJECT_STATUS.md` |

> 注意: 工具2 和工具3 **各自有** `request.example.yaml`(同名不同目录); 执行前先 `cd` 到对应工具目录。
> **写请求文件前必须先跑 `smanalyze metrics`**(否则不知道指标是否存在)。

## ① 澄清阶段(分批问, 不要一次抛 10 个问题)

研究文档通常抽象(如"活人感"),**不要替用户假设定义**,分三批澄清:

### 第 1 批 · 采集范围(先问这个)
- 目标账号:具体抖音号/昵称?(如 `55008743593` 红河文旅)—— 工具2 的输入
- 或搜索关键词:?(如"红河文旅""云南文旅")
- 时间范围、视频数量上限、点赞门槛?
- 是否需要评论?评论采集上限?(默认安全模式:单条最多 2000 条)

### 第 2 批 · 需要哪些变量
先跑 `smanalyze metrics` 拿到能力清单,再逐项对照研究文档:
- 文档里的每个概念 → 映射到具体指标(或告知做不了)
- 对**做不了/需补采**的项,当场告知用户(见下方"能力边界")

### 第 3 批 · 标注任务(如需要)
- 需要 LLM 标注什么?(如评论意愿分级、视频分类)
- **标签体系必须由用户确认**:等级/类别定义、边界案例怎么判
- 提醒:标签体系改动会使缓存失效并重标(有 API 成本)

## ② 规划阶段

产出给用户确认的执行计划:
```
[采集] 账号=红河文旅(55008743593) | 全部作品 或 按点赞取前 N
[采集] 是否含评论/字幕/视频文件
[加工] 统计指标清单 + 标注任务清单
[诚实] 做不了: 播放量/距离/方言/工作人员出镜(提前告知)
[输出] 目录位置
```

## ③ 执行阶段(标准命令)

```powershell
# 0) 起常驻浏览器(工具1/2 都需要)
cd D:\zhy\抖音\v1\tool2-search
& $py -m smsearch browser start

# 1) 工具2: 搜索 → URL 清单
#    先: Copy-Item request.example.yaml request.yaml, 按澄清结果编辑
& $py -m smsearch request.yaml

# 2) 工具1: 按清单采集(断点续跑, 已采跳过)
cd D:\zhy\抖音\v1\tool1-collect
& $py -m smfetch batch urls.txt

# 3) 工具3: 加工
cd D:\zhy\抖音\v1\tool3-analyze
& $py -m smanalyze metrics               # 先看能力清单(写需求前必做)
& $py -m smanalyze plan request.yaml     # 四态判定预览(不计算)
& $py -m smanalyze run request.yaml      # 统计引擎 → 变量表
& $py -m smanalyze label request.yaml --dry-run   # 标注成本估算(先跑这个)
& $py -m smanalyze label request.yaml    # 标注(有 API 成本)
```

**"四态判定"是什么**: `smanalyze plan` 对每条需求给出的四种状态 ——
`✅ 可做` / `⚠️ 部分可做`(数据不全, 值会失真) / `🔶 需补采`(指标可行但缺数据) / `❌ 做不了`(数据本质不可得)。
**执行前先跑 plan 并把结果给用户看**, 这是"提前告知做不了"的机制。

**顺序原则**:2 → 1 → 3;但每个工具都能独立使用(用户可能已有一批 URL, 或只想跑分析)。

**request 文件位置**:工具2 与工具3 **各自有** `request.example.yaml`(同名不同目录)——
第 1 步在 `tool2-search/` 下(搜索条件), 第 3 步在 `tool3-analyze/` 下(分析需求);
工具1 不需要 request 文件(只吃 `urls.txt`)。

**配额与工期**:工具1 默认单日采集限额 200 条(`config.yaml` 的 `safety.max_per_day`)。
账号数 × 每号作品数 ÷ 200 ≈ 所需天数。大规模采集前先算给用户看。

**合规提醒**:评论含用户昵称/IP/ID 等个人信息, 研究使用需**去标识化**; 只采公开数据。

## ④ 交付与诚实边界

交付物:
- `variables_video.csv`(每视频一行)+ `variables_comment.csv`(每评论一行, 含标注列)
- `labels_*.csv`(标注结果, 含模型/提示词版本, 可追溯)
- `report.md`(诚实报告: 覆盖率、方法、做不了的部分)

**必须主动告知用户的边界**(不要等用户发现):

| 需求类型 | 状态 | 说明 |
|---|---|---|
| 播放量 | ❌ 做不了 | 抖音网页接口不返回; 需 v2 移动端/数据平台 |
| 距离目的地 | ❌ 做不了 | 无用户真实位置; `ip_label` 仅弱近似(可降级为"是否本省") |
| 方言识别 | ❌ 做不了 | 无方言模型 |
| **工作人员出镜 / 非专业场景** | ❌ 做不了 | 工具1 v0c **判断逻辑**暂停(待 VLM/人工决策) |
| **真人出镜比例 / 人脸数 / 自拍手持 / 镜头运动** | 🔶 **需先跑工具1 视觉管线** | 工具1 `visual.py`/`keyframes.py` **已实现**, 但需在 py3.12 venv 单独跑(`tools/run_visual.py`); 当前已采数据多数**未生成** `visual.json`。用前先确认/补跑 |
| 作品数/音乐/分辨率 | 🔶 需补采 | 工具1 可补字段 |
| 是否节假日 | 🔶 需补采 | 需内置日历(含调休口径) |
| 视频质量 / 热点话题 | ⚠️ 口径未定 | 需与研究端确认操作化定义 |
| 回归/PSM/DID/稳健性 | ⛔ 不属本工程 | 研究端实现(但 DID 需"转型时点"、PSM 需匹配变量, 属数据需求) |

> **诚实原则**: 上表未覆盖的需求(如"评论区问题解决程度""景点类型"), **不要猜能不能做** —— 先跑 `smanalyze plan` 或查 `metrics.yaml` 再回答; 仍无法判断就告诉用户"待确认"。

**覆盖率警告**:评论是"安全模式采样"(单条默认上限 2000, 平台爆款常采不全)。
所有评论类指标必须带覆盖率; 覆盖率低时统计值会失真(如回复率被低估)。

## 安全红线(IRON RULES)

1. **只读**: 绝不点赞/关注/评论/转发
2. **小号隔离**: 只用小号(`.profile`), 绝不用户主号
3. **节奏不改快**: 各工具 pacing 参数是防封生命线, 未经用户同意不得调快
4. **验证码人工**: 出现登录墙/验证码 → 停下提示用户, 等用户明确告知("扫好了")才继续; **绝不自动继续、绝不关浏览器**
5. **常驻浏览器**: 只通过 `smsearch browser start|stop` 管理; 任务结束**不关**
6. **成本确认**: 标注类操作先 `--dry-run` 估算调用次数, 告知用户后再执行

## 常见坑(实测)

| 坑 | 说明 |
|---|---|
| 抖音号定位 | 卡片文本"抖音号:55008743593388.3万"数字粘连 → 工具已用前缀匹配+主页校验 |
| 搜索页版本 | 可能被重定向到 jingxuan 精选版(无用户 tab)→ 工具已内置保守+直开双路径 |
| 评论采集上限 | 网页端爆款视频天花板约 85%; 超大回复楼可能不全 |
| 字幕不完整 | 音乐/现场音视频 VAD 会误杀 → 工具已用策略3 两遍自适应; 仍可能识别错字 |
| 字幕被 LLM 修正 | `subtitles.llm.*` 是修正版(含推断); 研究端须知道; 原始 `subtitles.*` 未改 |
| 标注缓存 | key 含 model+prompt_ver; 改标签体系会失效重标(成本) |
| 抽样偏差 | 抽样策略必须显式(`all`/`random_n`/`top_likes_n`); 高赞抽样偏向吐槽 |
| 单日限额 | 工具1 默认 `max_per_day: 200` |
