# smfetch v1 — 抖音数据采集工具

安全优先的抖音数据采集: **文案 / 评论(含楼中楼与作者回复) / 视频 / 口播字幕**。
支持批量无人值守 + 微信通知。设计文档见 `DESIGN.md`。

## 快速开始

```powershell
# 1) 登录 (只需一次, 用【小号】扫码)
cd D:\zhy\抖音\v1\tool1-collect
D:\zhy\抖音\.venv\Scripts\python.exe -m smfetch login

# 2) 抓单条 (文案 + 评论 + 字幕, 默认全开)
... -m smfetch fetch https://v.douyin.com/xxxxx/
#    字幕默认转写; 只要评论可加 --no-subtitle

# 3) 批量无人值守 (同样默认评论+字幕)
... -m smfetch batch urls.txt
... -m smfetch status

# 5) 导出
... -m smfetch export --format csv
```

## 命令一览

| 命令 | 说明 |
|---|---|
| `login` | 扫码登录(小号), 保存到 `../../.profile` |
| `fetch <目标> [--no-subtitle] [--no-comments] [--video] [--no-video] [--model M] [--device D] [--force]` | 抓单条(默认评论+字幕) |

> 只要视频文件: `fetch <ID> --no-comments --no-subtitle --video`
> (视频下载与字幕转写已解耦; 不传 `--video/--no-video` 时沿用旧行为=跟随字幕开关)
| `batch <清单> [--per-day N] [--reset] [--force] [--no-notify] [--pause] [--dry-run]` | 批量 |
| `status` | 队列进度/受阻清单 |
| `export [--format csv\|json] [--scope all\|videos\|comments]` | 导出 |
| `config --show` | 查看生效配置 |

## 配置 (config.yaml)

节奏(防封)/单日限额/转写模型/通知渠道全在配置文件, 命令行只管"做什么"。

## 安全约定 (必读)

1. **只读**: 工具绝不点赞/关注/评论/转发
2. **小号**: 登录只用小号, 别用主号
3. **节奏**: 慢即是快; 默认 2000 条上限、25 轮/次、6-12 秒间隔
4. **验证码**: 弹出时人工滑一下; 卡住会自动停止并(批量时)微信通知
5. **合规**: 只采公开数据; 评论含个人信息, 研究注意去标识化

## 测试

```powershell
cd D:\zhy\抖音\v1\tool1-collect
D:\zhy\抖音\.venv\Scripts\python.exe -m pytest tests
```
黄金数据测试基于真实抖音数据, 不碰网络。

## 输出目录

```
data/douyin/<视频ID>/
├── video.json        主记录
├── comments.json     评论+回复
├── subtitles.*       口播字幕
└── video.mp4         无水印视频
```
