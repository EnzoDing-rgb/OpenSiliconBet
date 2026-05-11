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
- **音色**：独立克隆就绪前 **全员 `VOICE_ID_MEARSHEIMER`**，`tts_manager` 保留 per-speaker 映射位。
- **现状**：栈上仍为 `JERVIS`/`MEARSHEIMER` + `DIALOGUE_TURNS`；v2 未接线。

### 1.1 与 Cursor Plan 同步的 TODO 清单

| 状态 | 项 |
|------|-----|
| 待办 | 用户填 [`../background/deep-research.md`](../background/deep-research.md) 留白 → review |
| 已完成 | [`../characters/wuwei-riscv-perspective-SKILL.md`](../characters/wuwei-riscv-perspective-SKILL.md)（可持续迭代） |
| 已完成 | [`../characters/liptan-x86-perspective-SKILL.md`](../characters/liptan-x86-perspective-SKILL.md) |
| 已完成 | [`../characters/timcook-arm-perspective-SKILL.md`](../characters/timcook-arm-perspective-SKILL.md) |
| 已完成 | [`../characters/jensen-huang-perspective-SKILL.md`](../characters/jensen-huang-perspective-SKILL.md) |
| 已完成 | [`../characters/lex-fridman-host-perspective-SKILL.md`](../characters/lex-fridman-host-perspective-SKILL.md) |
| 已完成 | [./architecture.md](./architecture.md)（宪章） |
| 待办 | `docs/background/jensen-closing-speech.md`（可选；或并入 jensen SKILL） |
| 待办 | `backend/free_qa.py` + `FreeQAPanel`；Summary + Intent；五人窗 |
| 待办 | `scripts/pregen_lex_opening.py` + `public/audio` 两 mp3 + `OpeningPlayer.tsx` |
| 待办 | Speaker 五枚举；`models` / `types` / `DebateAudio` / TTS 全栈对齐 |
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
| 仍缺文档（可选） | `jensen-closing-speech.md`（可放 `docs/` 或 `docs/background/`） |
| 仍缺实现 | `scripts/pregen_lex_opening.py`、两轨 mp3、`OpeningPlayer.tsx`、`free_qa.py`、`FreeQAPanel.tsx`、`SpeakerWindow.tsx`、五 speaker + v2 Director + 三级 baton + 回合级 TTS |
| 运行栈 | `app.py` + `tts_manager.py` 仍双 voice；过渡期 **全员 `VOICE_ID_MEARSHEIMER`** |

---

## 3. A. 目标

| 项 | 内容 |
|----|------|
| 主题 | 指令集 · RISC-V vs x86 vs ARM，开放探讨 |
| UI | 顶栏 + `<title>` + banner：**RISC-V 三国杀**；副标题：公众科学日分会场 |
| 受众 | 老师 + 中学生（不降智） |
| 形式 | Lex 极简 → **0.5 预录**（可跳过）→ **论坛交锋**（每人 2 段共 6 段）→ Lex 手机钩 → 黄 **CSS** 独白 → **Lex 2.5 转场** → 主屏 chat → Lex 收束 |
| 知识轴 | RISC-V 能否替代 x86/ARM；Agent 窗口；1–3 年走向 |

---

## 4. B. 五人

全员中文；人设见 [`../characters/`](../characters/)。0.5 预录：`VOICE_ID_MEARSHEIMER`；其余规划独立 `VOICE_ID_*`，未就绪前 **一律 Mearsheimer fallback**。

| 人 | 文件 |
|----|------|
| Lex | [`../characters/lex-fridman-host-perspective-SKILL.md`](../characters/lex-fridman-host-perspective-SKILL.md) |
| 吴伟 / 陈立武 / 库克 / 黄仁勋 | `wuwei-riscv-…`、`liptan-…`、`timcook-…`、`jensen-…` 同上目录 |

黄仁勋：阶段 2 **纯 CSS**；小窗保留至结束；阶段 3 在席。

---

## 5. C. 叙事阶段

1. **0** Lex 极简 + 顶栏副标题。  
2. **0.5** 播 `lex-opening-long.mp3`；**跳过** → 停长播 `lex-opening-short.mp3`（「好的，那让我们直接开始。」）→ 进 **1**。`voice_id` = `VOICE_ID_MEARSHEIMER`。  
3. **1 论坛交锋** 三级 baton（见 **§7** 与宪章 §3）。Lex **不接棒**。**收口**：每人 2 段、**共 6** 条 guest turn；第 6 段播完 → **2**。  
4. **2** Lex 手机钩 → CSS「视频电话」→ 黄仁勋独白 ≤200 字 → 小窗。  
5. **2.5（必选）** 黄播完后 Lex：**「好，观众朋友们，我们现在进入观众提问环节。」** 播完 → **3**。  
6. **3** 主屏 chat：Summary（≤300 增量 + 近 3 轮原文）→ Intent（ASK/PROVOKE/CHITCHAT + target）→ 分发；建议 ≤120s Lex 收口。  
7. **收束** Lex 致谢一句。

---

## 6. D. 架构要点（摘录；细节以宪章为准）

**D.0** 所有 LLM system 首部：`GLOBAL_SPEAKER_CONSTRAINT` — 可见中文正文 ≤200 字（`@` 独行、JSON 字段不计）。

**D.1** `debate_runner`：**v2 Director** `0→0.5→1→2→2.5→3`；阶段 1 内按 **D.2** 选下一位；**6 段**后进 **2**；**2** 后经 **2.5** 进 **3**。

**D.2 Baton**  
1. 显式 `@`，别名归一 `lex|wuwei|liptan|cook|jensen`，多 `@` 取**最后**。  
2. **NextSpeakerSelector**（余下两席）。  
3. **LRS**。  
4. **相邻**禁同 Guest 连两轮 → 改走 2/3。  
5. **收口**：各 2 段、总和 6；`FORUM_GUEST_TURNS_TOTAL=6`（默认勿改）。

**D.3 文件**：`models.py`、`debate_runner.py`、`free_qa.py`、`tts_manager.py`、`app.py`、`.env.example`；前端 `types.ts`、`DebateAudio.tsx`、`avatars.ts`、`App.tsx`、`FreeQAPanel.tsx`、`SpeakerWindow.tsx`。

**D.4** SSE 文本可流式；音频 **整段完稿后** 一次性 TTS；**播放锁** 后再下一 turn。

**D.5** `free_qa.py`：SummaryLLM + IntentTargetLLM；JSON：`intent,target,confidence,rephrased_question`；攻击/失败 → Lex 软回应。

**D.6** 0.5：[`../background/lex-opening-script.md`](../background/lex-opening-script.md) + `scripts/pregen_lex_opening.py` + `lex-opening-{long,short}.mp3` + `OpeningPlayer.tsx`。

---

## 7. E. 交货顺序

1. [`../background/deep-research.md`](../background/deep-research.md) 留白 → Research。  
2. 五 SKILL 增量淬炼：[`../../.agents/skills/huashu-nuwa/SKILL.md`](../../.agents/skills/huashu-nuwa/SKILL.md)。  
3. 宪章已就绪；可选 `docs/background/jensen-closing-speech.md`。  
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
