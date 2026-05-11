"""
RISC-V 三国杀 · 阶段 1 传棒（纯逻辑，无 I/O）。

规则来源：docs/design/architecture.md §3。
调用方负责：在回合结束时把「刚发言的嘉宾」写入 last_spoken_at（单调时间戳）。
"""

from __future__ import annotations

import re
from typing import AbstractSet, Dict, Iterable, Mapping, Optional, Tuple

# 阶段 1 仅三阵营在席传棒（Lex / Jensen 不参与此池）
PHASE1_GUESTS: Tuple[str, ...] = ("wuwei", "liptan", "cook")

_AT_TOKEN_RE = re.compile(r"@([^\s@，。！？；:,.;!?]+)")


def _norm_token(raw: str) -> str:
    return raw.strip().lower().replace("－", "-").replace("—", "-")


# 别名 → 规范 id（仅小写）；未命中则返回 None
_ALIASES: Dict[str, str] = {}
for _canon, _aliases in (
    ("wuwei", ("吴伟", "riscv", "risk-v", "riskv", "risc-v", "risc5", "睿芯", "wuwei", "伍伟")),
    ("liptan", ("陈立武", "x86", "intel", "lipbu", "lip-bu", "liptan", "立武", "tan")),
    ("cook", ("库克", "arm", "apple", "tim", "timcook", "cook", "苹果", "silicon")),
    ("lex", ("lex", "弗莱德曼", "弗里德曼")),
    ("jensen", ("jensen", "黄仁勋", "老黄", "nvidia", "英伟达")),
):
    _ALIASES[_canon] = _canon
    for a in _aliases:
        _ALIASES[_norm_token(a)] = _canon


def normalize_speaker_token(token: str) -> Optional[str]:
    """将单个 token（可含 @ 前缀）归一为 lex|wuwei|liptan|cook|jensen。"""
    t = token.strip()
    if t.startswith("@"):
        t = t[1:]
    key = _norm_token(t)
    if key in _ALIASES:
        return _ALIASES[key]
    # 英文直接键
    if key in PHASE1_GUESTS or key in ("lex", "jensen"):
        return key
    return None


def parse_explicit_baton_target(text: str) -> Optional[str]:
    """
    从全文取 **最后一次** 有效的 @ 指向（多 @ 取最后）。
    若指向非阶段 1 池内成员（lex/jensen），返回 None（由调用方决定是否允许跨阶段）。
    """
    if not text:
        return None
    last: Optional[str] = None
    for m in _AT_TOKEN_RE.finditer(text.replace("\r\n", "\n")):
        raw = m.group(1)
        canon = normalize_speaker_token(raw)
        if canon in PHASE1_GUESTS:
            last = canon
    return last


def _lrs_pick(last_spoken_at: Mapping[str, float], pool: Iterable[str], tie_order: Tuple[str, ...]) -> str:
    """pool 中取 last_spoken_at 最小者；平局按 tie_order 靠前优先。"""
    pool_list = list(pool)
    if not pool_list:
        raise ValueError("empty pool")

    def key(g: str) -> Tuple[float, int]:
        ts = float(last_spoken_at.get(g, 0.0))
        try:
            prio = tie_order.index(g)
        except ValueError:
            prio = 999
        return (ts, prio)

    return min(pool_list, key=key)


def _normalize_pool(eligible: Optional[AbstractSet[str]]) -> Tuple[str, ...]:
    """eligible ∩ PHASE1_GUESTS，按 PHASE1_GUESTS 顺序稳定排列。"""
    if eligible is None:
        return PHASE1_GUESTS
    el = frozenset(eligible) & frozenset(PHASE1_GUESTS)
    if not el:
        raise ValueError("eligible ∩ PHASE1_GUESTS is empty")
    return tuple(g for g in PHASE1_GUESTS if g in el)


def resolve_next_phase1_guest(
    completed_text: str,
    current_speaker: str,
    *,
    implicit_next: Optional[str],
    last_spoken_at: Mapping[str, float],
    eligible: Optional[AbstractSet[str]] = None,
) -> str:
    """
    返回下一发言的 **阶段 1 嘉宾** id（wuwei|liptan|cook）。

    优先级：显式 @（**在 eligible pool 内**、且 ≠ current）→ implicit_next（∈ pool 且 ≠ current）→ LRS（仅在 pool 上）。

    若 @ 指向已满员（不在 pool）的嘉宾，视为无效 @，走隐式 / LRS（见 docs/design/implementation.md §6.1）。

    implicit_next 应由上游 NextSpeakerSelector LLM 产出并已归一；非法则视为 None。
    """
    if current_speaker not in PHASE1_GUESTS:
        raise ValueError(f"current_speaker must be one of {PHASE1_GUESTS}, got {current_speaker!r}")

    pool = _normalize_pool(eligible)

    explicit = parse_explicit_baton_target(completed_text)
    if explicit is not None and explicit in pool and explicit != current_speaker:
        return explicit

    imp = implicit_next if implicit_next in pool else None
    if imp is not None and imp != current_speaker:
        return imp

    nxt = _lrs_pick(last_spoken_at, pool, PHASE1_GUESTS)
    if nxt == current_speaker:
        for g in pool:
            if g != current_speaker:
                return g
    return nxt
