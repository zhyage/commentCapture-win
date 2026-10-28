# 监控看板 (MONITOR)

> 自动生成: **2026-09-13 16:50:06** ｜ 刷新机制: ⚠️ 已停止自动刷新（计划任务已删除）。本文件为冻结快照；恢复自动刷新需重新注册任务或跑 monitor.py --loop
> 本文件由 `monitor.py` 重写, 请勿手工编辑; 手工维护的部分在 `monitor_state.json`

## 1. 现在正在做什么

**当前聚焦**: ⏸ 用户主动暂停（2026-09-13 16:50）：重新论证取样策略；所有采集/监控任务已停止，计划任务 DouyinMonitor 已删除

| 信号 | 观测值 |
|---|---|
| 常驻浏览器(CDP 9222) | ✅ 运行中 · Chrome/151.0.7922.34 |
| 打开的页面数 | 23 |
| 相关后台进程 | 无（当前没有采集/加工任务在跑） |

**浏览器当前打开的抖音页面**（实时进度信号）:

- `https://www.douyin.com/user/MS4wLjABAAAAWSWF8iYfAxMV-BT9Yql2v9yn9OXPasox_8_NcvphUoX28-Th4-BNxnyN3GPApa7-?from_tab_name=m`
- `https://www.douyin.com/user/MS4wLjABAAAANaxL5A-fVLepESopaxYad4yrpr6SXFsQKX9xa_1_92E?from_tab_name=main&showSubTab=video&`
- `https://www.douyin.com/video/7605544093448211059`
- `https://www.douyin.com/user/MS4wLjABAAAAgfW402YshG30a2WRdYlkRyYdTYsD0MgpCe-Ki5Ymf70?from_tab_name=main&showSubTab=video&`

## 2. 还需要做什么

| # | 事项 | 状态 | 阻塞点 |
|---|---|---|---|
| 1 | 【待你定·阻塞】取样策略：点赞门槛 / limit / 是否分层随机抽样 | ⏳ 待定 | 现行规则(≥1000赞 + 每年前9) = 各号年度最火9条(top 0.5-4%), 使 idea.md 的“控制热门程度”“热门/非热门对比”失效 |
| 2 | 【待办】按新取样策略改造工具2：一次翻页 + 本地切片 | ⏳ 待办 | 省 66% 请求 + 解锁随机抽样; 纯代码, 离线可做 |
| 3 | 账号预检 9 个号（9/9 target） | ✅ 完成 | - |
| 4 | 修工具2 主页身份校验缺陷（生产已验证） | ✅ 完成 | - |
| 5 | 修工具2 序列化崩溃 + checkpoint + 限流早停 | ✅ 完成 | - |
| 6 | 【待办】限流冷却后重跑（探针 tools/probe_rate_limit.py 确认 OK 再跑） | ⏸ 暂停 | 用户暂停; 上次探针(15:43)仍 EMPTY |
| 7 | 【待办】工具1 采集 → 视觉派生 → 工具3 plan/run/label | ⏳ 待办 | 等取样策略定稿 |

## 3. 碰到的问题 / 风险

- **[阻塞]** 【取样策略未定】现行规则 = min_likes≥1000 + 每年点赞前 9 → 实际是“每个账号每年最火的 9 条”(选择率 top 0.5%-4%)。后果: ①idea.md 把点赞列为控制变量, 但样本全爆款→方差被压没 ②“不同样本(热门/非热门)”检验无对照组 ③skill 警告过高赞抽样偏向吐槽。选项: A保持 / B分层(前5+随机5) / C放宽或取消门槛让点赞成为连续控制变量
- **[已解决]** 【事故】2026-09-13 三段爬 6.3 小时产出 0 条: 根因①after/before 被 YAML 解析为 datetime.date → json.dumps 崩溃(崩在写 urls.txt 之前, 结果全丢; 2024/2025 实际已爬成功 81+54 条命中) 根因②连跑 6 小时被限流。已修: 日期归一化 + default=str + 先写 urls + 每号 checkpoint + 连续 0 条早停 + 运行器新鲜度校验/段间冷却; 测试 21→41
- **[已解决]** 架构冗余（已定位, 未改造）: 抖音号模式下 after/before/min_likes 都是【翻页之后】才过滤, 所以“按年份分段跑 3 次”= 同一账号全量作品被翻 3 遍。日志证据: gzslyfzwyh 2024段收集 5919 = 2025段收集 5919。解法: 一次翻页存全量 → 本地切片
- **[已解决]** 工具2 主页身份校验缺陷: DOM 常不渲染“抖音号:”字段 + 固定 sleep(6) 早于头部渲染 → 5/9 账号被静默跳过。已改三级证据(抖音号文本→官方认证徽章→昵称)+渲染等待, 生产已验证生效
- **[已解决]** 认证关键词假阴性: 浙江“文化广电和旅游厅”不含“文化和旅游厅” → 曾误判 non_target。已改“旅游厅/旅游局”锚点 + 回归测试
- **[已解决]** 样本混入 4 条非目标账号 → 已打标 non_target/excluded; 规则固化进 AGENTS.md + accounts.yaml(sample_policy)
- **[风险]** 播放量不可得 / 距离目的地不可得 / 方言无模型 → idea.md 的“控制热门程度”只能用点赞等代理; 调节变量只能降级为“是否本省”
- **[风险]** 工具2 主页翻页会混入他人作品(实测红河文旅 802 条里 34 条 = 4.2%) → 下游靠 sample_role 兜住
- **[风险]** 地区分布 7西:1中:1东 → 用户已决定接受, region 仅作控制变量, 不做地区异质性

## 4. 产出进度（自动采集）

| 指标 | 值 |
|---|---|
| 已采集视频目录 | 23 |
| 其中四件套完整 | 23 |
| 其中视觉派生完成 | 23 |
| 账号预检结果 | 8/9 定位成功 (09-11 15:14) |

**工具3 最近产物**:

- report.md (09-11 14:50)
- variables_comment.csv (09-11 14:50)
- variables.json (09-11 14:50)
- variables_video.csv (09-11 14:50)
- labels_sample_tl_llm_rhetorical.md (09-09 16:20)
- labels_tl_llm_rhetorical.csv (09-09 16:20)

## 5. 账号预检明细

| 昵称 | 抖音号 | 定位 | 认证主体 | 判定 | sample_role |
|---|---|---|---|---|---|
| 贵州文旅 | gzslyfzwyh | ✓ | - | target | main |
| 广西文化和旅游厅 | gxtravel | ✓ | - | target | main |
| 云南省文化和旅游厅 | ynswhhlyt | ✓ | - | target | main |
| 四川文旅 | sichuanwenlv | ✗ | - | - | - |
| 陕西文旅 | sxly6 | ✓ | - | target | main |
| 浙江文旅 | 26986112538 | ✓ | - | non_target | excluded |
| 重庆文旅 | cqwlzx | ✓ | - | target | main |
| 安徽文旅 | Anhuilvyou | ✓ | - | target | main |
| 红河文旅 | 55008743593 | ✓ | - | target | main |

---
_本文件仅供监控, 不替代 `PROJECT_STATUS.md`(沉淀) 与 `EXPANSION_PLAN.md`(计划) ｜ 生成器: `monitor.py`_
