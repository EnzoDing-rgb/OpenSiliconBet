"""离线单测：传棒逻辑（无 API）。"""

import pytest

from backend.baton import (
    PHASE1_GUESTS,
    normalize_speaker_token,
    parse_explicit_baton_target,
    resolve_next_phase1_guest,
)


def test_normalize_aliases():
    assert normalize_speaker_token("@x86") == "liptan"
    assert normalize_speaker_token("RISC-V") == "wuwei"
    assert normalize_speaker_token("库克") == "cook"
    assert normalize_speaker_token("@jensen") == "jensen"


def test_parse_explicit_last_wins():
    text = "先聊两句。\n最后请 @wuwei 收尾，不对 @liptan 你说两句。"
    assert parse_explicit_baton_target(text) == "liptan"


def test_explicit_ignored_if_only_lex():
    text = "我们请 @lex 总结"
    assert parse_explicit_baton_target(text) is None


def test_resolve_explicit_over_implicit():
    last = {"wuwei": 1.0, "liptan": 2.0, "cook": 3.0}
    nxt = resolve_next_phase1_guest(
        "结论在 x86。\n→ @cook",
        "wuwei",
        implicit_next="liptan",
        last_spoken_at=last,
    )
    assert nxt == "cook"


def test_resolve_implicit_when_no_at():
    last = {"wuwei": 10.0, "liptan": 1.0, "cook": 5.0}
    nxt = resolve_next_phase1_guest(
        "我不点名了。",
        "wuwei",
        implicit_next="liptan",
        last_spoken_at=last,
    )
    assert nxt == "liptan"


def test_explicit_same_as_current_falls_through():
    """@ 自己视为无效，走隐式 / LRS。"""
    last = {"wuwei": 100.0, "liptan": 1.0, "cook": 2.0}
    nxt = resolve_next_phase1_guest(
        "我反驳我自己？@wuwei",
        "wuwei",
        implicit_next=None,
        last_spoken_at=last,
    )
    assert nxt == "liptan"  # LRS: min ts among three


def test_lrs_tie_breaker_order():
    last = {"wuwei": 0.0, "liptan": 0.0, "cook": 0.0}
    nxt = resolve_next_phase1_guest(
        "无话。",
        "cook",
        implicit_next=None,
        last_spoken_at=last,
    )
    assert nxt == "wuwei"


def test_implicit_same_as_current_uses_lrs():
    last = {"wuwei": 1.0, "liptan": 9.0, "cook": 5.0}
    nxt = resolve_next_phase1_guest(
        "继续。",
        "liptan",
        implicit_next="liptan",
        last_spoken_at=last,
    )
    assert nxt == "wuwei"
