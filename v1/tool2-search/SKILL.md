---
name: smsearch
description: "抖音搜索/筛选工具。按描述性条件(关键词/账号/点赞/时间/主题)找到符合要求的视频URL清单, 供工具1采集。支持抖音号全量翻页模式。触发词: 抖音搜索/找视频/筛选视频/取URL清单/smsearch。"
---

# smsearch — 抖音搜索/获取URL (工具2)

## 用途

根据条件找到**尽量精确**的视频 URL 清单(工具2 是"筛选器", 决定哪些视频值得采集):

- **关键词模式**: 按关键词搜索 → 硬过滤(点赞/时间/作者)→ LLM 语义判定(主题意图)
- **抖音号模式**: 给定抖音号 → 定位主页 → **全量翻页**该号所有作品 → 同样过滤

## 环境

- 目录: `D:\zhy\抖音\v1\tool2-search`
- 解释器: `D:\zhy\抖音\.venv\Scripts\python.exe`
- 依赖: **常驻浏览器**(CDP 9222), 由本工具管理
- 登录态: `../../.profile`(小号, 与工具1 共用)
- 配置: `config.yaml`(deepseek key / 语义批量 / 滚动上限)

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='D:\zhy\抖音\.cache\ms-playwright'
$env:TMP='D:\zhy\抖音\.cache\tmp'; $env:TEMP='D:\zhy\抖音\.cache\tmp'
```

## 常驻浏览器管理

```powershell
python -m smsearch browser start    # 启动(工具1/2 共用, 任务结束不关)
python -m smsearch browser status   # 查看状态
python -m smsearch browser stop     # 显式关闭(唯一关闭方式)
```

## 工作流

### 1. 写请求文件(参考 `request.example.yaml`)
```yaml
# 二选一(互斥)
keywords: [红河文旅]           # 或 douyin_id: [55008743593]
min_likes: 1000                # 硬过滤: 点赞下限
authors: 红河文旅               # 硬过滤: 作者
sort: likes                    # 关键词模式排序: likes|latest|comprehensive
limit: 50                      # 关键词模式=命中即停; 抖音号模式=每号各自截断
describe: 景点介绍, 景点推荐, 民俗   # 语义意图(LLM 判定, 任一符合即命中)
```

### 2. 执行
```powershell
python -m smsearch request.yaml
```

### 3. 输出
| 文件 | 内容 |
|---|---|
| `results.json` | 命中列表(含 matched_conditions/semantic) |
| `urls.txt` | **给工具1 的 URL 清单** |
| `collected.json` / `collected_review.md` | 全量收集条目 + 逐条过滤判定(人工核对用) |
| `uncertain.json` | 语义"不确定"条目(待人工复核) |

## 关键语义

- **keywords 只做搜索词**, 不做主题硬过滤(文案常不含账号名, 曾误杀); 内容相关性全交 `describe` 语义判定
- **硬过滤只判客观字段**: 作者/时间/点赞/评论(精确)
- **limit**: 关键词模式=达 limit 提前停翻页; **抖音号模式=每号全量判定后按赞降序取前 limit**(多号则各自 limit)
- **排序**: 关键词模式用"筛选→最多点赞"; 抖音号模式主页无排序(接口无 sort 参数)→ 全量后本地按赞排

## 安全与协议

1. **只读**: 不点赞/关注/评论
2. **登录墙协议**: 检测到登录弹窗 → 打印提示并**阻塞等待** → 用户在手机扫码 → 用户明确说"扫好了" → 外部创建 `.continue.signal` 标记 → 脚本验证 sessionid 后继续。
   **绝不自动继续; 绝不关闭浏览器**。
3. **节奏**: 翻页间隔 2-4s 随机(10% 概率 6-10s); 关键词间冷却 6-10s。不改快。
4. **风控**: 搜索会话比采集敏感; 偶发 0 条/登录墙 → 冷却后重试, 不要连跑轰炸。

## 常见坑

| 坑 | 解法 |
|---|---|
| 直接打开搜索 URL 撞验证码中间页 | 必须走"搜索框输入+回车"; 抖音号模式另有直开 `?type=user` 兜底 |
| 抖音号数字粘连("55008743593388.3万") | 已用前缀匹配 + 进主页后用主页"抖音号:"文本二次校验 |
| 页面被重定向到 jingxuan 精选版(无用户 tab) | 已内置: 保守方式(首页→搜索框→回车→点用户tab)失败后自动直开 `?type=user` |
| 排序未生效 | "筛选"在右上角, **hover 即展开**; 切换只影响之后的翻页, 首屏不重排 |
| 搜索结果 0 条 | 可能软风控; 等待冷却, 检查登录态 |

## 与其他工具的关系

- **上游**: 无(独立入口)
- **下游**: 产出的 `urls.txt` 交给**工具1** `smfetch batch urls.txt`
- 不自动触发工具1
