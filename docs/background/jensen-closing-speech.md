# Jensen 阶段 2 独白 · 弹药（固定上下文）

> **用途**：在 `speaker=jensen`、**阶段 2**（≤200 字可见正文）生成独白时，由 `debate_runner` / Director **必须**把本文件指定章节并入 LLM 上下文（与 SKILL、deep-research **叠放**，不是二选一）。  
> **人设与语气**：仍以 [`../characters/jensen-huang-perspective-SKILL.md`](../characters/jensen-huang-perspective-SKILL.md) 全文为准；本文件提供 **可复述的硬锚 + 金句 + 导演骨架**，压低胡编率。

## 与 SKILL 的对齐

- 戏剧钩子、**「你们都没赢，我赢了」**、卖铲子、→ `@无` 等 **Baton 末行协议** → 见 SKILL「Demo 专有约束」「阶段 2 闭幕独白」。
- 本章只收 **更短、更贴 deep-research §2/§4/§6 口径** 的条目，便于 LLM **一句带过**。

## 可核验锚点（优先顺序 · 独白里择 2–4 点用）

1. **三家都买、都算力栈**：Grace 走 **ARM Neoverse**；DGX **部分配置**仍用 **Intel Xeon** 作主机 CPU；GPU 侧控制面 **Falcon → RISC-V** 路线为公开技术叙事（参见 Linux 文档对 Falcon 模块说明；产业侧有「单年约 **10 亿颗** RISC-V 核级出货量」量级报道，口径以 [RISC-V International 博文](https://riscv.org/blog/2025/02/how-nvidia-shipped-one-billion-risc-v-cores-in-2024/) / 二次报道为准，**勿夸成「手机应用核」**）。
2. **RISC-V 投资线**：对 **SiFive** 等 RISC-V 生态公司有公开投资与合作报道——细节数字以 `deep-research.md` §6 为准，演讲前重核。
3. **CUDA / 平台 vs 单 ISA**：CUDA 是 **横切 workload** 的软件栈叙事；与「垂直整合的 Apple Silicon moat」对仗时，用 SKILL 里 **horizontal vs vertical** 一句即可，**不必**展开股价。
4. **共存论**：「x86 与 ARM 长期共存、RISC-V 进入组合」与 deep-research §2「三角」一致时，可作为收束前一句的 **事实垫话**。
5. **合规边界**：反垄断、自研 AI 芯片分流 GPU——**承认压力一句带过**即可，不把 demo 变成监管听证会。

## 金句池（每条 ≤40 字 · 独白须至少化用 1 条，可改写不照抄）

- 「你们争 ISA，我卖**算力栈**——三家都从我这里进货。」
- 「**RISC-V 在我 GPU 里干活**——不是来取代 CUDA，是来**当控制器**。」
- 「**Grace 是 ARM，机头是 Xeon，GPU 里是 RISC-V**——这就是我的『全栈中立』。」
- 「CUDA 二十年堆出来的**开发者惯性**，比任何一条 ISA 都难搬。」

（英文短语若用，须 SKILL 约定：**整段仍以中文为主**，每段最多 1–2 处英文口头禅。）

## 独白骨架（约 120–180 字 · 可让模型略缩到 ≤200）

> 以下为 **导演稿**，非黄仁勋本人言论；生成时须遵守 `GLOBAL_SPEAKER_CONSTRAINT` 与 SKILL 末行 `→ @无`。

```
Lex，各位——前面开源、代工、生态，我听见了。**三家叙事都对一半**。**但你们都没赢，我赢了**：我栈里有 **ARM Grace**、有 **Xeon 主机**、GPU 里 **RISC-V 控制核**在跑——**指令集吵得越凶，我越像卖铲子的**。**算力 + CUDA 生态才是 AI 时代的基础设施。** → @无
```

可按现场节奏删掉半句，**保留**「三家都沾 + 卖铲子 + 基础设施」三角。

## 实现侧拼接约定（给 coding agent）

- **路径**：`docs/background/jensen-closing-speech.md`（本文件，**随仓必带**）。
- **注入**：进入阶段 2、调用 Jensen 之前，**必须**将 **「## 可核验锚点」+「## 金句池」+「## 独白骨架」** 全文 append 到 user 侧（或等价的 `additional_context`）；**不得**省略、不得用空字符串占位。
- **校验**：启动或 CI 中若该路径不可读 → **视为构建失败**，须立刻修复；与「缺 mp3 降级」类逻辑无关。

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05 | 初版：蒸馏自 `jensen-huang-perspective-SKILL.md` + `deep-research.md` §2 占位事实 + 公开报道级 RISC-V 核出货量口径 |
