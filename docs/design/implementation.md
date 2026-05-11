# RISC-V 三国杀 · 实施计划与测试规格

> **本文档角色**：仓库内 **计划与测试合一**（进 git 的 Canonical）。与 Cursor plan `risc-v_三国杀_demo_设计_bbe2bf8e.plan.md` **内容应对齐**（改其一请同步另一）。**架构宪章**：[./architecture.md](./architecture.md)。  
> **下半部**：Coding Agent / CI 用的 **测试分层、阶段验收清单、省钱跑法**。

---

## 1. 执行摘要（与 Plan overview 一致）

- 滴滴/Manus demo 改为「RISC-V vs x86 vs ARM」**论坛交锋**（非胜负辩论；中科院公众科学日分会场）。Lex + 吴伟/陈立武/库克 + 黄仁勋；阶段 3 五人常显。
- **架构钉死**：实现以 [./architecture.md](./architecture.md) 为准（阶段机 `0→0.5→1→2→2.5→3`、三级 baton、回合级 TTS）。
- **阶段 1 收口**：三嘉宾各 **2** 段 → **共 6** 条 guest turn → 立即进阶段 2。
- **阶段 2.5（必选）**：黄仁勋独白播完后 Lex 固定句：「好，观众朋友们，我们现在进入观众提问环节。」再开阶段 3；不可叠播、不可省略。
- **Baton**：`@` → **NextSpeakerSelector**（隐式挑衅）→ **LRS**；不用 Lex 点名接棒。
- **TTS**：SSE 文本可流式；**禁止**半句切块喂 TTS；整轮完稿后整段合成 + **播放锁**（`onended` / `audio_finished`）。
- **音色**：独立克隆就绪前 **五键可同一 `VOICE_ID_DEFAULT` / `VOICE_ID_MEARSHEIMER`**，`tts_manager` 按 `lex|wuwei|liptan|cook|jensen` 查表。
- **现状**：`Speaker` 五枚举 + 论坛 6 段 `DIALOGUE_TURNS` + `baton` eligible pool 已接线；**v2 Director / 0.5 / 2.5** 仍待实现。

### 1.1 与 Cursor Plan 同步的 TODO 清单

| 状态 | 项 |
|------|-----|
| 已完成 | [`../background/deep-research.md`](../background/deep-research.md) 留白已填 + **事实口径总注**（编辑用） |
| 已完成 | [`../characters/wuwei-riscv-perspective-SKILL.md`](../characters/wuwei-riscv-perspective-SKILL.md)（可持续迭代） |
| 已完成 | [`../characters/liptan-x86-perspective-SKILL.md`](../characters/liptan-x86-perspective-SKILL.md) |
| 已完成 | [`../characters/timcook-arm-perspective-SKILL.md`](../characters/timcook-arm-perspective-SKILL.md) |
| 已完成 | [`../characters/jensen-huang-perspective-SKILL.md`](../characters/jensen-huang-perspective-SKILL.md) |
| 已完成 | [`../characters/lex-fridman-host-perspective-SKILL.md`](../characters/lex-fridman-host-perspective-SKILL.md) |
| 已完成 | [./architecture.md](./architecture.md)（宪章） |
| 已完成 | [`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md)（阶段 2 **必注弹药**；见 §4 B、§6 **D.6b**） |
| 待办 | `backend/free_qa.py` + `FreeQAPanel`；Summary + Intent；五人窗 |
| 待办 | `scripts/pregen_lex_opening.py` + `public/audio` 两 mp3 + `OpeningPlayer.tsx` |
| 已完成 | Speaker 五枚举；`models` / `types` / `DebateAudio` / `tts_manager` / `baton` eligible pool + pytest |
| 待办 | `debate_runner`：v2 Director；6 guest turns 收口；2.5 Lex 转场；baton + D.0 |
| 待办 | `avatars`、顶栏、阶段 2 CSS、`SpeakerWindow`、当前说话人高亮 |
| 待办 | smoke：OpeningPlayer + Director + free_qa + 回合级 TTS；可选 browser |

---

## 2. 仓库快照（相对本计划）

| 类别 | 现状 |
|------|------|
| 事实底盘 | [`../background/deep-research.md`](../background/deep-research.md) 已在仓：§1–§7 骨架 + 留白 |
| 五嘉宾 SKILL | [`../characters/`](../characters/) 下 lex / wuwei / liptan / timcook / jensen 五文件 **已在仓** |
| Lex 0.5 文案 | [`../background/lex-opening-script.md`](../background/lex-opening-script.md) **已在仓**（含阶段 2.5 转场句） |
| V2 架构蓝图 | [./architecture.md](./architecture.md) **已在仓** |
| 架构入口 | 本目录 `design/`；旧双人长文 → [`../_archieved_mds/architecture-legacy-didi-manus.md`](../_archieved_mds/architecture-legacy-didi-manus.md) |
| Jensen 弹药 | [`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md) — 阶段 2 **强制**并入 prompt（已在仓） |
| 仍缺实现 | `scripts/pregen_lex_opening.py`、两轨 mp3、`OpeningPlayer.tsx`、`free_qa.py`、`FreeQAPanel.tsx`、`SpeakerWindow.tsx`、五 speaker + v2 Director + 三级 baton + 回合级 TTS |
| 运行栈 | `app.py` + `tts_manager.py`：`VOICE_ID_{LEX,WUWEI,...}` 或 **`VOICE_ID_DEFAULT` / `VOICE_ID_MEARSHEIMER`** 全员回退 |

---

## 3. A. 目标

| 项 | 内容 |
|----|------|
| 主题 | 指令集 · RISC-V vs x86 vs ARM，开放探讨 |
| UI | 顶栏 + `<title>` + banner：**RISC-V 三国杀**；副标题：公众科学日分会场 |
| 受众 | 老师 + 中学生（不降智） |
| 形式 | Lex 极简 → **0.5 预录**（可跳过）→ **论坛交锋**（每人 2 段共 6 段）→ Lex **主持引介** → **视频连线**（CSS 视窗）→ 黄独白 → **Lex 2.5 转场** → 主屏 chat → Lex 收束 |
| 知识轴 | RISC-V 能否替代 x86/ARM；Agent 窗口；1–3 年走向 |

---

## 4. B. 五人

全员中文；人设见 [`../characters/`](../characters/)。0.5 预录：`VOICE_ID_MEARSHEIMER`；其余规划独立 `VOICE_ID_*`，未就绪前 **一律 Mearsheimer fallback**。

| 人 | 文件 |
|----|------|
| Lex | [`../characters/lex-fridman-host-perspective-SKILL.md`](../characters/lex-fridman-host-perspective-SKILL.md) |
| 吴伟 / 陈立武 / 库克 / 黄仁勋 | `wuwei-riscv-…`、`liptan-…`、`timcook-…`、`jensen-…` 同上目录 |

黄仁勋：阶段 2 **纯 CSS**；小窗保留至结束；阶段 3 在席。

**「弹药」是什么（已落盘，强制使用）**  
[`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md)：**阶段 2** 调用 Jensen 前 **必须整段注入**（锚点 + 金句池 + 独白骨架），与 [`../characters/jensen-huang-perspective-SKILL.md`](../characters/jensen-huang-perspective-SKILL.md) + [`../background/deep-research.md`](../background/deep-research.md) **叠放**，不得省略。细节与实现约定见该文件底部「实现侧拼接约定」。

---

## 5. C. 叙事阶段

1. **0** Lex 极简 + 顶栏副标题。  
2. **0.5** 播 `lex-opening-long.mp3`；**跳过** → 停长播 `lex-opening-short.mp3`（「好的，那让我们直接开始。」）→ 进 **1**。`voice_id` = `VOICE_ID_MEARSHEIMER`。  
3. **1 论坛交锋** 三级 baton（见 **§7** 与宪章 §3）。Lex **不接棒**。**收口**：每人 2 段、**共 6** 条 guest turn；第 6 段播完 → **2**。  
4. **2** Lex **主持引介** → **视频连线** UI（纯 CSS）→ 黄仁勋独白 ≤200 字（**必带** [`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md) 弹药上下文）→ 小窗。  
5. **2.5（必选）** 黄播完后 Lex：**「好，观众朋友们，我们现在进入观众提问环节。」** 播完 → **3**。  
6. **3** 主屏 chat：Summary（≤300 增量 + 近 3 轮原文）→ Intent（ASK/PROVOKE/CHITCHAT + target）→ 分发；建议 ≤120s Lex 收口。  
7. **收束** Lex 致谢一句。

---

## 6. D. 架构要点（摘录；细节以宪章为准）

**D.0** 所有 LLM system 首部：`GLOBAL_SPEAKER_CONSTRAINT` — 可见中文正文 ≤200 字（`@` 独行、JSON 字段不计）。

**D.1** `debate_runner`：**v2 Director** `0→0.5→1→2→2.5→3`；阶段 1 内按 **D.2** 选下一位；**6 段**后进 **2**；**2** 后经 **2.5** 进 **3**。

**D.2 Baton**  
1. 显式 `@`，别名归一 `lex|wuwei|liptan|cook|jensen`，多 `@` 取**最后**。  
2. **NextSpeakerSelector**（在 **eligible pool** 内针对「余下可发言席」；pool 定义见 **§6.1**）。  
3. **LRS**（仅在 **eligible pool** 上取最久未发言）。  
4. **相邻**禁同 Guest 连两轮 → 改走 2/3。  
5. **收口**：各 2 段、总和 6；`FORUM_GUEST_TURNS_TOTAL=6`（默认勿改）；计数与 pool 的 **状态机细节见 §6.1**。

**D.2b 阶段 2.5（实现默认）**  
Lex 转场句：**当场 TTS + 固定字符串**（与 [./architecture.md](./architecture.md) 文案一致），**不**要求预合成 mp3；改字只改代码/配置常量即可。

**D.3 文件**：`models.py`、`debate_runner.py`、`free_qa.py`、`tts_manager.py`、`app.py`、`.env.example`；前端 `types.ts`、`DebateAudio.tsx`、`avatars.ts`、`App.tsx`、`FreeQAPanel.tsx`、`SpeakerWindow.tsx`。

**D.4** SSE 文本可流式；音频 **整段完稿后** 一次性 TTS；**播放锁** 后再下一 turn。

**D.5** `free_qa.py`：SummaryLLM + IntentTargetLLM；JSON：`intent,target,confidence,rephrased_question`；攻击/失败 → Lex 软回应。

**D.6** 0.5：[`../background/lex-opening-script.md`](../background/lex-opening-script.md) + `scripts/pregen_lex_opening.py` + `lex-opening-{long,short}.mp3` + `OpeningPlayer.tsx`。

**D.6b 阶段 2 · Jensen 弹药**  
[`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md) 为 **必选附件**：每次生成 Jensen 阶段 2 独白前 **必须**读入并注入其「可核验锚点」「金句池」「独白骨架」全文；文件缺失或读失败 → **报错 / 构建失败**，禁止静默降级。

### 6.1 每人两轮、共六段：机制说明（非整场硬编码）

**结论**

- **不是**旧滴滴栈那种「六行固定 `(speaker, prompt)` 表」硬编码**谁第几句说什么**。
- **是**把 **`MAX_SPEECHES_PER_GUEST = 2`** 与 **`FORUM_GUEST_TURNS_TOTAL = 6`**（默认常量；可选 env **仅在不改「每人 2 段」产品语义的前提下**覆盖总配额，若只改总数不等价于每人两轮则需另开产品讨论）写进 **Director 状态**；每完成一条 **三嘉宾之一**（`wuwei|liptan|cook`）的发言，只给该嘉宾 **`count += 1`**；当且仅当 **`wuwei==2 && liptan==2 && cook==2`** 时结束阶段 1（等价校验：`sum==6 && min==2`）。

**与 Baton 的配合（关键）**

下一发言人的解析仍走 [`../../backend/baton.py`](../../backend/baton.py) 的三级逻辑（`@` → NextSpeakerSelector → LRS），但传入的 **候选人池 `pool`（eligible）** 不是固定的三人全集，而是：

```text
pool = { g in (wuwei, liptan, cook) : count[g] < 2 }
```

- 若显式 `@` 指向 **`count` 已为 2** 的嘉宾 → 视为无效，走隐式 / LRS，且 **仅在 `pool` 内** 选。
- **LRS / NextSpeakerSelector** 同样只在 `pool` 上操作；从状态上 **不可能** 合法选中「某人第三段」（实现须单测防回归：满员仍被 `@` 时降级、`pool` 大小为 1 时下一发言者唯一等）。

早期轮次 `pool` 仍为三人；中后期 `pool` 缩小；当只剩一人未满 2 段时 `pool` 大小为 1，下一发言者唯一确定。

**建议落点（实现时）**

- 在 v2 Director（[`../../backend/debate_runner.py`](../../backend/debate_runner.py) 或未来拆出的 `forum_director.py`）中维护 **`guest_speech_counts: dict[str, int]`** 与 **`phase`**。
- 为 `resolve_next_phase1_guest` 增加可选参数 **`eligible: frozenset[str]`**（即上面的 `pool`），或由包装函数在调用前将 baton 结果 **clamp** 到 `pool`。
- 单测建议：`@` 已满员嘉宾时落到 LRS/隐式且仍在 `pool` 内；第 6 段完成后 `stage` 切入 **2**；禁止第 7 段三人发言。

---

## 7. E. 交货顺序

1. [`../background/deep-research.md`](../background/deep-research.md) 留白 → Research。  
2. 五 SKILL 增量淬炼：[`../../.agents/skills/huashu-nuwa/SKILL.md`](../../.agents/skills/huashu-nuwa/SKILL.md)。  
3. 宪章已就绪；[`../background/jensen-closing-speech.md`](../background/jensen-closing-speech.md)（Jensen 弹药）已在仓，阶段 2 **强制注入**（见 **D.6b**）。  
4. Lex 0.5：pregen + mp3 + `OpeningPlayer`。  
5. 代码：Director + baton + free_qa + 枚举 + 回合级 TTS + UI + D.0。

---

## 8. F. 风险（摘）

| 风险 | 处理 |
|------|------|
| NextSpeakerSelector 失败 | 日志原文 → **LRS** |
| token 涨 | 摘要 ≤300 + 3 轮 verbatim；摘要 `temperature=0` |
| 隐式误判 | 调 prompt / 阈值 → 仍不满意则 LRS |
| 叠播 | **D.4** 完稿再 TTS + 播放锁 |

---

## 9. G. 背景信息

- **事实层**：[`../background/deep-research.md`](../background/deep-research.md) 进全员 system prompt。  
- **灵魂层**：各 SKILL；与事实数字解耦，占位亦可跑通。

---

## 10. H. 下一步

1. deep-research 留白。  
2. 五 SKILL 迭代。  
3. Lex 0.5 工程化。  
4. RISC-V 主线代码 + smoke。  
5. 仓库别名：见 [`../../README.md`](../../README.md)。

---

# 第二部分：测试规格（Coding Agent / CI）

> 目标：**少打钱、多验逻辑**。默认 **mock / 离线单测**；极少集成探活；实现须遵守 [./architecture.md](./architecture.md)。

## II.0 测试分层

| 层 | 做什么 | API 费用 |
|----|--------|----------|
| **A. 纯 Python** | `baton`、LRS、别名、`models` | 无 |
| **B. 后端 mock LLM** | `debate_runner` / `free_qa` 状态迁移 | 无 |
| **C. Vitest** | `OpeningPlayer`、阶段 prop、mock `HTMLMediaElement` | 无 |
| **D. 集成（本地）** | `GET /api/health`；可选 `RUN_LLM_SMOKE=1` **单轮** | 极低 |
| **E. E2E（可选）** | 页面能开、控制台无 error；**不**测像素审美 | 无 |

**禁止**：CI 里打满五阶段全 LLM + 全轨 TTS。

---

## II.1 按叙事阶段的验收清单

### 阶段 0 — 壳与文案

- [ ] 顶栏含「RISC-V 三国杀」与副标题；`<title>` 一致。  
- [ ] 无 `run_id` 不崩。

### 阶段 0.5 — 预录开场

- [ ] 有两 mp3：长 `play()`；跳过 → `pause` 长 → 短 `play()`；短结束进 **1**。  
- [ ] 跳过时长轨已 `paused` 再起短轨，无叠声。  
- [ ] 无 mp3：降级或提示，**不**白屏。

### 阶段 1 — 论坛交锋 + 三级 baton

- [ ] `@` 多命中取最后；别名与 `backend/baton.py` 一致。  
- [ ] 相邻禁同 Guest 连两轮。  
- [ ] LRS 平局次序。  
- [ ] `NextSpeakerSelector` 可 mock；非法 → LRS。  
- [ ] `GLOBAL_SPEAKER_CONSTRAINT`；超长 mock 有截断/拒收单测。

### 阶段 1 → 2 — 收口（钉死）

- [ ] 仅计三嘉宾；**每人 2 条、共 6 条** 且最后一条播完后 `stage→2`；**无**第 7 条三人发言。  
- [ ] 可选 env `FORUM_GUEST_TURNS_TOTAL`（默认 6）；CI 用默认。

### 阶段 2 — 黄仁勋

- [ ] LLM 调用前 **已读入并注入** `docs/background/jensen-closing-speech.md` 全文（锚点 + 金句池 + 独白骨架）；路径缺失或内容为空 → **失败**（单测覆盖）。  
- [ ] CSS 动画类名；独白 ≤200 字。  
- [ ] 小窗延续到阶段 3。

### 阶段 2.5 — Lex 转场

- [ ] Jensen `onended` 后下一段 **必定**为：「好，观众朋友们，我们现在进入观众提问环节。」（trim 全等单测）。  
- [ ] 该句结束后才 `stage===3` 且输入框可用。  
- [ ] 与黄轨不叠播（播放锁）。

### 阶段 3 — Free QA

- [ ] mock Summary + Intent；非法 JSON → Lex。  
- [ ] `target` 合法；攻击/空 → Lex。

### TTS 与播放锁（跨阶段）

- [ ] 每 turn **整段**送 TTS / 或 `TextChunker` 仅一次性 flush；可 mock 断言每 turn 一次合成。  
- [ ] 下一 turn 请求仅在 `onended` / `round_done` 之后。

---

## II.2 LLM 调用测试（省钱）

| 测试名 | 行为 | 默认 |
|--------|------|------|
| `test_llm_client_configured` | 只构 client，**不调远端** | 可跑 |
| `test_one_completion_smoke` | 1 条消息 max_tokens≤32 | 仅 `RUN_LLM_SMOKE=1` |
| `test_debate_runner_one_turn_mocked` | 全程 mock | 总是跑 |

每日 `RUN_LLM_SMOKE` ≤ 5；**CI 禁止** `RUN_LLM_SMOKE`。

---

## II.3 前端交互（Vitest / 轻 E2E）

- [ ] `OpeningPlayer`：`aria`、跳过流程。  
- [ ] `SpeakerWindow`：高亮随 `speaker` 变。  
- [ ] `FreeQAPanel`：loading / error / 列表追加（mock `fetch`）。

---

## II.4 与人眼验收的关系

人眼只做 **[宪章 §8](./architecture.md#8-人眼验收只做这三四点)**；其余以本文 **第二部分** 为准。

---

## II.5 运行命令

```bash
# 后端（项目根）
./.venv/bin/pip install -r backend/requirements.txt
./.venv/bin/python -m pytest backend/tests/ -q --ignore=backend/tests/integration/

# 集成（仅 health，无 LLM）
RUN_INTEGRATION=1 ./.venv/bin/python -m pytest backend/tests/integration/ -q

# 前端
cd frontend && npm test
```

（venv 路径按本机调整。）
