---
name: smfetch
description: "抖音社交媒体数据采集工具。抓取视频的文案、评论(含楼中楼与作者回复)、口播字幕、视频文件；支持批量无人值守与微信通知。触发词: 抖音/抓评论/抓字幕/采集抖音/smfetch/爬抖音数据。"
---

# smfetch — 抖音数据采集 (v1)

## 用途
采集抖音视频的 4 类数据:
1. 文案与元数据(点赞/评论/收藏/转发/发布时间/粉丝数等)
2. 评论(顶层 + 楼中楼回复, 含作者互动标记与覆盖率)
3. 视频文件(无水印)
4. 口播字幕(Whisper 本地模型) + LLM 修正版

## 环境
- 项目根: `D:\zhy\抖音\v1\tool1-collect`
- 解释器: `D:\zhy\抖音\.venv\Scripts\python.exe`
- 运行方式: 在 tool1-collect 目录下 `python -m smfetch <命令>`
- 登录态: `../../.profile`(小号, 勿动)
- 配置: `config.yaml`(节奏/限额/通知/deepseek)
- **依赖常驻浏览器**(CDP 9222): 先 `cd ../tool2-search && python -m smsearch browser start`

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='D:\zhy\抖音\.cache\ms-playwright'
$env:TMP='D:\zhy\抖音\.cache\tmp'; $env:TEMP='D:\zhy\抖音\.cache\tmp'
```

## 工作流(标准流程)

### 1. 登录(会话失效时)
```powershell
python -m smfetch login
```
弹出浏览器窗口, 用户用**小号**扫码。检测到登录成功后自动关闭。

### 2. 单条抓取
```powershell
python -m smfetch fetch <短链或ID>                 # 默认: 文案+评论+字幕
python -m smfetch fetch <短链或ID> --no-subtitle   # 只要评论, 不要字幕
python -m smfetch fetch <短链或ID> --no-comments --no-subtitle --video   # 只要视频文件
python -m smfetch fetch <短链或ID> --model medium --device cuda
```
输出到 `data/douyin/<ID>/`。字幕默认转写; `--no-subtitle` 可关闭。

### 3. 批量无人值守
```powershell
python -m smfetch batch urls.txt [--per-day 200] [--no-notify]
python -m smfetch status        # 队列/受阻清单
python -m smfetch batch urls.txt --reset   # 清空重跑
```
- 断点续跑是默认行为(按 ID 去重, 完成跳过)
- 受阻条目不阻塞批次; 修复后重跑自动补抓
- 登录过期/风控 → 微信通知用户

### 4. 导出研究数据
```powershell
python -m smfetch export --format csv --scope all
```

## 安全红线(IRON RULES)
1. **只读**: 绝不点赞/关注/评论/转发。`config.yaml` 中 `read_only: true` 是硬约束。
2. **小号隔离**: 登录只用小号; 绝不用用户主号。
3. **节奏不改快**: `pacing` 参数是防封生命线, 未经用户同意不得调高轮次/条数上限或缩短间隔。
4. **验证码人工**: 弹出滑块时等待用户手动完成; 绝不自动重试轰炸。
5. **卡住即停**: 连续无新增自动停止; 单日限额(`max_per_day`)到即停。
6. **合规**: 只采公开数据; 评论含个人信息, 提醒用户研究用去标识化。

## 平台坑速查(实测踩坑记录)
| 坑 | 解法 |
|---|---|
| 地址栏复制 URL 打开是"选择页" | 用分享的 v.douyin.com 短链; ID 才是唯一标识 |
| 评论不翻页 | 网页版是"点击查看更多"机制, 用 JS 滚动 `.route-scroll-container` |
| 展开回复无反应 | **必须用真实点击(locator.click)**, 合成点击(JS .click())会被前端忽略 |
| 大回复楼抓不全 | 线程内继续点"查看更多回复"(已内置) |
| 口播转写漏段 | 音乐/现场音视频 VAD 误杀 → 已用**策略3 两遍自适应**; 仍可能识别错字(LLM 修正版可缓解) |
| GPU 报 cublas 缺失 | 本机 GPU 库不全 → `config.yaml` 固定 `device: cpu`; asr.py 保留 GPU→CPU 自动回退 |
| 字幕进程卡死 | 曾因 GPU 半加载僵死 9h → 已修: 回退逻辑覆盖初始化+转写全程 |
| 中文路径写文件失败 | 原生库(mediapipe/cv2)读中文路径失败 → 视觉管线用 py3.12 ASCII venv |
| Windows 控制台崩溃 | 中文/emoji 打印 GBK 报错 → CLI 已强制 UTF-8 + errors=replace |
| 清单文件 BOM 污染 | PowerShell 写 UTF-8 带 BOM → 用 Python 写无 BOM; 否则首行 URL 带 `\ufeff` |
| 会话过期 | 检测到登录墙 → 标记受阻 + 微信通知"请重新扫码" |

## 数据输出与 schema
```
data/douyin/<19位ID>/
├── video.json       主记录(作者画像/统计/字幕元信息/作者互动聚合)
├── comments.json    评论+回复(扁平, parent_id 建树, is_author/author_replied 标记)
├── subtitles.srt/.txt/.json     口播字幕(原始 ASR, 底稿)
├── subtitles.llm.srt/.txt/.json LLM 修正版(依据文案背景修正专名, 含 [识别不确定] 标记)
└── video.mp4        无水印视频
```
- **字幕两版制**: `subtitles.*` 是 ASR 原始底稿(永不被改写); `subtitles.llm.*` 是 DeepSeek 依据 `video.json` 文案修正的版本。
  研究端若用修正版须知道其含 LLM 推断。
- **ASR 策略3**: 两遍自适应 —— 第1遍 VAD=True, 语音覆盖率 <35% 时自动第2遍 VAD=False 重跑取覆盖更全者
  (音乐/现场音视频 VAD 会误杀语音)。`video.json.subtitles.asr_note` 记录是否触发。
- schema v0.1 字段说明见 `DESIGN.md`; 数字均为采集时点快照(`collected_at` 已记录)。

## 排障
- 命令报"登录过期": 运行 `smfetch login` 重新扫码
- 评论数 0: 检查登录态; 看是否被风控(等待冷却)
- 测试: `python -m pytest tests`(黄金数据, 不碰网络)
