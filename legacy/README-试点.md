# 抖音单视频研究采集工具（可行性试点）

目标：抓取**一条确定视频**的三类数据 —— ①文案 ②口播字幕 ③评论（含回复）。
原则：真实浏览器 + 只读操作 + 小号隔离 + 真人节奏，把封号风险降到最低。

## 工作流

```text
step1_login.py          登录一次 (你扫码小号)
   ↓
step2_scrape.py         抓取 文案 + 元数据 + 评论   → output/json/
   ↓
step3_download_asr.py   下载视频 + Whisper 转写字幕 → output/videos/ + output/subtitles/
```

## 环境要求

- Windows + Python 3.12~3.14（首次请运行 `setup_env.ps1`，需要系统级权限安装依赖）
- 一个**专门的小号**（千万别用日常主号！）
- 手机抖音 App（扫码登录用）

## 使用方法

```powershell
# 0) 首次：装环境（管理员权限运行，或在 DSH 里授权）
powershell -ExecutionPolicy Bypass -File .\setup_env.ps1

# 1) 登录（只做一次）
.\.venv\Scripts\python.exe step1_login.py
#    → 弹出浏览器窗口，用【小号】扫码 → 自动保存登录态

# 2) 抓取（目标视频默认取 dyconfig.py 里的 SHORT_URL）
.\.venv\Scripts\python.exe step2_scrape.py
#    → 若弹滑块验证码，手动滑一下即可；滚动加载评论为真人节奏

# 3) 下载 + 转写
.\.venv\Scripts\python.exe step3_download_asr.py            # 默认 small 模型
.\.venv\Scripts\python.exe step3_download_asr.py --model medium   # 效果更好, 首次要下载模型
```

## 输出目录

```
output/
├── video_id.txt         视频 ID (19位数字, 唯一标识)
├── json/
│   ├── detail.json      文案、作者、点赞/评论/分享数等元数据
│   └── comments.json    全部抓到的评论 (cid 去重, 含回复字段)
├── videos/{id}.mp4      无水印原视频
└── subtitles/
    ├── {id}.srt         标准字幕格式
    ├── {id}.txt         纯文本带时间戳
    └── {id}.json        结构化字幕段
```

## 风险控制（已内置）

- 只读：只滚动/展开，绝不点赞、关注、评论、转发
- 真人节奏：滚动间隔 3~5 秒随机，评论上限 2000 条
- 验证码：出现时脚本等待，你手动滑一下即可；连续无数据会自动停止
- 登录态持久化在 `.profile/`，可随时删除重新登录
- 若需清理登录态：删除 `.profile` 目录即可

## 常见问题

- **弹验证码怎么办**：直接在浏览器窗口手动滑动，脚本会继续等待
- **评论抓不全**：试试点开"查看更多回复"后重跑；或调大 `dyconfig.py` 的 `MAX_SCROLLS`
- **转写不准**：换 `--model medium` 或 `large-v3`（中文效果更好，但更慢）
- **换视频**：修改 `dyconfig.py` 里的 `SHORT_URL`，或 `python step2_scrape.py "https://v.douyin.com/xxx/"`
