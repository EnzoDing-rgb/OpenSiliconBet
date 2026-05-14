# RISC-V 三国杀 · 指令集 × AI/Agent 时代（互动 Demo）

全栈小应用（FastAPI + React/Vite）：**论坛交锋**（RISC-V / x86 / ARM 三阵营 + Lex 主持 + 黄仁勋环节 + 观众问答），用于中科院中关村·公众科学日分会场。**不做胜负式辩论**；旧「双案例对谈 / debate」栈已迁入归档，代码仍在按 [`docs/design/implementation.md`](docs/design/implementation.md) 向 v2 迁移。

总览与 Cursor plan：[`.cursor/plans/risc-v_三国杀_demo_设计_bbe2bf8e.plan.md`](.cursor/plans/risc-v_三国杀_demo_设计_bbe2bf8e.plan.md)

## Codename 候选（仓库名暂不改）

| 候选 | 含义 | 备注 |
|------|------|------|
| **OpenSiliconBet** | 押注开源硅 | 当前主推 |
| **AgentSiliconBet** | 押注 Agent 硅 | 强调 Agent 时代 |
| **第四架构 / fourth-arch** | x86 / ARM / POWER 之外的第四种 | 偏史诗叙事 |

## 文档索引（`docs/`）

| 目录 | 内容 |
|------|------|
| [`docs/background/`](docs/background/) | 共享事实 [`deep-research.md`](docs/background/deep-research.md)、Lex 台本 [`lex-opening-script.md`](docs/background/lex-opening-script.md) |
| [`docs/characters/`](docs/characters/) | 五嘉宾 perspective SKILL |
| [`docs/design/`](docs/design/) | [**architecture.md**](docs/design/architecture.md) 宪章 · [**implementation.md**](docs/design/implementation.md) 计划+测试 · [**realtime-tts-architecture.md**](docs/design/realtime-tts-architecture.md) 实时 TTS |
| `docs/_archieved_mds/` | 历史草稿与旧栈说明（**不在 README 维护**） |

## 本地运行

```bash
./dev.sh
```

浏览器：`http://127.0.0.1:5173`（前端）+ `http://127.0.0.1:9000`（后端 API，由脚本一并拉起）。

远程机开发时，可在本机做 SSH 转发：`ssh -L 5173:localhost:5173 -L 9000:localhost:9000 user@host`，再在本地浏览器打开 `http://localhost:5173`。

临时公网：

```bash
./dev.sh --tunnel
```

固定域名 + 生产单端口（示例）：

```bash
./dev.sh --setup-cloudflare --hostname app.enzoding.net --tunnel-name enzo-amusement-park
./dev.sh --prod --tunnel-name enzo-amusement-park
```

脚本说明：`./dev.sh --help`

## 环境变量

项目根 `.env`（已 `.gitignore`），勿把 Key 写进 README。

```bash
API_PROTOCOL=openai
API_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
API_KEY=你的ArkKey
MODEL=ark-code-latest
```

可选 TTS（DashScope）：根目录 `.env` 配 **`DASHSCOPE_API_KEY`**、**`TTS_MODEL`**（默认 `qwen3-tts-vc-realtime-2026-01-15`）、五辩手 **`VOICE_ID_LEX` / `VOICE_ID_WUWEI` / `VOICE_ID_LIPTAN` / `VOICE_ID_COOK` / `VOICE_ID_JENSEN`**（未填则回退 `VOICE_ID_DEFAULT` → `MEARSHEIMER` → `JERVIS`）。音频放 `assets/` 后一键复刻：`python3 scripts/enroll_voices.py`。详见 [`docs/design/architecture.md`](docs/design/architecture.md)、[`docs/design/realtime-tts-architecture.md`](docs/design/realtime-tts-architecture.md)、[`.env.example`](.env.example)。

## Cloudflare 与北京网络

经代理跑 `cloudflared` 做 Tunnel 为不备案 MVP 常见做法；域名、Tunnel 名等示例仍可用你文档里既有 hostname。**国内链路不保证稳定**，以实际环境为准。

## 测试与 smoke

```bash
python3 -m py_compile backend/app.py backend/debate_runner.py backend/tts_manager.py
cd frontend && npm test && npm run build
bash -n dev.sh
```

```bash
./dev.sh
curl -fsS http://127.0.0.1:9000/api/health
```

更完整的阶段单测与省钱策略见 [`docs/design/implementation.md`](docs/design/implementation.md) 第二部分。

## 目录结构（摘要）

```text
.
├── backend/           # FastAPI、编排（debate_runner 等为历史文件名，职责转向论坛 Director）
├── frontend/          # React + Vite
├── docs/
│   ├── background/
│   ├── characters/
│   ├── design/
│   └── _archieved_mds/
├── .env.example
├── dev.sh
└── README.md
```

## 技术栈

- 后端：FastAPI, Uvicorn, OpenAI SDK, DashScope TTS（可选）, WebSocket
- 前端：React 18, TypeScript, Vite, Vitest
- 部署：Cloudflare Tunnel；生产可由 FastAPI 单端口托管 `frontend/dist`

## 头像

占位头像在 `frontend/src/utils/avatars.ts`；可改为 `<img>` 引用真实照片。
