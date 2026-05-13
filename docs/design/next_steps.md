# design/ 下一步（执行序）

## 已写进宪章的扩展（先读再码）

| 主题 | 文档 |
|------|------|
| 三家股价联动（快照、prompt 佐料、边界） | [architecture.md §9](./architecture.md#9-三家股价联动市场快照--设计意图) |
| 观众 chat + 按钮 → LLM 策展 → Markdown 落盘 | [architecture.md §10](./architecture.md#10-观众-chat-与观点持久化llm-策展--落盘文档) |
| 上述两块的里程碑与测试钩子 | [implementation.md 第三部分](./implementation.md#第三部分扩展能力股价联动--chat-策展落盘) |
| TTS 与扩展能力正交说明 | [realtime-tts-architecture.md 末尾](./realtime-tts-architecture.md#与股价联动chat-策展落盘的关系) |

## 建议实现顺序（可并行）

1. **宪章主干**（若未绿）：`implementation.md` 第二部分阶段 0–3 + TTS 播放锁。
2. **行情 strip**：快照 API → UI 一行 → 开局可选 `market_context`（III.1）。
3. **落盘**：Curator 端点 + allowlist 写文件 + 阶段 3 按钮（III.2）；**暂不**做刷新自动同步 UI（留坑）。

## 刻意不做的（当前轮）

- 刷新后自动拉最新笔记、SSE 推送笔记更新。
- 把完整观众聊天记录无策展直接写 git。
