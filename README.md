# 辩论系统：国家安全双案例研究

一个 FastAPI + React/Vite 全栈小应用，用两位案例研究者围绕“滴滴数据安全案 vs Manus 案”进行结构化对谈，并在网页中展示、下载 Markdown 结果。

## 成品形态

本地开发：

```bash
./dev.sh
```

打开：

```text
http://127.0.0.1:5173
```

临时公网演示（不用买域名，URL 每次可能变化）：

```bash
./dev.sh --tunnel
```

固定域名公网部署（域名买好并接入 Cloudflare 后）：

```bash
./dev.sh --setup-cloudflare --hostname app.enzoding.net --tunnel-name enzo-amusement-park
./dev.sh --prod --tunnel-name enzo-amusement-park
```

最终访问：

```text
https://app.enzoding.net
```

## 自动化脚本

`dev.sh` 是主入口，尽量不要手动分别启动后端和前端。

```bash
./dev.sh --help
```

支持的模式：

```bash
# 初始化 .env（如果 .env 已存在，不会覆盖）
./dev.sh --init-env

# 本地开发：后端 9000 + Vite 5173
./dev.sh

# 临时公网：Cloudflare Quick Tunnel -> Vite 5173
./dev.sh --tunnel

# 自动创建/配置 Cloudflare 命名 Tunnel（域名必须已在 Cloudflare 账户中）
./dev.sh --setup-cloudflare --hostname app.enzoding.net --tunnel-name enzo-amusement-park

# 生产运行：构建前端，FastAPI 单端口服务前端 + API + WebSocket，再启动命名 Tunnel
./dev.sh --prod --tunnel-name enzo-amusement-park
```

## 环境变量

项目根目录的 `.env` 是运行配置入口，已被 `.gitignore` 忽略，不会提交到仓库。不要把 API Key 写进 `~/.zshrc`，也不要写进 README 或代码。

核心配置：

```bash
API_PROTOCOL=openai
API_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
API_KEY=你的ArkKey
MODEL=ark-code-latest
```

可选语音配置：

```bash
DASHSCOPE_API_KEY=你的DashScopeKey
TTS_MODEL=qwen3-tts-vc-realtime-2026-01-15
TTS_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime
VOICE_ID_JERVIS=可选
VOICE_ID_MEARSHEIMER=可选
```

如果语音 API 欠费或未配置，主站、文字对谈、下载结果仍应正常运行；只是音频播放不可用。

## Cloudflare 和北京网络

当前 Linux 出网已经通过 Mac Clash 代理，适合跑 `cloudflared`。Cloudflare 在国内网络下不保证稳定，但通过代理建立 Tunnel 是最省事的不备案 MVP 方案。

域名购买入口：

[Cloudflare Registrar](https://dash.cloudflare.com/?to=/:account/domains/register)

推荐配置：

- 域名：`enzoding.net`
- 公网子域名：`app.enzoding.net`
- Tunnel 名称：`enzo-amusement-park`
- 本地服务：`http://127.0.0.1:9000`

域名还没购买时，只能完整测试本地开发、生产单端口和 Quick Tunnel；固定域名 DNS 路由要等 `enzoding.net` 加入 Cloudflare 后才能成功。

## 测试命令

后端语法检查：

```bash
python3 -m py_compile backend/app.py backend/debate_runner.py backend/tts_manager.py
```

前端单测：

```bash
cd frontend
npm test
```

前端生产构建：

```bash
cd frontend
npm run build
```

脚本语法检查：

```bash
bash -n dev.sh
```

本地 smoke test：

```bash
./dev.sh
curl -fsS http://127.0.0.1:9000/api/health
curl -fsS http://127.0.0.1:5173/api/health
```

生产单端口 smoke test：

```bash
./dev.sh --prod
curl -fsS http://127.0.0.1:9000/api/health
curl -fsS http://127.0.0.1:9000/
```

## 目录结构

```text
.
├── backend/
│   ├── app.py
│   ├── debate_runner.py
│   ├── models.py
│   ├── requirements.txt
│   └── tts_manager.py
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── docs/
├── .env.example
├── dev.sh
└── README.md
```

## 技术栈

- 后端：FastAPI, Uvicorn, OpenAI SDK, DashScope TTS（可选）
- 前端：React 18, TypeScript, Vite, Vitest
- 部署：Cloudflare Tunnel, 单端口 FastAPI production serving
# 辩论系统：罗伯特·杰维斯 vs 约翰·米尔斯海默

一个全栈小应用，让两位学者（通过蒸馏好的 Skill）围绕《知觉与错误知觉》的核心命题进行 3 轮辩论。你可以在浏览器里一键启动，实时看辩论过程，最后下载完整的 Markdown 记录。

## 目录结构

```
national_security/
├── backend/              # Python FastAPI 后端
│   ├── app.py           # FastAPI 入口
│   ├── debate_runner.py # 辩论流程控制 + LLM 调用
│   ├── models.py        # 数据类型
│   └── requirements.txt # 后端依赖
├── frontend/            # React+Vite 前端
├── .agents/
│   └── skills/          # 女娲蒸馏的两个 Skill
│       ├── robert-jervis-perspective/SKILL.md
│       └── john-mearsheimer-perspective/SKILL.md
├── .env.example         # 环境变量示例
├── prompt.md            # 原始需求
└── README.md            # 本文档
```

## 快速开始

### 1. 安装依赖

**后端**：

（推荐用虚拟环境，避免破坏系统 Python）：
```bash
# 在项目根目录创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate
cd backend
pip install -r requirements.txt
```

如果系统允许你直接装，也可以：
```bash
# cd backend && pip install -r requirements.txt --break-system-packages
```

**前端**：
```bash
cd ../frontend
npm install
```

### 2. 配置 API

本项目**不再硬编码任何 API Key**，请使用环境变量（推荐用项目根目录 `.env` 文件）。\n+\n+1) 复制示例文件：\n+\n+```bash\n+cp .env.example .env\n+```\n+\n+2) 编辑 `.env`，填入你的配置（`.env` 已被 `.gitignore` 忽略，不会提交到仓库）：\n+\n+```bash\n+API_PROTOCOL=openai\n+API_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3\n+API_KEY=你的ArkKey\n+MODEL=ark-code-latest\n+\n+# 可选：阿里云 DashScope 语音（只在你启用音频功能时需要）\n+# DASHSCOPE_API_KEY=你的DashScopeKey\n+# VOICE_ID_JERVIS=\n+# VOICE_ID_MEARSHEIMER=\n+```\n+\n+后端会优先读取 `API_*`，也兼容旧变量名 `ARK_API_KEY/ARK_BASE_URL/ARK_MODEL`。\n*** End Patch"}]} 

### 3. 启动服务

**启动后端**（端口 9000，绑定 0.0.0.0 允许远程访问）：
```bash
# 在项目根目录，确保已经激活虚拟环境
# source .venv/bin/activate
uvicorn backend.app:app --reload --port 9000 --host 0.0.0.0
```

**启动前端**（另开终端）：
```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

### 快捷启动（推荐）

项目自带 `dev.sh` 一键启动脚本，帮你做好这些事情：
```bash
./dev.sh [--tunnel]
```

1. ✅ 自动创建虚拟环境（如果还没有）
2. ✅ 自动安装后端/前端依赖（如果缺失）
3. ✅ **启动前自动杀死占用端口的旧进程**，避免端口冲突
4. ✅ 启动后端 + 前端，输出日志到前台
5. ✅ 检测内网 IP，打印可访问地址
6. ✅ **只有 URL 会绿色高亮**，直接点击就能打开
7. ✅ `Ctrl+C` 一键停止**所有服务**，干净清理不会留僵尸进程

如果要开启公网穿透，加 `--tunnel` 参数：
```bash
./dev.sh --tunnel
```

---

打开浏览器访问 `http://localhost:5173`（本地）或者 `http://你的Linux_IP:5173`（远程 Mac）即可开始辩论。

### 从 Mac Chrome 访问远程 Linux（你的场景）（你的场景）

你的环境：
- **Linux 服务器 IP**：`100.90.186.53`，用户名：`fengde`
- **Mac 客户端**：`100.114.70.79`，和 Linux 在同一tailscale/私有网络

#### 方式一：SSH 端口转发（最简单，不需要公网 IP）

**Linux 端**（在 Linux 上启动服务）：
```bash
./dev.sh
```

**Mac 端**（在你的 Mac 本地终端执行端口转发）：
```bash
ssh -L 5173:localhost:5173 -L 9000:localhost:9000 fengde@100.90.186.53
```

保持这个 SSH 连接打开，然后在**Mac Chrome**访问：
```
http://localhost:5173
```

流量会通过 SSH 隧道加密转发到 Linux，不需要公网 IP，也不需要改防火墙，直接就能用。

---

#### 方式二：Cloudflare 内网穿透（可以从公共互联网任何地方访问）

如果需要从其他网络访问，Linux 上已经装了 `cloudflared` 的话直接启动：
```bash
./dev.sh --tunnel
```

脚本会：
1. 自动杀掉旧端口进程，启动前端+后端
2. 自动启动 cloudflare tunnel 并拿到公开 HTTPS URL
3. 绿色高亮打印出可访问地址，直接在任何浏览器打开就行

---

## 固定域名公网部署（`enzoding.net`，不备案）

你可以用 **Cloudflare Registrar** 购买/托管域名（不需要国内备案），并用 **Cloudflare Tunnel（命名 Tunnel）** 把本机服务安全暴露到公网。\n+\n+推荐 Tunnel 名称：`enzo-amusement-park`。\n+\n+### 1) Cloudflare 买域名\n+\n+- 入口：[Cloudflare Registrar](https://dash.cloudflare.com/?to=/:account/domains/register)\n+\n+### 2) 登录并创建命名 Tunnel（在 Linux 上）\n+\n+```bash\n+cloudflared tunnel login\n+cloudflared tunnel create enzo-amusement-park\n+```\n+\n+创建后会得到一个 Tunnel UUID。你可以用：\n+\n+```bash\n+cloudflared tunnel list\n+```\n+\n+### 3) 绑定子域名到 Tunnel（例如 `app.enzoding.net`）\n+\n+```bash\n+cloudflared tunnel route dns enzo-amusement-park app.enzoding.net\n+```\n+\n+### 4) 创建 `cloudflared` 配置文件\n+\n+在 `~/.cloudflared/config.yml` 写入（注意把 `<TUNNEL-UUID>` 改成你的）：\n+\n+```yaml\n+tunnel: <TUNNEL-UUID>\n+credentials-file: /home/fengde/.cloudflared/<TUNNEL-UUID>.json\n+\n+ingress:\n+  - hostname: app.enzoding.net\n+    service: http://127.0.0.1:9000\n+  - service: http_status:404\n+```\n+\n+### 5) 生产启动（单端口 + 命名 Tunnel）\n+\n+```bash\n+./dev.sh --prod --tunnel-name enzo-amusement-park\n+```\n+\n+说明：\n+\n+- `--prod` 会构建前端并让 FastAPI 服务 `frontend/dist`，整个站点只需后端 `9000` 一个端口。\n+- 命名 Tunnel 不会像 Quick Tunnel 那样每次重启换 URL。\n*** End Patch"}]} 

#### 方式三：直接内网 IP 访问（如果 Mac 和 Linux 在同一个局域网/VPN）

Linux 启动后，Mac 直接访问：
```
http://100.90.186.53:5173
```
就能打开，不用任何额外配置（确保 Linux 防火墙放通 5173 端口就行）。

## 辩论流程

程序严格遵循 3 轮结构：

1. **第一轮**：杰维斯开篇立论 → 米尔斯海默根本批判
2. **第二轮**：杰维斯回应质疑 → 米尔斯海默强化批判
3. **第三轮**：杰维斯总结立场 → 米尔斯海默总结批判

每轮发言控制在 300 字以内。

## 输出

- 辩论过程实时显示在网页上
- 完成后自动保存 `docs/debate_result.md`
- 网页提供「下载 Markdown 记录」按钮

## 技术栈

- 后端：Python 3.8+, FastAPI, Uvicorn, OpenAI SDK
- 前端：React 18 + TypeScript + Vite
- API：兼容 OpenAI 格式的接口（官方 OpenAI、本地模型都可以）

## 替换头像

占位头像是基于首字母的 SVG。如果你有真实照片，替换 `frontend/src/utils/avatars.ts` 里的 SVG 代码换成 `<img>` 引用即可。
