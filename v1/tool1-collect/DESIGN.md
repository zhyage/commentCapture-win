# smfetch v1 设计文档

> 状态: **工具1(原始数据收集) v0 完成 + 视觉派生(v0a/v0b/v0c)可行性验证完成 + 字幕增强(策略3+LLM修正)完成** | 日期: 2026-08-25, 追记 2026-08-28
> 实现: 52/52 单测通过; 真实全量抓取(评论/字幕/视频/视觉/场景/关键帧)通过; 浏览器改为共享常驻(CDP 9222)

---

## 1. 项目定位

面向社交媒体的数据采集工具。v1 仅支持抖音, 采集四类数据:
1. 文案与元数据(点赞/评论/收藏/转发/发布时间)
2. 评论(顶层 + 楼中楼回复), 含作者互动标记
3. 视频文件(无水印)
4. 口播字幕(Whisper 转写, 支持 GPU)

核心原则: **安全优先**(只读、小号隔离、真人节奏、熔断), 支持无人值守(批量队列 + 断点续跑 + 微信通知)。

> 定位说明: 本工具是"三工具集"中的**工具1(原始数据收集)**, 工具2(搜索)/工具3(分析)的联合设计见 `v1/DESIGN.md`。

## 2. 范围

### v1 做
- 抖音适配器(详情/评论/回复/下载)
- 回复线程分页(大回复楼抓全)
- 会话过期检测 + 重新登录提示
- 批量队列 + 断点续跑 + 受阻清单
- 微信通知(Server酱, 企业微信预留)
- 统一 schema v0.1 落盘
- DSH skill (SKILL.md)
- 单测 + 黄金数据测试 + 冒烟

### v1 不做
- Codex 适配(AGENTS.md) — 用户明确 v1 只做 DSH skill
- 多平台适配器(接口预留)
- MCP server
- 定时调度 / 多账号轮换
- 验证码自动识别(打码平台)
- 研究字段(情感/主题标记) — 分析层处理

## 3. 目录结构

> 工具1 位于三工具结构中的 `v1/tool1-collect/` (详见 v1/DESIGN.md 高层设计)

```
D:\zhy\抖音\v1\tool1-collect\
├── DESIGN.md                  ← 本文档(工具1 详细设计)
├── config.yaml                ← 用户配置(节奏/通知/路径)
├── config-test.yaml           ← 测试配置(2000条/长轮次)
├── smfetch/                   ← Python 包
│   ├── __init__.py
│   ├── __main__.py            ← python -m smfetch
│   ├── cli.py                 ← 命令行入口(argparse)
│   ├── config.py              ← 配置加载与合并(CLI > 文件 > 默认)
│   ├── schema.py              ← 统一schema: 记录模型 + 序列化
│   ├── pipeline.py            ← 管线编排(单条/批量/导出)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            ← PlatformAdapter 抽象接口
│   │   └── douyin.py          ← 抖音实现(Playwright + 响应拦截)
│   ├── session.py             ← 登录态管理 + 过期检测
│   ├── risk.py                ← 节奏/上限/熔断/卡住检测
│   ├── queue.py               ← 批量队列 + 断点续跑(JSONL)
│   ├── notifier.py            ← 通知(Server酱/企业微信)
│   ├── browser.py             ← 连接常驻浏览器(CDP 9222, 与工具2共享; 不自起进程)
│   ├── asr.py                 ← Whisper 封装(策略3 两遍自适应 VAD)
│   ├── correct.py             ← 字幕 LLM 修正(DeepSeek, 依据文案背景, 派生可追溯)
│   ├── visual.py              ← 视觉特征 v0a (mediapipe, 需 venv312)
│   ├── scene.py               ← CLIP 场景语义 v0b (需 venv312)
│   ├── keyframes.py           ← 关键帧提取 v0c (需 venv312)
│   └── export.py              ← CSV/JSON 导出
├── tests/
│   ├── conftest.py            ← 黄金数据 fixtures(真实数据固化)
│   ├── test_schema.py / test_queue.py / test_risk.py
│   ├── test_notifier.py / test_export.py / test_cli.py / test_visual.py
│   └── test_asr_strategy.py   ← 策略3决策 + LLM修正合并 (2026-08-28)
├── tools/                     ← 批处理/实验脚本(run_visual/run_scene/run_keyframes等)
├── data/                      ← 采集输出(schema 落盘)
├── data-2000/                 ← 长跑测试输出(独立目录)
└── SKILL.md / README.md       ← DSH skill / 使用手册
```

> 共享基础设施在工程根: `.venv`(py3.14 主环境), `%LOCALAPPDATA%\smfetch\venv312`(py3.12 视觉环境),
> `.cache/`(模型/浏览器), `.profile/`(小号登录态) — 详见 v1/DESIGN.md §3。

## 4. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| 语言 | Python 3.14(现有环境) | 已有 venv |
| 浏览器自动化 | Playwright (sync) | 已验证; **连接常驻浏览器(CDP 9222, 工具2共享)**, 免签名逆向 |
| CLI | argparse(标准库) | 零依赖, 简单 |
| 配置 | YAML (pyyaml) | 可读性好 |
| 转写 | faster-whisper + 本地模型(离线) | 已验证 GPU/CPU; 讯飞 API 为备选(见§16) |
| 测试 | pytest | 标准 |
| 数据落盘 | JSON(schema) + CSV(导出) | 结构化 + 研究友好 |

## 5. 架构分层

```
CLI (cli.py)
  │
  ├─ 队列层 (queue.py)      批量/续跑/受阻, 调度单条任务
  │     │
  │     └─ 适配器接口 (adapters/base.py)
  │            │
  │            └─ 抖音适配器 (adapters/douyin.py)
  │                   ├─ session.py   登录态/过期检测
  │                   ├─ risk.py      节奏/上限/熔断
  │                   ├─ notifier.py  阻塞事件 → 微信
  │                   ├─ asr.py       转写(可插拔)
  │                   └─ schema.py    统一记录
  │
  └─ export.py   ← 数据 → CSV/JSON
```

依赖方向: CLI → queue → adapter; adapter 内部依赖 session/risk/notifier/schema。
**纯逻辑层(风险/队列/schema/通知/导出)不依赖浏览器**, 保证可单测。

## 6. Schema v0.1 规范

### 6.1 VideoRecord (data/<platform>/<id>/video.json)

```json
{
  "schema_version": "0.1",
  "platform": "douyin",
  "platform_item_id": "7447163286870707508",
  "url": "https://www.douyin.com/video/7447163286870707508",
  "source_short_url": null,
  "collected_at": "ISO8601+08:00",

  "author": {                       // 事实: 采集时点快照
    "id": "405032890799566",
    "nickname": "红河文旅",
    "certification": null,
    "signature": null,
    "follower_count": 151005,       // 粉丝数
    "following_count": 0,           // 关注数
    "favoriting_count": 1163,       // 喜欢数
    "total_favorited": 3881508,     // 获赞总数
    "aweme_count": null             // 作品数(视频详情接口无, 需抓主页; v1 为 null)
  },

  "caption": "…",                   // 文案
  "hashtags": ["…"],                // 话题(从文案解析)
  "publish_time": "ISO8601+08:00",

  "stats": {                        // 事实: 采集时点快照
    "likes": 11566,                 // 点赞数
    "comments": 1937,               // 评论数
    "shares": 548,                  // 转发数
    "collects": 243,                // 收藏数
    "recommends": 76
  },

  "media": {"type": "video", "duration_seconds": 56.4, "video_file": "…", "size_bytes": 18553206},

  "subtitles": {                    // 可选(仅 --subtitle 时)
    "source": "whisper",
    "engine": "faster-whisper",
    "model": "faster-whisper-medium",
    "language": "zh",
    "segments_count": 13,
    "full_text": "…",
    "segments_file": "…subtitles.json"
  },

  "comments": {
    "collected_count": 322,
    "platform_total": 1937,
    "coverage_note": "…",           // 元信息: 数据完整度
    "file": "…comments.json"
  },

  "author_engagement": {            // 派生
    "total_author_replies": 25,
    "replied_comment_count": 25,
    "comments_with_author_reply": ["cid", …]
  }
}
```

### 6.2 CommentRecord (comments.json, 数组, 扁平+parent_id树)

```json
{
  "comment_id": "…",
  "parent_id": null,                // 楼中楼指向父评论, 顶层null
  "user": {"id": "…", "nickname": "…", "is_author": false},   // is_author 事实
  "text": "…",
  "likes": 1126,
  "reply_count": 261,
  "created_at": "ISO8601+08:00",
  "ip_label": "江西",
  "is_hot": false,
  "author_replied": true,           // 派生
  "author_reply_ids": ["…"],        // 派生
  "author_reply_count": 1           // 派生
}
```

### 6.3 SubtitleRecord (subtitles.json)

```json
{"index": 1, "start": 0.34, "end": 2.34, "text": "大家好 我是洪大勇"}
```

**字幕两版制 (2026-08-28 起)**:
- `subtitles.json/srt/txt` — **ASR 原始底稿**(策略3 输出), 永不被改写
- `subtitles.llm.json/srt/txt` — **LLM 修正版**(DeepSeek 依据 video.json 文案背景修正专名/同音错字; 无依据片段保留原文并追加 `[识别不确定]`), 字段结构与原始相同
- video.json 的 `subtitles`: `source` = `whisper`(无修正)或 `whisper+llm`(有修正); `corrected_file` 指向修正版 json; `corrected_note` 记录依据/模型; `asr_note` 记录策略3 是否触发第2遍(VAD=False)
- 修正版属**派生数据**(可再生); 研究端若用修正版须知道其含 LLM 推断

### 6.4 字段属性约定
- 事实字段: 采集时直接来自平台, 固化
- 派生字段: 由事实计算, schema 内标注 `_derived` 说明
- 元信息字段: `coverage_note` 等, 记录完整度
- 所有数字统计均为**采集时点快照**, 可比研究须同批同天采集

## 7. CLI 规范

```
smfetch login [--force]
smfetch fetch <短链|ID> [--comments|--no-comments] [--subtitle]
                    [--model tiny|small|medium|large-v3] [--device cpu|cuda]
                    [--output DIR] [--force]
smfetch batch <urls.txt> [--per-day N] [--reset] [--no-notify]
                    [--pause | --skip-on-block] [--dry-run]
smfetch status
smfetch export [--format csv|json] [--scope comments|videos|all]
smfetch config --show
```

exit code: 0 成功 / 1 出错 / 2 受阻待处理
设计原则: 命令只管"做什么", 节奏细节全在 config.yaml; 默认保守。

## 8. 配置规范 (config.yaml)

```yaml
platform: douyin
profile_dir: .profile
output_dir: data

pacing:            # 安全节奏(防封)
  scroll_wait: [6, 12]
  pause_every: 5
  pause_long: [15, 25]
  max_scrolls: 25
  max_comments: 2000      # 单次上限(用户已确认默认2000)
  stall_limit: 5

safety:
  max_per_day: 200        # 单日全局限额
  read_only: true         # 硬约束: 只读

asr:
  model: medium
  device: cuda
  local_model: .cache/hf-local/faster-whisper-medium

notify:
  channel: serverchan
  serverchan: {sendkey: ""}
  wecom: {webhook: ""}
```

## 9. 安全与风控设计

1. 只读硬约束: 代码层禁止点赞/关注/评论/转发操作
2. 真人节奏: 随机间隔 + 阅读停顿 + 平滑滚动(JS驱动, 不依赖物理光标)
3. 卡住检测: 连续 stall_limit 轮无新增 → 停止
4. 熔断: 验证码频繁 → 冷却; 连续失败 → 标记受阻 + 通知
5. 会话过期检测: 登录墙特征 → 标记 blocked + 微信通知"请重新扫码"
6. 单日限额: max_per_day 跨会话累计
7. 小号隔离: profile 与主号分离(文档红线)
8. 合规: 只采公开数据; 评论涉及个人信息, 研究用注意去标识化

## 10. 队列与无人值守

- 队列文件: data/.queue.jsonl, 每行 {video_id, url, state: pending|done|blocked, error, retries}
- 断点续跑: 启动时读取队列, done 跳过, blocked 列出
- 受阻处理: blocked 视频不阻塞批次, 汇总清单通知; 修复后重跑自动补抓
- 幂等: 按 video_id / comment_id 去重合并, 多次采集累积

## 11. 通知设计

- notifier.py: BaseNotifier → ServerChanNotifier / WeComNotifier
- 事件: 卡住(验证码/登录过期/风控), 单条失败, 批次完成
- 频率: 只发关键事件, 不发心跳; 受阻清单合并成一条
- 密钥仅存 config.yaml, 不进代码

## 12. 测试策略

### 黄金数据测试(核心)
- fixtures: 现有真实数据固化(detail.json / comments.json 322条 / subtitles)
- test_schema.py: author画像块8字段 / parent_id推导(68回复) / is_author(25作者回复) / 聚合
- 价值: 抖音改字段立刻暴露

### 单元测试(纯逻辑, 无网络无浏览器)
- test_queue.py: 续跑/去重/受阻/重试计数
- test_risk.py: 每日限额/节奏边界/卡住判定
- test_notifier.py: mock urllib, payload 断言
- test_export.py: CSV 行列/中文/emoji 编码
- test_cli.py: 参数解析/配置合并优先级

### 冒烟(手动, pytest -m smoke)
- 登录态检测 → 抓一条新视频 → 四类数据齐全
- 转写: tiny 模型 + 短音频, CPU/GPU 各一次

## 13. 开发计划(里程碑)

| 阶段 | 内容 | 验收标准 | 工时 |
|---|---|---|---|
| P0 骨架 | 包结构/config.yaml/CLI空壳/黄金fixtures | 目录就绪, pytest 可跑 | 0.5天 |
| P1 schema | schema.py + 黄金测试 | 322条真实数据映射全对 | 0.5天 |
| P2 纯逻辑 | session/risk/notifier/queue/export + 单测 | 全部单测通过 | 0.5天 |
| P3 适配器 | douyin.py(登录/详情/评论/回复分页/下载) | 复用现有逻辑, 单条端到端 | 1天 |
| P4 CLI集成 | 全命令打通 + 冒烟(1-2条真实小抓) | 四类数据端到端 | 0.5天 |
| P5 Skill | SKILL.md + README + 交付说明 | 可加载可用 | 0.5天 |
| 合计 | | | ~3.5天 |

P3 中回复线程分页: 展开后点击"查看更多回复"循环 + 拦截回复接口 cursor 分页。

## 14. 风险与对策

| 风险 | 对策 | 实测结论(v1) |
|---|---|---|
| 回复分页深度未知(能否触底) | 先做"分页尽力 + 记录覆盖率" | ✅ 实测: 页面懒加载在 ~984 条触底(顶层748/1937≈38.6%); 回复第一层120线程全覆盖; 大回复楼(261条)深度分页失败(仅1条) |
| 连续抓2000条触发风控 | 专门实测; 节奏参数可调 | ✅ 实测: ~30分钟连续会话/300+请求, 零风控信号; 实际触底984条未到2000上限 |
| 抖音改接口/页面 | 黄金测试兜底 + 适配器内聚便于修 | - |
| 会话过期 | 过期检测 + 通知 + 重扫流程 | - |
| 模型质量(口播转写) | medium 已验证; 可换 large-v3/FunASR(接口预留) | - |

## 17. ASR 备选方案: 讯飞 iFlytek (暂不实施, 记录备用)

> 状态: **备选项**, 未接入。触发条件: 方言需求确认 / Whisper 质量不足时启用。

### Whisper 已知短板 (本方案要解决的)
1. **方言**: Whisper 仅能粗分粤语(yue)/闽南(zh-min-nan), 四川/东北/河南等区域方言会被"普通话化", 无法标注方言区
2. **无标点**: 转写输出不带标点, 影响反问/口语化等文本特征检测
3. 中文口音/绕口令/歌唱段准确率中等

### 讯飞方案 (路线 A: 在线 API)
- **录音文件转写 (lfasr)**: REST 上传音频→轮询, 适合离线批量; 支持**主要方言**(粤/川/豫/东北/吴等十几种, 以官网为准)、**带标点**、数字规整
- **语音听写 (iat)**: 实时 WebSocket, 方言参数, 2025 升级后方言准确率 60%→98%
- 接入: xfyun.cn 注册→建应用拿 appid/api_key/api_secret→asr.py 加 iFlytekASR 适配器(与 Whisper 同一接口, 可插拔)
- 成本: 免费额度 + 按量计费; 研究量级(数百条视频)约几十~几百元
- Effort: 0.5~1 天; 需要用户提供 appid/secret
- 参考: https://www.xfyun.cn/services/lfasr , https://www.xfyun.cn/site/3340.html

### 开源备选 (路线 B: 本地免费)
- **FunASR (阿里)**: 有方言 ASR 方案(如四川话)与方言分类模型; 本地运行零费用, 需装 torch(Py3.14 兼容性待排查)
- 方言分类开源参考: chinese-dialect-recognition (2018 讯飞方言赛, 十类方言 acc 0.82)
- Effort: 1~2 天

### 决策触发条件
1. 先做**方言需求量化**: 用现有视频统计 Whisper 转写中"疑似方言"(低置信度/乱码)片段占比, <5% 则维持 Whisper
2. 确认需要方言/标点 → 优先路线 A (讯飞 API), FunASR 为不付费备选

## 18. 视觉特征 (v0a/v0b/v0c, 2026-08-25 可行性验证完成)

### 实现状态
- 模块: `smfetch/visual.py`, 批处理: `tools/run_visual.py`
- 产出: `data/douyin/<id>/visual.json` (engine: v0a-mediapipe-solutions)
- 指标: 出镜比例 / 人脸数量 / 自拍指数 / 镜头运动(静止/平移/手持) / 抖动指数
- 验证: 3 视频结果合理(红河文旅出镜63%, 木工孙平移, 科普手持)

### 关键经验 (踩坑记录)
1. **mediapipe 1.0.1 的 py3.14 wheel 残缺**(py3-none, 无 .pyd) → 弃用; 用 **0.10.21**(完整 solutions API, 但仅支持到 py3.12)
2. **中文路径坑**: mediapipe C++ 内核 fopen 读不了含中文的路径(与 OpenCV FaceDetectorYN 同款问题) → 依赖环境的 site-packages 必须在 ASCII 路径
3. **解决方案**: uv 装独立 Python 3.12 → venv 建在 ASCII 路径 `%LOCALAPPDATA%\smfetch\venv312` → 装 mediapipe==0.10.21 + opencv + numpy
4. 运行: `%LOCALAPPDATA%\smfetch\venv312\Scripts\python.exe tools/run_visual.py` (数据仍在中文路径无妨, cv2.VideoCapture 可读)

### 待办 (v0b/v0c)
- ~~v0b: CLIP 零样本场景语义~~ **已完成(2026-08-25)**: `smfetch/scene.py` + `tools/run_scene.py`, 输出 scene.json (engine: v0b-clip-vitb32)
  - 实现要点: open_clip ViT-B/32 + quick_gelu=True; preprocess 需 PIL Image 不能喂 numpy; 权重走 HF(可达)
  - 验证: 专业度分 0.34(车内)/0.40(景区)/0.66(科普演示) — 区分度成立, 主场景判断正确
  - 注意: 科普类视频的动画/地图画面会被判为 stage/presentation → 可视为"专业制作感"信号; 标签集可调
- ~~v0c 关键帧提取~~ **已完成(2026-08-25)**: `smfetch/keyframes.py` + `tools/run_keyframes.py`, PySceneDetect ContentDetector
  - 产出: keyframes.json + keyframes/*.jpg + keyframes_sheet_*.jpg (人工核验网格图)
  - 验证: 3 视频 20/31/45 镜头; 每镜头一帧代表
  - 坑: cv2.imwrite/imread 中文路径静默失败 → 字节读写(imencode/imdecode + write_bytes)
- **v0c 工作人员出镜/非正式场景判断**: **暂停** (可行性分析到此为止)。关键帧机制已就绪; 判断方式待研究端决策: VLM 自动(本地 Qwen2.5-VL 或 API, 1~2天) vs 人工标注(网格图, 样本小最可靠)。同一套关键帧亦可用于 v0a/v0b 分数的人工核验

## 15. 决策记录

| 决策 | 结论 | 依据 |
|---|---|---|
| 默认评论上限 | 2000条 | 用户确认; v1后实测风控 |
| v1 平台 | 仅抖音 | 适配器接口预留 |
| 交付形态 | CLI + DSH skill | Codex/MCP 后置 |
| 回复分页 | 进 v1 | 数据完整性 |
| 研究字段 | v1 不加 | 分析层处理 |
| 根因修复 | 真实点击(trusted)替代合成点击 | 实测发现前端忽略合成事件 |
| 会话保存 | 浏览器 profile 目录 | 登录态与设备指纹绑定 |
| 模型源 | 本地模型文件(离线) | 国内网络/免下载 |

## 16. v1.1 待办 (2026-08-25 2000条实测后记录)

### 实测数据 (config-test.yaml, 126轮/约30分钟/零风控信号)
- 总记录 984 = 顶层 748 + 回复 236
- 作者回复 107 条(此前短会话仅25条; 长会话显著提升作者互动捕获)
- 停止原因: 连续无新增(页面懒加载触底), 非风控阻断
- 覆盖率: 顶层 748/1937≈38.6%; 回复第一层 120/120 线程; 大回复楼深度分页失败

### 待办项
1. ~~"全部评论"面板驱动~~ **已实验(2026-08-25): 未突破** — 无独立弹层, 顶层仍748
2. ~~线程内分页~~ **已修复+已到顶(2026-08-25)**: 「展开更多」是分页真控件; 单线程实验可达253/261。**最终结论**: 网页端天花板 ≈ 748顶层 + 889声明回复 ≈ **1637**(已抓1646含孤儿回复, 占平台1937的85%); 剩余~300为服务端计数中UI不展示的深层嵌套/隐藏评论, **网页端不可达**。普通视频(顶层<748)可100%抓全, 爆款视频封顶~85%
3. ~~覆盖率写入~~ **已完成(2026-08-25)**: CommentsMeta 新增 top_level_count/reply_count/author_reply_count/top_level_coverage; 抓取自动写入 + 存量已回填(backfill_coverage.py)
4. **会话过期真实触发测试**: 待登录态自然过期后验证 SessionExpired 检测 + 微信通知 + 重扫流程
5. **抓满爆款视频的完整评论** (v2, 需换路线): 移动端接口 / 抖音开放平台 / 付费数据平台

### 已确认无需做
- 2000条上限本身: 实测页面深度先于上限到来, 上限保留为安全网, 无需调大

## 19. 工具1(原始数据收集) 现状清单 (2026-08-25, 追记 2026-08-28)

### 能力清单
| 能力 | 模块 | 状态 |
|---|---|---|
| 采集: 详情/文案/统计/作者画像 | adapters/douyin.py | ✅ |
| 采集: 评论(顶层+楼中楼+作者互动, 回复分页) | adapters/douyin.py + schema.py | ✅ 85%天花板实测 |
| 采集: 视频(无水印) / 字幕 | asr.py | ✅ |
| 字幕策略3: 两遍自适应 (低覆盖率自动 VAD=False 重跑) | asr.py `transcribe_adaptive` | ✅ 2026-08-28 |
| 字幕 LLM 修正 (文案背景 → DeepSeek; 存 subtitles.llm.*, 保留原始) | correct.py | ✅ 2026-08-28 |
| 批量无人值守: 队列/断点续跑/受阻重试/微信通知 | queue.py / notifier.py / pipeline.py | ✅ |
| 安全: 只读/节奏/熔断/会话过期检测/单日限额 | risk.py / session.py | ✅ |
| 浏览器: 连接常驻浏览器(CDP 9222, 与工具2共享) | browser.py | ✅ 2026-08-28 (原自起进程与工具2抢 .profile 锁, 已弃) |
| 导出: CSV(视频汇总/评论) | export.py | ✅ |
| 派生: 视觉 visual.json (出镜/人脸/自拍/运动) | visual.py (v0a) | ✅ |
| 派生: 场景 scene.json (专业度) | scene.py (v0b) | ✅ |
| 派生: 关键帧 keyframes/ (镜头代表帧+网格图) | keyframes.py (v0c) | ✅ |
| 测试 | tests/ (52 用例, 黄金数据+纯逻辑) | ✅ |

### 运行环境
- **主环境** `D:\zhy\抖音\.venv` (Python 3.14): 采集/字幕/导出/CLI
- **视觉环境** `%LOCALAPPDATA%\smfetch\venv312` (Python 3.12, ASCII路径): visual/scene/keyframes (mediapipe/CLIP/scenedetect 的原生库要求)
  - 原因: mediapipe 1.0.1 wheel 残缺 + 中文路径导致原生库读文件失败(详见 §18)
- **ASR 设备**: config 固定 `cpu`(本机 cublas64_12.dll 缺失, GPU 不可用); asr.py 保留 GPU→CPU 自动回退
- **字幕修正**: config 需 `deepseek.api_key`(有 key 才生成修正版; 无 key 只留原始 ASR)

### 数据产出 (data/douyin/<id>/)
`video.json`(含 subtitles: source=whisper+llm, asr_note, corrected_file) + `comments.json` + `subtitles.*`(原始ASR) + `subtitles.llm.*`(LLM修正版) + `video.mp4` + `visual.json` + `scene.json` + `keyframes/` + `keyframes_sheet_*.jpg`

### 待办
- [ ] SKILL.md 安装到 `~/.dsh/skills/smfetch/`
- [ ] 低 effort 补字段: 作品数(抓作者主页) / 音乐 / 分辨率
- [ ] 会话过期真实触发测试 (v1.1 待办4)
- [ ] 播放量: 网页端不可得, v2 路线(移动端/数据平台)
- [ ] 方言需求量化 (备选触发, §17)
- [ ] v0c 工作人员出镜/非正式场景判断: 暂停待研究端决策 (VLM vs 人工标注, 关键帧已就绪)

### 近期修复记录 (2026-08-27/28)
- ASR GPU(cublas)缺失: 初始化+转写全程回退 CPU (此前转写阶段失败会卡死进程 9h)
- stdout GBK 编码崩溃 → CLI 强制 UTF-8 + errors=replace (与工具2 一致)
- urls 清单 BOM 污染 (\ufeff) → 写入统一无 BOM UTF-8
- 实测: 17 条目标视频字幕全量重跑(策略3+LLM); 3 条 blocked 无 mp4 无法转写
