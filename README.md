# mdbeacon-lab

Markdown 像素信标（pixel beacon）数据外传的最小可复现靶场。配套文章：《[原创] 不可信的模型输出：从 Markdown 像素信标看 LLM 输出安全》。

一句话：聊天 UI 把模型回复渲染成 Markdown 并自动加载 `<img>`，攻击者只要在会被检索进上下文的文档里埋一行隐藏指令，就能让模型把用户上一轮说过的秘密写进图片 URL 的 query string，浏览器一加载就送到攻击者日志。

## 组成

| 文件 | 职责 |
|------|------|
| `log_server.py` | 攻击者日志服务。`/p.png` 返回 1x1 透明 PNG，所有请求落 `exfil.log`，命中时打横幅。端口 8090。 |
| `index.html` | 脆弱聊天 UI。`marked` + `DOMPurify` 渲染，`<img>` 自动加载，带"注入文档"按钮一键复现。 |
| `index_csp.html` | CSP 防御版。同上 + `img-src 'self'`，用于对照实验。 |
| `payload.md` | 载体文档。周报外壳 + HTML 注释里的注入指令。 |
| `drive_demo.py` | CDP 驱动：自启 Chrome，跑 Turn1/Turn2，`Page.captureScreenshot` 落盘。 |
| `drive_csp.py` | CSP 对照的 CDP 驱动。 |
| `shoot_pages.py` | 截 `exfil.log` 渲染页与解码页。 |
| `show_log.html` / `show_decode.html` | 把 `exfil.log` 渲染成终端样式 / 解码回放，便于截图。 |
| `run_demo.ps1` / `shoot.ps1` | 一键编排脚本。 |
| `test_*.py` | 模型服从性排查脚本（3B/7B 对 base64、邮箱脱敏、占位顶替的实测记录）。 |

## 复现

```powershell
# 1. 拉模型（3B 不可靠，建议 7B；约 4.7GB）
ollama pull qwen2.5:7b

# 2. 起攻击者日志服务（端口 8090；8080 常被 Burp 占用）
py -3 log_server.py

# 3. 另开终端，起 UI 静态服务（端口 8091；用 http 而非 file，否则 Ollama CORS 拒 null origin）
py -3 -m http.server 8091

# 4. 浏览器打开 UI，手动复现
#    http://127.0.0.1:8091/index.html
#    Turn 1: 输入「我的邮箱是 victim@example.com，帮我记一下」回车
#    Turn 2: 点「注入文档（Turn 2 载体）」再点「发送」
#    观察 exfil.log 出现 GET /p.png?d=victim@example.com

# 5. 一键自动复现 + 截图（自启 Chrome，CDP 落盘）
py -3 drive_demo.py        # 脆弱版
py -3 shoot_pages.py       # 日志 / 解码截图
py -3 drive_csp.py         # CSP 对照
```

## 两个真实坑

- **端口 8080 被本机 Burp Suite 占用** → 信标改 8090。
- **`file://` 的 null origin 被 Ollama CORS 403** → UI 起在 `http.server 8091`。

## 模型能力是可靠性瓶颈

`qwen2.5:3b` 在这条链路上不可靠：base64 乱编、邮箱脱敏成 `****@alibaba-inc.com`、拿 `example@example.com` 顶替、加 system prompt 直接拒。`qwen2.5:7b` 同样算不动 base64，但**原样回填邮箱**这一步稳。所以演示用 `?d=` 原样回传（信道对编码中立），解码页再补 base64url 概念对照。

结论：像素信标攻击的可靠性瓶颈在"编码"这一步，不在信道。想让载荷在日志里不显眼，要么换更强模型，要么把编码挪到 UI 侧（注入指令触发一段 JS）。信道本身对编码形式中立。

## 合规声明

本实验在本地自建 UI + 本地模型 + 本机日志服务完成，未对任何第三方 SaaS 聊天产品做未授权测试。文中邮箱 `victim@example.com` 为合成数据。
