# 项目架构与可改造点（current state）

> **归档（2026-05）**：本文件从旧 `docs/architecture.md` 迁入 `_archieved_mds/`，保留滴滴/Manus 双人栈细节。当前 RISC-V 三国杀：**宪章**见 [`../design/architecture.md`](../design/architecture.md)；**计划 + 测试**见 [`../design/implementation.md`](../design/implementation.md)；仓库根 `README` 与 Cursor plan `risc-v_三国杀_demo_设计_bbe2bf8e.plan.md`。国关学者 Skill 等历史入口亦在本归档目录。

> 写这份文档的目的：在你把 demo 从「滴滴 vs Manus 国家安全案」改造成「RISC-V vs x86 vs ARM 科普」之前，先把当前系统在做什么、由哪些文件支撑、哪些是**硬编码的角色绑定点**讲清楚。改造时只动这些点即可，不需要重写架构。

---

## 1. 一句话定位

一个「**蒸馏好的人物 Skill × 多轮自动对谈 × 文字/语音双通道实时播放**」的全栈小应用：

- 后端按预设的 **6 个 turn（3 轮）** 顺序，让两个角色各自基于自己的 SKILL.md 调 LLM 生成发言；
- 前端以**轮询 + WebSocket 流式音频**的方式实时显示文字 + 播报语音；
- 对谈结束后再调一次 LLM 生成「对比小结」，并允许用户进入「与研究者对话」模式追问。

整个系统在 `./dev.sh` 一键起的本地双进程，或 `./dev.sh --prod` 单端口生产模式下运行；可选挂 Cloudflare Tunnel 走公网。

---

## 2. 拓扑与运行形态

```
┌─────────────────────────────┐         REST (polling 1.5s)
│  Browser (React + Vite)     │ ───────────────────────────────► /api/debate/{start,status,result,chat}
│                             │
│  - App.tsx (state machine)  │ ◄──────── WebSocket (binary PCM) ─── /ws/debate-audio?run_id=...
│  - DebateAudio (PCM player) │
│  - MasterChat (drawer)      │
└─────────────────────────────┘
                                                  ▲
                                                  │
                                        ┌─────────┴──────────┐
                                        │  FastAPI (9000)    │
                                        │                    │
                                        │  app.py  ─────────►│ HTTP/WS endpoints
                                        │  debate_runner.py ►│ LLM 调用 + Skill 注入 + 6 turn 顺序
                                        │  tts_manager.py  ──►│ DashScope Realtime TTS proxy
                                        │  models.py         │ Pydantic schemas
                                        └─────────┬──────────┘
                                                  │
                              ┌───────────────────┼─────────────────────┐
                              ▼                   ▼                     ▼
                  火山方舟 / 本地 Qwen      DashScope TTS WS     docs/*-SKILL.md
                  (OpenAI-compatible)     (PCM 24k mono)       (角色蒸馏 prompt)
```

两条独立信道：
- **文字**：`POST /api/debate/start` 返回 `run_id`，前端按 `run_id` 轮询 `/api/debate/status/{run_id}`，把累积的 `turns[]` 渲染成时间线。
- **语音**：前端拿到 `run_id` 后直接开 `wss://.../ws/debate-audio?run_id=...`，后端按 `turns` 数组逐段做 TTS，二进制 PCM 直接 push 到浏览器 WebAudio 播放；文字早走音频后追，二者用 `DISPLAY_DELAY_SECONDS_PER_TURN = 7.0` 软同步。

---

## 3. 关键文件与职责

### 3.1 后端 `backend/`

| 文件 | 行数级 | 干什么 |
|---|---|---|
| `app.py` | ~146 | FastAPI 入口；注册 5 个 REST + 1 个 WebSocket；生产模式下 mount 前端 `dist/` 当静态站。 |
| `debate_runner.py` | ~704 | 单例 `DebateRunner`：读 SKILL → 拼 system prompt → 顺序跑 6 turn → 落盘 `docs/_archieved_mds/debate_result.md` → `chat_with_debater` 实现共享会场追问。 |
| `tts_manager.py` | ~382 | DashScope Realtime TTS 代理：`TextChunker` 流式切片 → `QwenTtsRealtime` WebSocket → 把 `response.audio.delta` (base64 PCM) 解码后转发到浏览器；带 ack 流控避免抢拍。 |
| `models.py` | ~53 | 数据契约：`Speaker`(枚举 `JERVIS / MEARSHEIMER`)、`Turn`、`ChatMessage`、`DebateRun`、API 返回结构。 |
| `requirements.txt` | 10 | `fastapi / uvicorn / openai / anthropic / dotenv / pydantic / dashscope / ...` |

### 3.2 前端 `frontend/src/`

| 文件 | 干什么 |
|---|---|
| `App.tsx` | 状态机：`runId / status / turns / judgeResult / chatOpen / audioEnabled`；`handleStart` 触发后端，`useEffect` 起 1.5s 轮询；渲染头像卡 + 时间线 + 对比小结 + 抽屉式 MasterChat。 |
| `api.ts` | 4 个 fetch 包装 + `downloadMarkdown` blob 下载。 |
| `types.ts` | TypeScript 镜像 backend Pydantic（`Speaker / Turn / ChatMessage / *Response`）。 |
| `components/RoleCard.tsx` | 头像卡片（左右两侧，accent 色描边）。 |
| `components/TurnMessage.tsx` | 单条发言气泡，渲染 markdown。 |
| `components/MasterChat.tsx` | 抽屉式追问面板：tab 切换 speaker → `postChat` → 共享 `chat_history`。 |
| `components/DebateAudio.tsx` | WebSocket 客户端：收 `meta / phase / turn_done / all_done`，二进制送 `PcmPlayer`；带暂停/继续按钮和 ack 节流。 |
| `audio/pcmPlayer.ts` | 24kHz 单声道 16-bit LE PCM → Float32 队列 → `ScriptProcessorNode` 输出，最多 buffer 30 秒。 |
| `utils/avatars.ts` | **角色元数据集中点**：`speakerMeta[Speaker]` = `{ nameZh, subtitleZh, avatarSrc, accent }`。 |
| `utils/markdownRender.ts` | 自研最小 markdown→HTML（粗体/标题/列表/换行），带 XSS escape。 |
| `utils/ttsPhaseUi.ts` | 把 `connecting / generating / playing / completed / waiting_content` 翻译成中文 UI 提示。 |

### 3.3 Skill 与素材

| 路径 | 说明 |
|---|---|
| `docs/didi-case-research-SKILL.md` | 通过 symlink 指向 `.agents/skills/didi-case-research/SKILL.md`（**当前演的是滴滴**）。 |
| `docs/manus-case-research-SKILL.md` | 通过 symlink 指向 `.agents/skills/manus-case-research/SKILL.md`（**当前演的是 Manus**）。 |
| `docs/john-mearsheimer-perspective-SKILL.md` / `docs/robert-jervis-perspective-SKILL.md` | 早期版本留下的国关学者 Skill（链接还在，但已不再被加载，见下面 §4）。 |
| `assets/Jervis*.mp3 / Mearsheimer*.mp3` | 音色样本（用于先前 voice clone 的参考；运行时不直接读取）。 |
| `frontend/src/assets/jervis.png / mearsheimer.png` | 头像图（**还是国关学者的脸**，待你换成 RISC-V/x86/ARM 代表的肖像）。 |

---

## 4. 核心数据流（一次完整对谈）

1. 用户点「开始对谈」 → `POST /api/debate/start` → `runner.create_new_run()` 生成 `run_id` → 后台任务 `runner.run_debate(run_id)` 起跑。
2. `run_debate` 按 `DIALOGUE_TURNS`（在 `debate_runner.py` 第 150–190 行硬编码）依次执行 6 个 turn：
   - 拼 `system_prompt = 角色前缀 + SKILL 全文`；
   - 拼 `user_prompt = 该轮基础指令 + 对手上一轮原文（_interaction_wrapper）`；
   - 调 `_call_llm`（OpenAI 协议，火山方舟 `ark-code-latest`；429/配额耗尽自动 fallback 到 `LLM_FALLBACK_*` 指向的本地 Qwen3.5）；
   - `_clean_model_output` 把模型自带的「免责声明 / 我以XX视角...」之类样板话剥掉；
   - 第 1、2 turn 自动加 `【我是 XXX Researcher】` 前缀（强制自报家门）；
   - `await asyncio.sleep(7.0)` 让 UI 不超前于音频。
3. 前端轮询 `/api/debate/status/{run_id}` 每 1.5s 拉一次累积 `turns[]`，新加的 turn 直接 append 到时间线。
4. 同时 `DebateAudio` 已经开了 WebSocket：
   - 后端 `tts_manager.handle_connection` while 循环看 `len(run.turns)` 是否多了一段，多了就开 `TtsSession` 走 DashScope 流式 → 浏览器；
   - 浏览器收到 `turn_done` 后等 `PcmPlayer.getBufferedMs() < 120` 才发 `ack_turn_done`，后端才推下一段（防止字音错位）。
5. 6 个 turn 跑完，`run.status = DONE` → `_save_result` 再调一次 LLM 生成「对比小结」（system prompt 在 `_judge_system_prompt`）→ 写 `docs/_archieved_mds/debate_result.md` 并把 `judge_result` 挂到 `run` 对象上 → 前端轮询拿到后渲染「对比小结」面板。
6. 用户随时可以点「与研究者对话」抽屉，`POST /api/debate/chat/{run_id}` → `chat_with_debater` 把整场 6 turn + 历史所有 chat 当 context 一起送回模型，实现「共享会场可追问」。

---

## 5. 角色硬编码点（**改造时只看这一节**）

这个项目从「国关学者辩论」演化到「双案例研究对谈」时，**没有彻底重命名**。Speaker 枚举的 key 还是 `JERVIS / MEARSHEIMER`（杰维斯/米尔斯海默），但显示名已经改成「滴滴 Researcher / Manus Researcher」。要把它改成 **三方 RISC-V / x86 / ARM 科普对谈**，要动的点全在下面这张表里：

| 改造维度 | 文件 | 当前内容 | 改造方向 |
|---|---|---|---|
| **Speaker 枚举（最底层）** | `backend/models.py` L12-15 | `JERVIS / MEARSHEIMER`（两方） | 改成 `RISCV / X86 / ARM`（三方），**注意全栈 grep 替换**。 |
| **TS 镜像** | `frontend/src/types.ts` L1 | `"jervis" \| "mearsheimer"` | 同步成三方 union。 |
| **Skill 文件路径** | `debate_runner.py` L76-77 | `docs/didi-case-research-SKILL.md` / `docs/manus-case-research-SKILL.md`（**symlink 到 .agents/skills/**） | 新增三个 Skill：David Patterson（RISC-V 代表）、x86 代表（建议 **Pat Gelsinger** / 或 Linus Torvalds 这种持有 strong x86 view 的工程视角）、ARM 代表（建议 **Hermann Hauser** 联合创始人 或 **Rene Haas** 现任 CEO）。先用「女娲蒸馏」skill 一键生成。 |
| **对谈话题** | `debate_runner.py` L80 `DEBATE_TOPIC` | "滴滴数据安全案 vs Manus案：……" | 改成 "RISC-V vs x86 vs ARM：开放指令集 / 性能霸权 / 移动生态在 2026 的三国杀"。 |
| **Turn 序列** | `debate_runner.py` L150-190 `DIALOGUE_TURNS` | 6 个 turn（2 角色 × 3 轮），每个 turn 文案都引用「Manus / 滴滴」 | 三角对谈建议改成 **3 角色 × 3 轮 = 9 turn**，或保留 6 turn 但每轮三人各发一次。文案里「研究者」改「布道者 / 工程师」，案例话题改成「指令集开放性 / 制造工艺 / 终端生态 / 资本流动」等。 |
| **角色中文名 + 提示语** | `debate_runner.py` L93-94 `_speaker_zh` | `"滴滴 Researcher" / "Manus Researcher"` | 改成 `"RISC-V · 大卫·帕特森"` / `"x86 · 帕特·盖尔辛格"` / `"ARM · 雷内·哈斯"`。 |
| **强制自报家门前缀** | `debate_runner.py` L366-369 `if i == 1 / i == 2` | `【我是 Manus Researcher】 / 【我是 滴滴 Researcher】` | 三方时改成按 `speaker` 动态注入，不要再用 `i==1/i==2`。 |
| **共享会场上下文** | `debate_runner.py` L616-622 first_turn_user_context | "你在与一位中国的国家安全学方向博士生进行学术讨论..." | 改成 "你在面向一群对芯片产业感兴趣的中国大学生 / 投资者讲解..."；增加「带数据可视化、可结合实时股价」的引导。 |
| **对比小结模板** | `debate_runner.py` L213-227 `_judge_user_prompt` | "相同点 / 不同点 / 关键争点 / 研究议程" | 三方对比可改成「**架构哲学差异 / 性能-功耗 trade-off / 生态壁垒 / 5 年预测**」；也可以加一栏「**给散户的一句话总结**」。 |
| **角色元数据（前端）** | `frontend/src/utils/avatars.ts` | 两个 entry：`jervis(蓝) / mearsheimer(红)`，引用 `assets/jervis.png / mearsheimer.png` | 三个 entry：`riscv(绿) / x86(蓝) / arm(紫)`，换头像图。Patterson 真人照、Gelsinger 真人照、Haas 真人照 + 各自 Logo 备选。 |
| **App.tsx 顶部文案** | `App.tsx` L88-91 | "国家安全案例研究对谈 / 滴滴数据安全案 vs Manus案" | "RISC-V vs x86 vs ARM：2026 芯片三国杀" 等。 |
| **RoleCard 渲染** | `App.tsx` L94-109 | 写死两个 `<RoleCard>` | 改成 `Object.entries(speakerMeta).map(...)`。 |
| **MasterChat tab** | `MasterChat.tsx` L70-83 | 写死两个 button | 同样改 map。 |
| **DebateAudio 类型** | `DebateAudio.tsx` L7,18,25,29-33 | `'jervis' \| 'mearsheimer'` 联合类型 | 改成 `Speaker` 三方联合，并改 `speakerZh` 函数。 |
| **TTS 音色** | 环境变量 `VOICE_ID_JERVIS / VOICE_ID_MEARSHEIMER` + `tts_manager.py` L121-125 `_get_voice_id` | 两个 voice id 写死分支 | 加 `VOICE_ID_RISCV / VOICE_ID_X86 / VOICE_ID_ARM`，把 `_get_voice_id` 改成查表（Dict）。需要重新做 voice clone（DashScope CosyVoice）；不做 voice clone 时退化到默认音色也能跑。 |
| **TTS 触发条件** | `app.py` L25-26 | `if api_key and voice_jervis and voice_mearsheimer` | 改成 `if api_key and all_voice_ids_present`。 |

---

## 6. 接口契约（**改造时不需要动**）

这些是「角色无关」的稳定面，改三方对谈时可以原样保留：

```
POST   /api/debate/start                     →  { run_id }
GET    /api/debate/status/{run_id}           →  { status, current_round, turns[], judge_result?, error? }
POST   /api/debate/chat/{run_id}             →  { reply, chat_history[] }
GET    /api/debate/result/{run_id}           →  { content }   # markdown 全文
GET    /api/health                           →  { status: "ok" }
WS     /ws/debate-audio?run_id=...&test=0|1
        client → { type:"start" }
        server → { type:"meta", format, speaker, round, turn_index }
        server → <ArrayBuffer PCM>
        server → { type:"phase", phase:"connecting|generating|playing|completed|waiting_content", ... }
        server → { type:"turn_done", speaker, round, turn_index }
        client → { type:"ack_turn_done", turn_index }
        server → { type:"all_done" }
        server → { type:"error", message }
```

---

## 7. 配置入口

所有 secrets 走 `.env`（已 gitignore）。变量名：

```ini
# 主链路（必须）
API_PROTOCOL=openai          # 也支持 anthropic
API_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
API_KEY=ark-...
MODEL=ark-code-latest

# 限流时本地后备（可选；走家里 ssh 隧道到校园网 Qwen3.5）
LLM_FALLBACK_BASE_URL=http://127.0.0.1:30023/v1
LLM_FALLBACK_API_KEY=my-local-secret-key
LLM_FALLBACK_MODEL=qwen3.5

# 语音（可选；缺了文字流仍正常）
DASHSCOPE_API_KEY=...
VOICE_ID_JERVIS=...
VOICE_ID_MEARSHEIMER=...
TTS_MODEL=qwen3-tts-vc-realtime-2026-01-15
TTS_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime

# 改用其他 Skill 文件路径（默认走 docs/*-SKILL.md symlink）
DIDI_SKILL_PATH=...
MANUS_SKILL_PATH=...
```

`debate_runner.py` 里 LLM 限流时的 fallback 逻辑（`_openai_chat_with_quota_fallback`，第 400 行附近）会在火山方舟返回 `429 / AccountQuotaExceeded` 时**整场切到本地后备**，下半场不会再回切——这点对演示稳定性很关键，改造时保持不动。

---

## 8. 已知约束与可演化方向

**当前约束（demo 级）**：
- `runs: Dict[str, DebateRun]` 是**进程内字典**，重启即丢；多进程部署会丢 run 状态。
- WebSocket 一个 `run_id` 同一时间只允许一路播放（`_active_run_audio` 计数），多 tab 会被拒。
- 没有持久化数据库，只有 `docs/_archieved_mds/debate_result.md` 这一份 last-write-wins。
- `runner` 是**模块级单例**，自然限定单实例部署。

**为「RISC-V 科普 + 互动 + 实时」要做的演化**（这一节是给后面讨论用的钩子，不是承诺）：
1. **三方对谈**：Speaker 枚举三态化，`DIALOGUE_TURNS` 重排成 3×3 = 9 turn 或 3×2=6 turn（每轮三人各一发言）。
2. **股价联动 / 实时数据 widget**：新增 `/api/market/snapshot?tickers=ARM,INTC,AMD,QCOM,NVDA,...`，前端 `App.tsx` 顶上一行实时报价条；Skill 在 `_call_llm` 前可以把最新报价当 context 注进去（"今天 ARM 涨 X%，请把这个事实纳入你的论证"），实现「**让大牛实时点评盘面**」。数据源建议：
   - 美股：Alpha Vantage / Yahoo Finance Chart API / Polygon.io（免费层够 demo）；
   - 港股 RISC-V 概念：东方财富/雪球非官方接口；
   - **每次对谈开局先抓一次快照固化进 system prompt**，避免对谈过程中模型被实时数据反复打断。
3. **互动性**：把「与研究者对话」从抽屉默认打开，加 quick-reply chips（"那中国国产 RISC-V 厂商呢？" / "Apple Silicon 算 ARM 吗？" / "下一个 Intel 是谁？"）。
4. **可视化**：在「对比小结」面板加一张 D3 / Recharts 雷达图（开放性 / 性能 / 生态 / 软件栈成熟度 / 市值），数值由 LLM 在 judge 步骤里输出 JSON。
5. **实时性**：把 6 turn 顺序改成**streaming token-by-token**（OpenAI `stream=True`）写到 SSE 通道，前端 typewriter 渲染——这步会让酷度提升一个数量级，但要重写 `run_debate` 的循环和前端的轮询为 SSE。

---

## 9. 一行总结

> **当前是一个用 SKILL.md 注入角色 + 6 turn 顺序自动跑 + 文字轮询 + 音频流式的双方对谈 demo；要改成 RISC-V 科普版，主要工作量在「Speaker 枚举三态化 + Skill 蒸馏 3 个新角色 + 文案/头像/音色替换」，架构本身不需要重写。**
