# 工具2: 搜索/获取URL — 设计文档

> 状态: **v0 已实现, 第一阶段完成** (2026-08-27) | 最初定稿: 2026-08-25 | 来源: thinking.md

## 0. 阶段说明

- **第一阶段(v0)完成** = 单关键词、有限翻页、硬过滤+语义判定全链路跑通, 输出可核对的全量清单。
- 已知未覆盖: 多关键词(框架已支持)、排序后结果不严格单调、搜索偶发 0 条(软封)、`sort=latest/comprehensive` 未验证 —— 见 §9 遗留问题。
- 本文档历史结论保留(§7/§7.5/§7.6), 已实现的标注 ✅。

## 1. 定位: 工具2 = 筛选器 (Filter)

工具2 的核心职责 = **筛选** — 根据条件收集**尽量精确**的视频 URL 清单, 交给工具1 采集。
因为工具1 的处理时长与复杂度远大于搜索, 所以**"去留"尽量在搜索阶段定**, 工具1 只采值得采的。

**两段式过滤原则 (v0 实际落地)**:
```
工具2 (搜索阶段): 关键词搜索(并集去重) → 滚动翻页 → 硬过滤(客观字段) → 语义判定(内容相关性) → 输出候选清单
   ├── 硬过滤(精确): 点赞/评论/时间/作者 (statistics/create_time/author)
   ├── 语义判定(内容相关性): describe 意图 → DeepSeek 三态判定(符合/不符合/不确定)
   └── 不可判定: 口播内容/视觉/签名 — 标注"需工具1采集后二次过滤"
工具1 采集后: 字幕/视觉类条件的二次过滤 → 属于工具3/研究端
```
**决策**: keywords 仅作搜索词, **不做主题硬过滤**(文案常不含账号名导致误杀, 2026-08-27 用户确认); 内容相关性全部交给 describe 语义判定。

## 2. 目标

根据**描述性条件**从抖音找到相关的视频 URL/ID 清单, 供工具1 采集使用(不自动对接, 另行发起)。
条件开放、描述性; 输出带**命中证据与诚实性说明**。

## 3. 定位与边界

- 产出 = 结构化结果(results.json, 已过滤候选) + URL 清单(urls.txt) + 全量核对清单(collected_review.md / collected.json)
- 不负责采集(工具1)、不负责分析(工具3)、**不自动触发工具1**
- 与工具1 共享登录态与安全策略, 可独立运行

## 4. 输入设计 (已确认: 混合形态, 文本模板文件)

用户复制模板照填, 运行 `smsearch <request.yaml> [--out urls.txt]`

### 模板字段 (v0)

| 字段 | 类型 | 说明 | 处理方式 |
|---|---|---|---|
| `keywords` | list[str] | 搜索词(可多个, 并集去重) | **仅作平台搜索词, 不做主题硬过滤** |
| `after` / `before` | date\|null | 发布时间范围 | 结果 create_time 本地精确过滤 |
| `min_likes` / `min_comments` | int\|null | 互动数下限 | 结果 statistics 本地精确过滤 |
| `authors` | list\|null | 限定发布机构/账号 | 结果 author.nickname 精确过滤 |
| `sort` | likes\|latest\|comprehensive | 排序方式 | 页面"筛选→最多点赞"等(实测 likes 可用, 见 §7.5) |
| `limit` | int | 命中条数上限(语义判定后) | 达到即提前终止 |
| `describe` | str\|null | 软条件(描述性) | 拆为**语义意图列表**, DeepSeek 批量判定, 任一符合即命中 |

> 已移除: `keyword_mode`(or/and) — keywords 不做主题过滤后无意义(2026-08-27)。

### 解析逻辑 (v0, 诚实)
- 硬条件字段: 直接读取 → 本地过滤规则(逐条精确判定)
- **describe: 不参与搜索, 作为"语义后过滤"** — DeepSeek API 对候选文案做**意思匹配**(非文字匹配), 三态判定: 符合/不符合/不确定
- 判定顺序: **先硬过滤**(统计/时间/作者) 缩小候选 → 再语义判定(省 LLM 调用); 硬过滤未通过者不产生 LLM 调用
- describe 结构: 多个意图(逗号/标点/空白拆分), **任一符合即保留**

## 5. 输出设计 (已确认: 结构化 + 诚实性说明)

每次运行在当前目录生成:

| 文件 | 内容 |
|---|---|
| `results.json` | 主输出: request 回显 + performed_at + llm_calls + hits_count/uncertain_count + honesty_notes + results[](命中列表, 含 URL/作者/文案/时间/互动/matched_conditions/semantic) |
| `urls.txt` | 命中视频 URL(每行一条, 可 `smfetch batch urls.txt`) |
| `uncertain.json` | 语义"不确定"条目(单独留存待人工复核, 不占命中名额) |
| `collected.json` | **全量收集条目(不过滤)**: 每条含 URL/摘要/硬过滤判定(通过?/匹配/淘汰原因)/语义判定 — 供人工核对过滤是否合理 |
| `collected_review.md` | collected.json 的 Markdown 可读版(逐条 URL+摘要+判定) |

`results.json` 结构(v0 实际):
```json
{
  "request": {"keywords": […], "intents": […], "filters": {...}, "sort": "likes", "limit": 50},
  "performed_at": "…+08:00",
  "method": "douyin-web-search + deepseek-semantic",
  "llm_calls": 2,
  "hits_count": 10,
  "uncertain_count": 0,
  "honesty_notes": […],
  "results": [
    {"aweme_id": "…", "url": "…", "author": "…", "caption": "…",
     "publish_time": "…", "stats": {"likes": …, "comments": …, …},
     "matched_conditions": ["authors", "min_likes"], "semantic": "符合"}
  ]
}
```

## 6. 诚实性原则 (与工具3 一致)

- 每个条件标注: **平台端精确 / 平台排序近似 / 本地过滤近似 / 无法实现**
- 输出必须带 honesty_notes, 研究端据此判断数据可信度
- v0 honesty_notes 实际包含: 语义判定仅'符合'计命中 / keywords 仅搜索词 / 互动时间作者精确 / 翻页有限未翻尽 / total_favorited 不可信 / 排序是否真实切换

## 7. 已确认决策 (含第一阶段落地)

| 决策 | 结论 |
|---|---|
| 定位 | **筛选器**: 搜索阶段定"去留", 输出尽量精确的 URL 给工具1 (两段式过滤) |
| 输入形态 | 混合(文本模板文件, 结构化字段 + describe 软条件) |
| **输入模式** | **二选一(互斥)**: `keywords` 关键词搜索模式 或 `douyin_id` 抖音号主页模式 (2026-08-27 新增) |
| 用户如何提供 | 模板文件照填 (不搞 UI) |
| 输出 | results.json + urls.txt + uncertain.json + collected.json/collected_review.md(全量核对) |
| 对接工具1 | 不自动触发, 仅产清单(清单=已通过过滤的候选) |
| 解析 | v0 规则化(硬条件直读 + describe 拆意图列表), LLM 解析列 v1 |
| **技术路线** | **A1: 常驻浏览器 + CDP 连接复用** (单一 Chromium 进程, 固定 profile, 任务完不关) |
| **代码组织** | **各自写一份** (不抽 shared); 待三工具完成后再评估抽取公共核心重构 |
| **关键词语义** | keywords = **搜索词(并集去重), 不做主题硬过滤** (2026-08-27: 文案常不含账号名导致误杀) |
| **搜索排序** | "筛选"(右上角, hover 展开)→"最多点赞", 实测可切换(见 §7.5); 切换只影响切换后的翻页请求 |
| **验证码/登录墙** | 检测到登录弹窗(元素级: 扫码登录/二维码文本)或 session 缺失 → 停下提示 → 等用户扫码+明确告知("扫好了") → 放行继续; 绝不自动继续、绝不关浏览器 |
| **浏览器生命周期** | 常驻: `smsearch browser start|stop|status`; 仅显式 stop 才关; 任务失败也保持打开(与用户讨论后同浏览器继续) |
| **describe 用途** | **语义后过滤(不参与搜索)**: DeepSeek 三态判定, 任一意图符合即保留; 先硬过滤后语义判定 |

## 7.2 抖音号模式 (douyin_id, 2026-08-27 新增)

**动机**: 用户提供抖音号(如 55008743593)时, 想要"该号发布内容的全集"而非平台搜索结果。

**流程**:
```
douyin_id: [55008743593, YNHHFB, ...]   (可多条 → 串行逐号处理)
 → 回首页 → 搜索框输入抖音号 → 点 tab「用户」(保守姿势优先; 直开 ?type=user 为备选)
 → 提取用户卡片文本中的"抖音号:"字段 → 与输入精确匹配(≥8位时前缀匹配, 处理获赞数字粘连)
 → 进入主页 → 主页头部"抖音号:"文本最终校验 (兜底, 确保进对号)
 → 全量翻页: while has_more, 页间隔 2-4s 随机(10% 概率 6-10s 躲避风控), 不限时长
 → 每条走两段式过滤 (硬过滤 + DeepSeek 语义判定)
 → 每号内部按点赞数降序取前 limit 条 (每号独立 limit, 非总和; 2026-08-27 用户确认)
 → 跨号按 aweme_id 去重, 合并输出
```

**关键差异 vs 关键词模式**:
- 主页作品接口 `/aweme/v1/web/aweme/post/` **无排序参数**(默认发布时间倒序) → 必须全量翻页
- 作者过滤在该模式下恒真(主页即该号)
- LLM 预算放宽: `semantic.max_llm_calls_did`(默认 1000), 关键词模式仍为 50
- **limit 语义**: 每个抖音号各自截断 — A 号 50 条 + B 号 50 条 = 最多 100 条
- 每号独立 `_Pipeline`(独立 LLM 预算/统计/计时); 每号计时与总计时输出; collected 每条带 source_douyin_id
- 实跑: 红河文旅 55008743593 全量 802 条, 命中 117, 输出截断 50, LLM 23 次
- 实跑: 云南红河哈尼 YNHHFB 4300+ 条全量翻页(慢节奏, 观察风控)

**实测绘到的问题**:
- 搜索卡片文本"抖音号:55008743593388.3万"中抖音号与获赞数粘连 → 前缀匹配+主页校验双重保障
- 搜索页可能被重定向到 jingxuan 精选版(无用户 tab, 只有分类 tab) → 定位不稳; 保守姿势(首页→搜索框→回车)优先, 直开 `?type=user` 为备选

## 7.5 搜索阶段可判定的字段 (2026-08-25/27 实测)

| 字段 | 搜索阶段可得 | 说明 |
|---|---|---|
| desc 文案 | ✅ | 语义判定(describe)的输入 |
| author.nickname/uid/粉丝数/认证 | ✅ | 作者条件可精确判定 |
| **author.signature** | ❌ | 搜索响应为 None, 需工具1 详情接口 |
| statistics 赞/评/藏/转 | ✅ | min_likes/min_comments 精确判定 |
| create_time | ✅ | 时间范围精确判定 |
| video.play_addr 直链 | ✅ | 搜索阶段即可下载(但下载是工具1职责) |
| total_favorited | ⚠️ 不可信(返回0) | 诚实性标注: 以工具1采集为准 |
| 口播字幕/视觉/签名 | ❌ | 需工具1 采集后二次过滤(工具3/研究端) |

## 8. 可行性验证结果 (2026-08-25/27 实测)

| 待验证项 | 结论 |
|---|---|
| 接口形态 | ✅ `/aweme/v1/web/search/item/?keyword=…`; **必须走搜索框输入+回车流程**, 直接 URL 打开会撞"验证码中间页"(风控) |
| 可筛字段 | ✅ 每条含: desc / author.nickname / aweme_id / create_time / statistics(digg/comment/collect/share) / share_url(iesdouyin.com/share/video/ID) |
| 分页 | ✅ 滚动触发 cursor 分页 (20/30/40/50…, has_more=1); `.route-scroll-container` 滚动容器 |
| 风控 | ⚠️ 初始出现"验证码中间页"(自动放行); 搜索比单视频浏览敏感; 偶发**0 条软封**(见 §8.6) |
| 排序 | ✅ **"筛选"右上角 hover → "最多点赞" 已实测可切换**(2026-08-27, 连续 3 次运行成功); 切换只影响之后翻页 |
| URL 对接工具1 | ✅ aweme_id 与 share_url 均可用 |

## 8.5 搜索界面已知行为 (2026-08-25 用户人工观察 + 2026-08-27 实现验证)

- **"筛选"控件**: 位于搜索页**右上角**(x≈1738), **hover 即自动展开**(无需点击)
- 展开内容含"排序依据": **综合排序 / 最新发布 / 最多点赞**; 点"最多点赞"后新翻页按点赞降序 ✅(实现验证)
- 页面顶部另有 tab 栏"综合/视频/用户/直播/筛选"(非排序控件, 勿混淆)
- 搜索内容区文本在 `body.innerText` 读取不到(iframe/shadow DOM) → 探测时需读"所有可见元素文本", 勿依赖 body.innerText
- 页面挂有验证码组件 frame (rc-verifycenter), 可能触发登录墙/验证码中间页
- **登录墙多为 modal**(页面标题不变) → 检测必须元素级(扫码登录/二维码文本), 不能只看 title ✅(实现验证)

## 8.6 风控教训 (2026-08-25/27)

- 短时间内多次搜索/探测浏览器会话 → 触发**登录墙**(需冷却)
- **搜索类会话比单视频采集更敏感**: 节奏需更保守(关键词间冷却加长、单日搜索次数限额、探测降频)
- 冷却后登录态一般仍在(已验证); 若失效需重新扫码
- 偶发**搜索返回 0 条**(软风控/搜索触发不稳定的表象) → 不 panic, 保守重试或冷却
- 重复搜索会话期间, 常驻浏览器 + 有效 sessionid 下运行更稳(2026-08-27 连续 3 次 86 条)

## 9. 第一阶段实现总结 (v0, 2026-08-27)

### 架构: 常驻浏览器 (A1)
```
service.py   browser start|stop|status|connect
             - 独立 Chromium: 固定 profile(D:/zhy/抖音/.profile) + CDP 端口 9222
             - 进程识别: 路径在 .cache/ms-playwright + 命令行含 --user-data-dir=.profile
             - connect(): 未运行则先启动; 返回 (p, browser, ctx, page)
browser.py   connect() → service.connect() 解包返回 (ctx, page); 调用方不关浏览器
search.py    run_search: connect → 搜索页 → 登录门(_ensure_login) → 搜索框+回车
             → 拦截 /aweme/v1/web/search/item/ → 硬过滤(_hard_status) → 攒批语义判定 → 命中/预算提前终止
             → 全量收集记录(collected) 不关浏览器
cli.py       smsearch <request.yaml> [--out] 或 smsearch browser start|stop|status
             - stdout 强制 UTF-8+errors=replace (修复 Windows GBK 打印中文/emoji 崩溃)
filter.py    hard_filter/hard_status: 仅客观字段(作者/时间/互动), keywords 不参与
llm.py       DeepSeek(OpenAI 兼容, urllib 零依赖), 批量三态判定, batch_size=10, max_llm_calls=50
parser.py    request.yaml → 搜索计划 (describe 拆意图; 无 keyword_mode)
```

### 登录门协议 (用户确认的流程)
1. `_ensure_login` 元素级检测登录弹窗(扫码登录/二维码文本) 或 session 缺失
2. 命中 → 打印提示(浏览器保持打开), 阻塞等待
3. 用户手机抖音 App 扫码 → 聊天告知"扫好了" → 外部创建 `.continue.signal` 标记文件
4. 脚本检测到标记 → 验证 sessionid/sessionid_ss cookie 就位 → 继续同一浏览器会话
5. **绝不自动继续, 绝不在此关闭浏览器**; 超时(默认 1800s)也只提示不关闭

### 运行方式
```
cd v1/tool2-search
$env:PLAYWRIGHT_BROWSERS_PATH='D:\zhy\抖音\.cache\ms-playwright'
D:\zhy\抖音\.venv\Scripts\python.exe -m smsearch browser start    # 启动常驻浏览器
D:\zhy\抖音\.venv\Scripts\python.exe -m smsearch request.test.yaml  # 执行搜索(复用同浏览器)
D:\zhy\抖音\.venv\Scripts\python.exe -m smsearch browser status   # 查看状态
D:\zhy\抖音\.venv\Scripts\python.exe -m smsearch browser stop     # 显式关闭
```

### 测试
- `test_filter.py` 7 用例: 解析器(describe→intents, 空关键词报错, authors 字符串化) + 硬过滤(基础/仅实际设置/关键词不参与/时间) ✅
- 纯逻辑, 不碰网络

### 实跑记录 (request.test.yaml: 红河文旅 / 赞≥1000 / 作者=红河文旅 / likes / limit 50)
| 运行 | 收集 | 硬过滤淘汰 | 语义判定 | 命中 | 说明 |
|---|---|---|---|---|---|
| 首跑(改前) | 86 | topic 误杀为主 | 12 条→LLM 2 次 | 6 | keywords 兼做 topic 硬过滤 |
| 改后(现版) | 86 | 仅 min_likes(26)/authors(27) | 33 条→LLM 4 次 | 10 | topic 移除, 内容相关性归语义 |

- 排序"最多点赞"连续 3 次切换成功; 命中 10 条全部作者=红河文旅、赞≥1000
- 全量核对清单(86 条)产出正常, 淘汰原因逐条可查

## 10. 已知限制与遗留问题 (第一阶段)

1. **排序后结果不严格单调**: "最多点赞"切换只影响切换后的翻页请求, 首屏已加载内容不重排 → 命中列表赞数非严格降序。若需严格排序: 先切排序再采集 / 对结果二次排序。
2. **搜索偶发 0 条**: 现象存在, 触发条件未完全定位(软风控/触发不稳定), 需保守节奏。
3. **sort=latest / comprehensive** 未实测; `sort` 参数目前只实现 likes 分支。
4. **多关键词**: 框架支持(逐词搜索并集), 但第一阶段只跑过单关键词; 多词时关键词间冷却生效, 未实测验证。
5. **author.signature / total_favorited** 搜索响应不可信或缺失 → 以工具1 采集为准(诚实性已标注)。
6. **翻页上限**: max_scrolls=5 默认, 未翻尽全部结果(诚实性已标注)。

## 11. 下一步 (第二阶段候选)

- 多关键词真实用例跑通; 验证并集去重与关键词间冷却
- 排序严格性改进(§10.1)或明确接受现状
- 0 条软封的触发边界观察与应对策略固化
- 与工具1 端到端对接实测: `smfetch batch urls.txt` 采集 urls.txt 输出的 10 条
- 评估 `sort=latest/comprehensive` 分支实现
