# 抖音研究数据工程 — 项目状态总结

> 更新日期: 2026-09-09 | 阅读对象: 离项目多天后的你自己
> 配套: `idea.md`(研究目标) `thinking.md`(方案思考) `AGENTS.md`(工程规则) `v1/DESIGN.md`(三工具高层设计)

---

## 0. 项目是做什么的(一句话)

为"文旅官方账号'活人感'(OTAHI) → 表达性旅游意愿(ETI)"的抖音研究,**采集原始数据**(视频文案/评论/字幕/视频文件/作者画像),做成三个**独立可运行的工具**。本工程**不做研究分析**(那是另一个工程),只保证数据采全、采好、可追溯。安全红线:只读、小号、真人节奏。

## 1. 当前总进度

```
v1/
├── tool1-collect/  原始数据收集 smfetch      ✅ 完成 (52 测试)
├── tool2-search/   搜索/获取URL smsearch     ✅ v0 完成 (11 测试)
└── tool3-analyze/  数据分析 smanalyze        ✅ v0.1+v0.2 完成 (38 测试)
```

数据流: **工具2**(条件→URL 清单) → **工具1**(按 URL 采原始数据) → **工具3**(加工成研究变量 + 诚实报告)
三工具测试合计 **101 个全绿**。

---

## 2. 已经做了什么

### 2.1 工具1 (smfetch) — 原始数据采集

- 采集:文案+话题、作者画像、互动统计、**评论+楼中楼**(含作者回复/覆盖率)、无水印视频、**口播字幕**、视觉派生(visual/scene/keyframes)
- **字幕增强(2026-08-28)**:策略3 两遍自适应(VAD 误杀自动重跑)+ **LLM 修正版**(依据文案背景修正专名,保留原始底稿)
- 浏览器:**共享常驻浏览器**(CDP 9222,与工具2 共用小号登录态)
- 数据: `data/douyin/<视频ID>/` 四件套(video.json / comments.json / video.mp4 / subtitles.*)+ subtitles.llm.*
- 当前数据: **23 个视频目录,全部四件套完整**

### 2.2 工具2 (smsearch) — 搜索/获取 URL

- 两种模式:**关键词搜索** / **抖音号全量翻页**(按抖音号精确匹配定位)
- 两段式过滤:硬过滤(客观字段)+ DeepSeek 语义判定(describe 意图)
- 输出: results.json / urls.txt / collected 全量核对清单
- 实跑: 红河文旅 802 条→符合117; 云南红河发布 4308 条→符合57

### 2.3 工具3 (smanalyze) — 数据分析 **(本轮新增)**

**定位**:数据加工层(把原始数据变成研究变量),**不做研究逻辑**(回归/PSM/DID 属研究端)

| 能力 | 状态 |
|---|---|
| **指标库** (metrics.yaml) | **95 指标(94 已实现)** + 7 项不可得/需补采(v0.2) |
| **统计引擎** | ✅ 视频层 46 列 + 评论层 16 列,零模型纯计算 |
| **四态判定** | ✅ 可做 / 部分可做 / 需补采 / 做不了(附原因) |
| **标注引擎 v0.2** | ✅ LLM 标注(任务外部 YAML 配置)+ 缓存 + 并发 + 抽检 |
| **诚实报告** | ✅ 每个值带覆盖率+方法+不确定性 |

**本轮实跑成果**:
- 23 视频 → `variables_video.csv`(**77 列**, v0.2)+ `variables_comment.csv`(22162 行)
- **22162 条评论全量标注意愿分级**(零失败):L0 无意愿 95.4%,**表达意愿 4.6%**
- 23 视频分类标注完成
- 发现:同账号不同视频的"意愿激发率"相差 5 倍(24.1% vs 4.8%)

### 2.3.1 工具3 v0.2 补齐 (2026-09-09) **(本轮新增)**

按 `idea.md` 的 OTAHI 三维补齐缺口:

| 新增 | 内容 | 说明 |
|---|---|---|
| **视觉接入** | `visual_present_ratio` / `face_count_avg/max` / `selfie_score` / `shake_index` / `camera_motion` | 工具1 视觉管线**已补跑全部 23 条**(`tools/run_visual.py`), 出镜比例均值 59.6% |
| **节假日日历** | `is_holiday` / `holiday_name` / `is_weekend` / `is_makeup_workday` / `is_rest_day` | `smanalyze/holiday.py`, 国务院口径 2024–2026(含调休); 未收录年份返回空 |
| **Text Liveness** | 6 维 × 双通道(仅文案 / 文案+字幕)+ 等权指数 | `smanalyze/lexicon.yaml` **v0.2 词表**(v0.1 种子表按口语/情绪语言学标记扩充, 新增词标 `# [v0.2]` 可回退; **待研究者审**); 文本先**繁→简归一化**(zhconv) 再匹配; 字幕用 **LLM 修正版**(`subtitles.llm.json`, 缺失回退原始 ASR); 纯字符串可复现 |
| **因变量派生** | `etir` / `strong_etir` / `eti_mean` / `eti_n` | 由 22162 条意愿标注按视频聚合 |
| **分辨率** | `video_resolution` | 顺带关闭"未采集"缺口 |

- 新增 6 个 LLM 标注任务 `tasks/tl_llm_*.yaml`(二分类+理由, 视频层, 输入=文案+字幕)
- 测试: **74 个全绿**(原 38 + v0.2 新增 36)
- 四态判定:`可做 47 | 部分可做 8 | 需补采 1 | 做不了 3`

**诚实缺口(本轮明确不做/不可得)**:播放量、距离目的地、方言(无模型, 已放弃该维)、音乐信息;
中介变量(真实性/社会临场感)与"评论区问题解决程度"按用户决定不纳入本轮。

**构念口径提醒(已写入 `output/report.md`)**: `tl_*_meme`(词典)=引用具体梗 vs `tl_llm_meme`(LLM)=更宽的幽默化;
`tl_*_slang` vs `tl_llm_slang` 同理 → **两组非同一构念, 不可互替**; HCI3 用 LLM 版, 词典版作稳健性对照。

### 2.3.2 样本清理 + 目标账号筛选规则 (2026-09-09) **(本轮新增)**

对 23 条逐条按作者 uid + 认证主体核查, 发现样本被污染:

| 判定 | 条数 | 账号 | 依据 |
|---|---|---|---|
| `target` | **9** | 红河文旅 | 认证=红河州**文化和旅游局**官方抖音号 ✅ |
| `borderline` | **10** | 云南红河发布 | 认证=红河州**融媒体中心**官方抖音号 ⚠️ 非文旅局主体 |
| `non_target` | 4 | 木工孙(个人IP)、MrY(个人博主)、海信激光电视(企业品牌)、一城一史话(个人科普) | 无认证或企业认证, 非目的地推广主体 |

- **严格符合 idea.md"文旅官方账号"的只有 9/23 条(39%)**
- 4 条 `non_target` 里, 2 条(木工孙/一城一史话)来自早期手工测试清单 `urls.txt`; 2 条(MrY/海信)是**工具2 主页翻页混入**(来源号 55008743593)
- 工具2 混入率实测: 红河文旅 802 条里 **34 条(4.2%)** 作者 uid ≠ 本人

落地物:
- `v1/tool3-analyze/accounts.yaml` — 白名单(uid) + 认证关键词规则 + manual_overrides + **`sample_policy`(样本分层口径)**
- `smanalyze/stats.account_status()` / `sample_role()` — 判定函数; 变量表新增 8 列: `account_uid/account_status/is_target_account/account_admin_type/account_level/account_province/account_region/sample_role`(表宽 84 → **92 列**)
- `AGENTS.md` 新增「目标账号筛选规则」章节(工程级规则, 永久生效)
- `report.md` 自动输出账号判定分布 + 样本分层分布 + 过滤提醒
- 测试: **84 个全绿**

**样本分层口径(用户 2026-09-09 决定, 记在 `accounts.yaml.sample_policy`)**:

| `sample_role` | 账号判定 | 条数 | 用途 |
|---|---|---|---|
| `main` | target | **9** | **主样本**(严格符合"文旅官方账号") |
| `robustness` | borderline | **10** | **仅稳健性检验时纳入**(云南红河发布=融媒体中心) |
| `excluded` | non_target | 4 | 不进样本 |
| `undetermined` | unknown | 0 | 待人工确认 |

> 主样本过滤: `df[df.sample_role == "main"]`(当前 9 条) —— **严格样本很小, 更加说明扩采的紧迫性**。

### 2.3.3 阶段一扩采 · 账号预检 + 工具2 缺陷修复 (2026-09-11)

**预检结论: 9/9 全部 `target`**(方式: 搜索卡片读「认证徽章<主体名>」)

| 账号 | 认证主体 | 大区 |
|---|---|---|
| 贵州文旅 / 广西文化和旅游厅 / 云南省文化和旅游厅 / 四川文旅 / 陕西文旅 | 各省**文化和旅游厅**官方 | 西部 |
| 重庆文旅 | 重庆市**文化和旅游信息中心**(文旅系统事业单位) | 西部 |
| 浙江文旅 | 浙江省**文化广电和旅游厅**官方 | **东部** |
| 安徽文旅 | 安徽省**文化和旅游厅**官方 | **中部** |
| 红河文旅 | 红河州**文化和旅游局**官方 | 西部(地市) |

- 9 个号已预登记进 `accounts.yaml`(含 sec_uid/层级/省份/大区); uid 待采集后回填(已支持**昵称兜底匹配**)
- 新增列 `account_match`(uid / nickname / manual_uid / cert_keyword / cert_other), 记录判定依据便于审计

**修掉的两个 bug**:

1. **认证关键词假阴性**: 「浙江省**文化广电和**旅游厅」不含「文化和旅游厅」→ 曾误判 `non_target`。
   已改用「旅游厅/旅游局」锚点覆盖各省厅名变体(浙江/广电系)
2. **工具2 主页身份校验缺陷(严重)**: `_verify_profile_did()` 依赖主页 DOM 渲染「抖音号:」字段,
   而该字段**经常不渲染**, 加上 `goto` 后固定 `sleep(6)` **早于头部渲染** → 预检 9 个号里 5 个被判失败。
   **同一段校验在 `_crawl_user_all` 里也跑 → 采集时会静默跳过这些账号。**
   修复: **渲染等待(轮询) + 三级证据**(①抖音号文本 → ②官方认证徽章 `[data-e2e="badge-role-name"]` → ③昵称),
   且**不放宽到无条件通过**(证据不足仍拒绝, 避免采错账号)

**验证**: 工具2 测试 11 → **32 个全绿**(新增 `test_locate.py` 21 项); 真机回归: 云南/安徽(修复前失败)现均通过,
且 sec_uid 与预检(另一条独立路径)完全一致。

**地区口径(用户 2026-09-11 决定)**: 接受 7西:1中:1东 不平衡 → `account_region` **仅作控制变量, 不做地区异质性**;
记在 `accounts.yaml.sample_policy.region_policy`, 并写入 `report.md` 口径与局限。

### 2.3.4 ⚠️ 事故与修复: 2026-09-13 工具2 三段爬取全线失败

**结果**: 三段共跑 6.3 小时, **产出 0 条 URL**。2024 段(3.5h)与 2025 段(2.4h)其实**爬成功了**
(2024: 7 个号共收集 26,149 条作品、命中 4,916 条、各输出 9 条 = 63 条 URL), 但**全部丢失**。

**根因 1(致命, 我的配置引入)**: `after: 2024-01-01` 被 YAML 解析成 `datetime.date` →
`json.dumps(result)` 抛 `TypeError: Object of type date is not JSON serializable`
→ 崩在**写 results.json 这一步**(在写 urls.txt 之前) → 结果全丢。
2026-08-27 那次用 `after/before: null`(可序列化), 所以这个潜伏 bug 一直没暴露。

**根因 2(风控, 计划未预算)**: 连续跑约 6 小时后被限流 —— 2025 段第 7 个号起、2026 段全部
出现"收集 0 条"(作品接口不返回数据), 每个号仍空耗 80-95s。

**已修(工具2)**:

| 修复 | 内容 |
|---|---|
| **日期归一化** | `parser._iso_date()`: 解析期把 date/datetime → ISO 字符串(过滤层本就用 `date.fromisoformat(str(...))`, 行为不变) |
| **序列化兜底** | cli 所有 `json.dumps(..., default=str)`, 绝不因非原生类型丢结果 |
| **落盘顺序** | 先写最有价值的 `urls.txt`, 再写其余; 每个输出独立 `try/except`(`_safe_write`) |
| **在线 checkpoint** | `run_douyin_ids(checkpoint_path=...)`: **每完成一个号就落盘** → 崩溃最多丢一个号 |
| **限流早停** | 连续 3 个号收集 0 条 → 判定限流, 提前中止本段(不再空耗) |
| **运行器加固** | 只归档**本次新写**的产物(旧文件不再被误当本段结果); 段间冷却 5 分钟, 上段无产出则冷却 20 分钟 |

**新增**: 测试 21 → **41 个**(含 `test_parser_regression.py` 锁定日期回归);
`tools/probe_rate_limit.py`(单次主页加载探测限流是否解除)、`tools/run_stage1.py`(分段运行器)。

**教训(写进下次同类任务的前置清单)**:
1. 新增过滤/配置字段后, **先跑一次"能写出全部产物"的最小验证**, 再开始长任务
2. 任何长任务必须有**在线 checkpoint**, 不能只在最后统一落盘
3. 连续 6 小时爬取**必被限流** → 分段跑 + 段间冷却 + 探针确认, 是硬性要求而非可选项
4. 运行器的归档逻辑要校验文件**新鲜度**, 否则会把旧文件当新结果

**当前状态**: 探针实测(2026-09-13 15:5x)**仍被限流**(接口调用 2 次、收到 0 条) →
需冷却后再探; 确认 OK 才重跑。重跑按段进行(**先 2024 单段**), 不再三段连跑。

### 2.4 常驻浏览器状态

需用时启动: `cd v1/tool2-search && python -m smsearch browser start`(小号 cookie 在 `.profile`)。

## 2.5 监控看板 (MONITOR, 2026-09-11 新增)

| 文件 | 维护方 | 内容 |
|---|---|---|
| `MONITOR.md` | **自动生成** | 实时看板: 正在做什么 / 待办 / 问题风险 / 产出进度 / 预检明细 |
| `monitor_state.json` | 人工 | 待办清单 + 问题风险(改这里, 下次刷新带出去) |
| `monitor.py` | — | 生成器; `--loop 300` 循环或单跑 |

- **刷新机制**: Windows 计划任务 **`DouyinMonitor`**(每 5 分钟, 与会话无关)
  - 查看: `Get-ScheduledTaskInfo -TaskName DouyinMonitor`
  - 停用: `Stop-ScheduledTask -TaskName DouyinMonitor` / `Unregister-ScheduledTask -TaskName DouyinMonitor`
- **实时进度信号**: 从 CDP 9222 读浏览器**当前打开的抖音页面 URL** —— 后台任务 stdout 被块缓冲时, 这是唯一可见的活进度
- 注意: 不要同时用 `monitor.py --loop` 跑第二份, 会与计划任务**双写**同一文件

---

## 3. 还有什么要做

### 🔴 短期
1. **人工抽检标注质量**:看 `v1/tool3-analyze/output/labels_sample_*.md`(各 20 条),判断标签体系/prompt 是否需要调整
2. 若抽检发现错误率高 → 改 `tasks/*.yaml` 的 prompt_hint → 重标(缓存会自动失效)

### 🟡 中期
3. **工具3 v0.3**:自由文本需求(LLM 解析 → YAML → 确认)
4. 工具1 待办: SKILL.md 安装、补字段(作品数/音乐/分辨率)、会话过期测试
5. 工具2 遗留: 排序后首屏不重排、多关键词未实测

### 🟢 硬缺口(v2 路线)
6. **播放量**(网页端不可得)、**距离目的地**(无用户位置)、**方言识别**、**工作人员出镜判断**(待 VLM/人工决策)

---

## 4. 快速上手命令

```powershell
# 环境变量(每次新 shell 都要设)
$env:PLAYWRIGHT_BROWSERS_PATH='D:\zhy\抖音\.cache\ms-playwright'
$env:TMP='D:\zhy\抖音\.cache\tmp'; $env:TEMP='D:\zhy\抖音\.cache\tmp'
$py = 'D:\zhy\抖音\.venv\Scripts\python.exe'

# 起常驻浏览器(工具1/2 共用)
cd D:\zhy\抖音\v1\tool2-search
& $py -m smsearch browser start          # 或 status / stop

# 工具2: 搜索产出 URL 清单
& $py -m smsearch request.douyin_id.yaml

# 工具1: 按清单采集
cd D:\zhy\抖音\v1\tool1-collect
& $py -m smfetch batch urls.2x10.txt     # 断点续跑

# 工具3: 分析
cd D:\zhy\抖音\v1\tool3-analyze
& $py -m smanalyze metrics               # 看指标库(能力边界)
& $py -m smanalyze plan request.example.yaml   # 四态判定预览
& $py -m smanalyze run request.example.yaml    # 统计引擎 → 变量表
& $py -m smanalyze label request.example.yaml --dry-run   # 标注成本预估
& $py -m smanalyze label request.example.yaml            # 执行标注
```

---

## 5. 数据盘点快照

| 位置 | 内容 |
|---|---|
| `v1/tool1-collect/data/douyin/` | 23 视频 × 四件套(详情/评论/视频/字幕) |
| `v1/tool1-collect/data/douyin/<id>/comments.json` | 合计 22162 条评论 |
| `v1/tool3-analyze/output/variables_*.csv` | 分析层变量表(视频层46列/评论层16列) |
| `v1/tool3-analyze/output/labels_*.csv` | LLM 标注结果(意愿分级 22162 条 + 视频类别 23 条) |

---

*本文档随时可更新。核心知识沉淀在各工具 DESIGN.md 与 AGENTS.md,本文档是"入口索引 + 现场快照"。*
