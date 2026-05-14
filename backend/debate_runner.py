import os
import time
import uuid
import asyncio
import re
from typing import Dict, List, Tuple, Optional, Sequence
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError, AuthenticationError, RateLimitError
from .models import DebateRun, RunStatus, Turn, Speaker, ChatMessage

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# API config (MUST come from environment variables; do not hardcode secrets)
# Preferred env names:
# - API_PROTOCOL: openai | anthropic
# - API_BASE_URL
# - API_KEY
# - MODEL
#
# Backward-compatible aliases (optional):
# - ARK_API_KEY, ARK_BASE_URL, ARK_MODEL
ARK_API_KEY: str = ""
ARK_BASE_URL: str = ""
ARK_MODEL: str = ""

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _is_volcengine_quota_exhausted(exc: BaseException) -> bool:
    """429 / AccountQuotaExceeded from Volcengine Ark (and similar OpenAI-compatible gateways)."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIError):
        status = getattr(exc, "status_code", None)
        if status == 429:
            return True
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            err = body.get("error") or {}
            if err.get("code") == "AccountQuotaExceeded":
                return True
        if body is not None and "AccountQuotaExceeded" in str(body):
            return True
    text = str(exc)
    if "AccountQuotaExceeded" in text:
        return True
    if "429" in text and ("quota" in text.lower() or "AccountQuota" in text):
        return True
    return False

# Skill file paths (relative to project root)
PROJECT_ROOT = Path(os.path.dirname(__file__)).parent
#
# Skill drop-in points:
# - Default: use repo-local case skills under docs/
# - If you later move skills into .agents/skills/, you can override via env:
#   - DIDI_SKILL_PATH=/abs/or/relative/path
#   - MANUS_SKILL_PATH=/abs/or/relative/path
#
def _skill_path(env_name: str, default_rel: Path) -> Path:
    raw = _env(env_name)
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (PROJECT_ROOT / p)
    return default_rel


DEEP_RESEARCH_PATH = _skill_path("DEEP_RESEARCH_PATH", PROJECT_ROOT / "docs" / "background" / "deep-research.md")
WUWEI_SKILL_PATH = _skill_path("WUWEI_SKILL_PATH", PROJECT_ROOT / "docs" / "characters" / "wuwei-riscv-perspective-SKILL.md")
LIPTAN_SKILL_PATH = _skill_path("LIPTAN_SKILL_PATH", PROJECT_ROOT / "docs" / "characters" / "liptan-x86-perspective-SKILL.md")
COOK_SKILL_PATH = _skill_path("COOK_SKILL_PATH", PROJECT_ROOT / "docs" / "characters" / "timcook-arm-perspective-SKILL.md")
JENSEN_SKILL_PATH = _skill_path("JENSEN_SKILL_PATH", PROJECT_ROOT / "docs" / "characters" / "jensen-huang-perspective-SKILL.md")
LEX_SKILL_PATH = _skill_path("LEX_SKILL_PATH", PROJECT_ROOT / "docs" / "characters" / "lex-fridman-host-perspective-SKILL.md")
JENSEN_CLOSING_PATH = _skill_path(
    "JENSEN_CLOSING_PATH", PROJECT_ROOT / "docs" / "background" / "jensen-closing-speech.md"
)

# Dialogue topic（论坛交锋 demo）
DEBATE_TOPIC = "RISC-V vs x86 vs ARM：Agent 时代的指令集与算力格局（公众科学日分会场 · 论坛交锋）"

MAX_RESPONSE_TOKENS = 400
# 与宪章 GLOBAL 对齐：可见中文正文约 200 字（宁少勿灌水）
RESPONSE_LEN_HINT_ZH = "中文可见正文约 两百字以内（用汉字写「两百」仅作提示）；宁少勿堆字，密度优先。**念给语音听**：年限、比例、年份尽量用汉字（三十年、百分之六十），少用阿拉伯数字串。"
FORUM_LLM_TEMPERATURE = 0.88
DEFAULT_LLM_TEMPERATURE = 0.72
DISPLAY_DELAY_SECONDS_PER_TURN = 7.0

# Judge output needs to be longer than debater turns; otherwise it gets cut off.
JUDGE_MAX_RESPONSE_TOKENS = 500
# Lex 散场锐评：略拉高温度，口语更像人（仍受模型上限约束）
JUDGE_LLM_TEMPERATURE = 0.86
# 注入 Lex SKILL 全文可能过长；保留前缀保证角色 DNA + 心智模型进上下文
LEX_REVIEW_SKILL_MAX_CHARS = 14000

# Master chat should allow longer, multi-turn replies.
CHAT_MAX_RESPONSE_TOKENS = 500


def _speaker_zh(speaker: Speaker) -> str:
    return {
        Speaker.LEX: "Lex Fridman（主持人）",
        Speaker.WUWEI: "吴伟（RISC-V）",
        Speaker.LIPTAN: "陈立武（x86 / Intel）",
        Speaker.COOK: "蒂姆·库克（ARM / Apple）",
        Speaker.JENSEN: "黄仁勋（NVIDIA）",
    }[speaker]


def _interaction_wrapper(opponent_name_zh: str, opponent_last: Optional[str]) -> str:
    if not opponent_last:
        return ""
    return (
        f"\n\n【上一位刚说完的原话（接着往下接，像在圆桌上抢话 / 接话，别像在写纪要）】\n"
        f"{opponent_name_zh}：\n{opponent_last}\n"
    )


ORAL_FORUM_CONTRACT_ZH = """
【本场表达契约 — 现场圆桌 + 语音给观众听】
- 场合是**公众科学日分会场**：台下是真观众，你的话会走 **TTS 念出来**——要像**对着人和麦克风聊天**，有停顿、有口气；不要咨询备忘录、PR one-pager、研报「执行摘要」体。
- **念给 TTS 的中文数字**：阿拉伯数字易被读成「三零年」之类。**年限、年份、百分比、金额、型号里的数字尽量用汉字**：写「三十年」不要写「30年」，「百分之六十」不要写「60%」，「二零二五年」优于「2025」；若必须用数码，优先全角「３０」并少用。
- **禁止**在正文里出现传棒符号：`@人名`、`@无`、`→@`、`→ @` 等——**仅限吴伟 / 陈立武 / 库克三位论坛嘉宾**；想点名就口语直呼「老陈」「库克这边」之类自然带过即可。
- **黄仁勋（阶段二视频串场闭幕独白）例外**：须遵守 SKILL 末行 Baton，**仅允许** `→ @无` / `→ @所有人` / `→ @吴伟` / `→ @陈立武` / `→ @库克` 五选一，且放在**最后一行**。
- **禁止**公文编号腔：不要写「Q1/Q2」「第1条」「1）共识」这种；宁可短句、偶尔自我打断「不对，我换个说法」。
- **少用** markdown 大标题层级；**加粗**最多一两处真正要敲黑板的地方；不要为排版而排版。
- 事实底盘在 system 里已给：心里有数即可，**口语里不必句句挂「§几」**；拿不准就说「这块我还得回去核一下」。
"""


_FORUM_HEAD_ALIASES: Dict[Speaker, Tuple[str, ...]] = {
    Speaker.WUWEI: ("吴伟",),
    Speaker.LIPTAN: ("陈立武",),
    Speaker.COOK: ("蒂姆·库克", "库克"),
    Speaker.JENSEN: ("黄仁勋", "Jensen"),
    Speaker.LEX: ("Lex", "Lex Fridman"),
}


def _strip_redundant_speaker_head(text: str, speaker: Speaker) -> str:
    """UI 已显示嘉宾名时，去掉正文开头重复的「吴伟：」或单独一行姓名。"""
    aliases = _FORUM_HEAD_ALIASES.get(speaker)
    if not aliases or not text:
        return text
    t = text
    for _ in range(3):
        raw = t.replace("\r\n", "\n").lstrip()
        if not raw:
            return t
        first_line, sep, rest = raw.partition("\n")
        fl = first_line.strip()
        matched = False
        for a in aliases:
            for wrap in (False, True):
                core = f"【{a}】" if wrap else a
                for suf in ("", "：", ":", "，", ",", "。", ".", "——", "—"):
                    if fl == core + suf:
                        matched = True
                        break
                if matched:
                    break
            if matched:
                break
        if matched:
            t = rest.lstrip()
            continue
        # 同一行重复两次短名，如「吴伟 吴伟」
        bits = fl.split()
        if len(bits) >= 2 and bits[0] == bits[1] and bits[0] in aliases:
            t = rest.lstrip()
            continue
        break
    return t


def _number_to_chinese_digit_reading(n: int) -> str:
    """数位读法：3200 → 三千二百。"""
    digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if n == 0:
        return "零"
    if n < 10:
        return digits[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + digits[n % 10]
    if n < 100:
        tens = n // 10
        rest = n % 10
        return digits[tens] + "十" + (digits[rest] if rest else "")
    if n < 1000:
        hundreds = n // 100
        rest = n % 100
        result = digits[hundreds] + "百"
        if rest:
            if rest < 10:
                result += "零" + digits[rest]
            else:
                result += _number_to_chinese_digit_reading(rest)
        return result
    if n < 10000:
        thousands = n // 1000
        rest = n % 1000
        result = digits[thousands] + "千"
        if rest:
            if rest < 100:
                result += "零" + _number_to_chinese_digit_reading(rest)
            else:
                result += _number_to_chinese_digit_reading(rest)
        return result
    return str(n)


def _number_to_chinese(num_str: str) -> str:
    """TTS 友好：把阿拉伯数字按口语读法转中文。
    年份读法（4位数且后面带「年」）：2012年 → 二零一二年（逐字读）
    普通数字（1-3位，或 4 位非年份）：量读法 → 三十、十七、一千二百
    百分比：3200% → 百分之三千二百（调用 _number_to_chinese_digit_reading）
    """
    digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]

    # 4位数字且不是年份上下文的：按数位读（1234 → 一千二百三十四）
    if re.match(r"^\d{4}$", num_str):
        # 注意：年份的逐字读由上层 re.sub(r'(\d{4})(年)') 处理
        # 这里进来的是普通的 4 位数字（不带年），按数位读
        return _number_to_chinese_digit_reading(int(num_str))

    # 普通数字：量读法
    try:
        n = int(num_str)
        return _number_to_chinese_digit_reading(n)
    except ValueError:
        return num_str


def _convert_numerals_to_chinese_readable(text: str) -> str:
    """把文本中的阿拉伯数字替换成 TTS 可读的中文口语。"""
    if not text:
        return text
    t = text

    # 百分比：60% → 百分之六十（先处理避免 % 被拆开）
    def replace_percent(m: re.Match[str]) -> str:
        return "百分之" + _number_to_chinese(m.group(1))

    t = re.sub(r"(\d+(?:\.\d+)?)%", replace_percent, t)

    # 年份：2025年 → 二零二五年
    def replace_year(m: re.Match[str]) -> str:
        year_chinese = "".join(["零一二三四五六七八九"[int(d)] for d in m.group(1)])
        return year_chinese + m.group(2)

    t = re.sub(r"(\d{4})(年)", replace_year, t)

    # 百分比：% 前面的数字转中文
    def replace_percent(m: re.Match[str]) -> str:
        num = m.group(1)
        # 百分比用中文数位读法：3200 → 三千二百
        try:
            n = int(num)
            if n < 10000:
                return "百分之" + _number_to_chinese_digit_reading(n)
        except ValueError:
            pass
        return "百分之" + num

    t = re.sub(r"(\d+(?:\.\d+)?)%", replace_percent, t)

    # 年份：2025年 → 二零二五年（逐字读法）
    def replace_year(m: re.Match[str]) -> str:
        year_chinese = "".join(["零一二三四五六七八九"[int(d)] for d in m.group(1)])
        return year_chinese + m.group(2)

    t = re.sub(r"(\d{4})(年)", replace_year, t)

    # "第X轮" → "第X轮" 但 X 转中文
    def replace_round(m: re.Match[str]) -> str:
        return "第" + _number_to_chinese(m.group(1)) + "轮"

    t = re.sub(r"第(\d+)轮", replace_round, t)

    # 所有阿拉伯数字（1-4位）：直接替换，不管前后是什么字符
    # 排除已知的专有名词：x86，ARMv8 等，以及 8086/80386 等 CPU 型号
    SKIP_NUMBERS = {"86", "8086", "80386", "80486", "64", "32", "128", "256", "512", "1024"}

    def replace_all_numbers(m: re.Match[str]) -> str:
        num = m.group(1)
        if num in SKIP_NUMBERS:
            return num  # 专有名词保留阿拉伯数字
        if len(num) <= 4:
            return _number_to_chinese(num)
        return num  # 太长的保留原文

    t = re.sub(r"(\d+)", replace_all_numbers, t)

    return t


def _clean_forum_live(text: str, *, speaker: Optional[Speaker] = None) -> str:
    """去掉自述头、末尾 @ 传棒等不适合 TTS/现场感的痕迹。"""
    if not text:
        return text
    t = text.replace("\r\n", "\n").strip()
    # 去掉开头的「我是…」类标签（可出现多次）
    for _ in range(4):
        nt = re.sub(r"^【我是[^】]+】\s*", "", t, flags=re.MULTILINE).strip()
        if nt == t:
            break
        t = nt
    # 去掉末尾单独一行「→ @xxx」「@xxx」
    lines = t.split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if re.match(r"^[→＞>]?\s*@\S+\s*$", last) or re.match(r"^@\S+\s*$", last):
            lines.pop()
            continue
        break
    t = "\n".join(lines).strip()
    # 去掉文末同一行里夹着的 →@xxx
    t = re.sub(r"[ \t]*[→＞>]\s*@\S+\s*$", "", t).strip()
    if speaker is not None:
        t = _strip_redundant_speaker_head(t, speaker)
    # 强制把阿拉伯数字转成中文口语读法（TTS 友好）
    t = _convert_numerals_to_chinese_readable(t)
    return t


def _tts_speech_optimization(text: str) -> str:
    """【仅 TTS 使用】语音友好化处理：不影响前端显示，只优化 TTS 读法。
    前端原样显示：x86, RISC-V
    TTS 优化读：叉86, RISC五（避免读成 RISC减V）
    """
    if not text:
        return text
    t = text

    # x86 → 叉86（不要读成「艾克斯86」）
    t = re.sub(r"x86", "叉86", t, flags=re.IGNORECASE)

    # RISC-V → RISC五（避免读成 RISC减V）
    t = re.sub(r"RISC-V", "RISC五", t)
    t = re.sub(r"RISC V", "RISC五", t)

    # ARM → 保持 ARM（TTS 读得还可以）

    return t


_DISCLAIMER_LINE_RE = re.compile(
    r"(?:"
    r"我以.*?视角.*?(?:聊|回应)"
    r"|基于公开言论推断"
    r"|非本人观点"
    r"|免责声明"
    r")"
)


def _clean_model_output(text: str) -> str:
    """
    Remove boilerplate/disclaimer lines that models may emit.
    We do this in software to guarantee UI cleanliness.
    """
    if not text:
        return text

    lines_in = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines_out: List[str] = []
    for line in lines_in:
        # Drop any line containing boilerplate disclaimer phrases.
        if _DISCLAIMER_LINE_RE.search(line):
            continue
        # Extra hard filter (some models vary wording slightly)
        if ("视角" in line and "非本人观点" in line) or ("公开言论" in line and "非本人观点" in line):
            continue
        lines_out.append(line)

    # Collapse excessive blank lines
    cleaned: List[str] = []
    prev_blank = False
    for line in lines_out:
        blank = (line.strip() == "")
        if blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = blank

    return "\n".join(cleaned).strip()


# 阶段 1 论坛交锋：每人 2 段、共 6 段（顺序：吴伟→陈立武→库克×2 轮）。口吻：现场口语 + TTS，非纪要体。
DIALOGUE_TURNS: List[Tuple[Speaker, str]] = [
    (Speaker.WUWEI, (
        "你是吴伟，圆桌**开场第一段**。台下是公众科学日分会场观众，左右还有两位同行在听。\n"
        "像对着人和麦克风聊天：先把「Agent 时代 RISC-V 的机会」摊开，**一两个点**就够，可以带半句「我猜你们接下来要杠我哪」。\n"
        "事实别编；拿不准就说「这块我还得回去核一下」。不要人身攻击。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.LIPTAN, (
        "你是陈立武，接着吴伟**刚才那段话**往下接——先用**一句口语**接住（顶一句、笑一下、认一半都行），"
        "再从 **x86 / Intel、存量系统、工艺与产品节奏** 里挑你最有把握的角度聊，别写成「Q1/Q2」那种答辩稿。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.COOK, (
        "你是库克，接着现场气氛往下聊：别端「公关声明」腔，可以有一句「我直说」式的坦白。"
        "从 **ARM / Apple 的功耗与整合、IP 模式** 里挑你能站得住的两句硬话，顺带对另外两路各**半句**「我懂你的压力，但…」。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.WUWEI, (
        "你是吴伟，**第二轮**：接着前面已经聊出来的火药味，往 **设计自由度 vs 生态碎片化** 上收一收，"
        "可以抛一个**可检验的预测**，但用口语说出来，别列「待核验清单」。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.LIPTAN, (
        "你是陈立武，**第二轮**：从 **软件栈 / 数据中心 CPU-GPU 配比** 里抓一个你最有手感的点，"
        "用**讲故事**的方式讲出来——可以反问一句，但不要写成「对方过度简化」的八股标题。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.COOK, (
        "你是库克，**收个尾**：像主持人跟观众说一句「今天先聊到这」，顺手把三条路线各**点一句人话**，"
        "让观众觉得「这三个人是真的在吵同一件事」，不是来判输赢的。"
        f"\n{RESPONSE_LEN_HINT_ZH}"
    )),
]


def _format_turns_transcript_zh(turns: Sequence[Turn]) -> str:
    transcript_lines: List[str] = []
    current_round = 0
    for t in turns:
        if t.round != current_round:
            current_round = t.round
            transcript_lines.append(f"\n## 第 {current_round} 轮\n")
        transcript_lines.append(f"{_speaker_zh(t.speaker)}：{t.text}\n")
    return "\n".join(transcript_lines).strip()


def _lex_review_system_prompt(lex_skill_body: str) -> str:
    """散场总结：Lex 口吻 + 仓库 Lex SKILL 注入（截断防爆上下文）。"""
    body = (lex_skill_body or "").strip()
    if not body:
        body = "（未找到 lex-fridman-host-perspective-SKILL：请你仍以 Lex Fridman 式中文口播收尾——好奇、短句、steelman、不站队、少套话。）"
    elif len(body) > LEX_REVIEW_SKILL_MAX_CHARS:
        body = body[:LEX_REVIEW_SKILL_MAX_CHARS].rstrip() + "\n\n[Lex SKILL 已截断：token 预算]\n"

    return (
        "你是 **Lex Fridman**。下面整段来自本仓库 `docs/characters/lex-fridman-host-perspective-SKILL.md`，"
        "等于你的表达 DNA / 心智模型 / demo 约束。\n"
        "**本回合任务类型**：散场后的「Lex 口述锐评」——像 podcast 尾声对着观众收束，不是 live 主持抢话；"
        "但仍必须听起来像你本人（中文为主，招牌英文每整段 ≤1 句且紧跟中文，见 SKILL）。\n\n"
        "---BEGIN LEX SKILL---\n"
        f"{body}\n"
        "---END LEX SKILL---\n\n"
        "【Lex 锐评 — 硬规则】\n"
        "- 只根据 user 消息里的 transcript；**禁止**发明 transcript 没有的硬数字、公司内幕、场外事实。\n"
        "- 像真人：短句、停顿感、好奇、先 steelman 再点出张力；**不判输赢**、不当裁判写判决书。\n"
        "- 禁止「1）2）3）」、禁止咨询报告 / 公文摘要腔、禁止「作为一个人工智能」类 meta。\n"
        "- 约 **3–6 段**口语；可加 **一两处加粗** 帮观众抓住关键词；宁像说完下车，不像机器人纪要。\n"
        "- **口语数字**：年限、比例、年份多用汉字（三十年、百分之六十），少用阿拉伯数字串，避免念给 TTS 时读错。\n"
    )


def _lex_review_user_prompt(topic: str, turns: List[Turn]) -> str:
    transcript = _format_turns_transcript_zh(turns)
    return (
        f"主题：{topic}\n\n"
        f"以下是圆桌口语实录（含论坛与串场；别帮嘉宾改口风）：\n{transcript}\n\n"
        "现在请你 **以 Lex Fridman 的身份** 写散场总结（Lex 锐评）："
        "抓住每位嘉宾**最硬**的一点、今天**真正掐起来**的一处张力、再给观众 **2–3 个**散场后可自己去查证的方向（用口语点名即可，别列公文清单）。"
    )


def _jensen_vc_user_prompt(turns_block: str, ammo: str) -> str:
    return (
        "论坛三位嘉宾已完成实录（见下）。你现在处于「阶段二 · 视频串场」：像刚接入的视频电话，短独白。\n\n"
        f"--- 实录 ---\n{turns_block}\n\n"
        f"--- 导演弹药（精读；可化用骨架与金句；勿发明实录没有的硬数字）---\n{ammo.strip()}\n\n"
        "【硬要求】\n"
        "- 中文可见正文 ≤ 两百字；口语数字：年限、比例、年份用汉字（如三十年、百分之六十），少用阿拉伯数字。\n"
        "- 须让观众听清「你们都没赢」与「我赢了」两大块语义；推荐嵌进一整句，例如「其实你们都没赢，我赢了」。\n"
        "- 末行 Baton：→ @无（或与 SKILL 一致的另四种之一）。\n"
        "- 叙事仍落在 SKILL：三家都买你的栈、卖铲子、CUDA / horizontal moat。\n"
    )


def _ensure_jensen_golden_line(text: str) -> str:
    t = (text or "").strip()
    if "都没赢" in t and "我赢了" in t:
        return t
    graft = "其实你们都没赢，我赢了。"
    if t:
        return (t.rstrip() + "\n\n" + graft).strip()
    return graft


class DebateRunner:
    def __init__(self):
        self.deep_research = self._read_skill(DEEP_RESEARCH_PATH)
        self._skills: Dict[Speaker, str] = {
            Speaker.WUWEI: self._read_skill(WUWEI_SKILL_PATH),
            Speaker.LIPTAN: self._read_skill(LIPTAN_SKILL_PATH),
            Speaker.COOK: self._read_skill(COOK_SKILL_PATH),
            Speaker.JENSEN: self._read_skill(JENSEN_SKILL_PATH),
            Speaker.LEX: self._read_skill(LEX_SKILL_PATH),
        }

        # Initialize LLM client (OpenAI-compatible for Ark coding endpoint)
        self.protocol = _env("API_PROTOCOL", "openai")  # openai (default) or anthropic

        # Prefer generic env names; fall back to ARK_* aliases for compatibility.
        primary_key = _env("API_KEY") or _env("ARK_API_KEY") or ARK_API_KEY
        primary_base = _env("API_BASE_URL") or _env("ARK_BASE_URL") or ARK_BASE_URL
        primary_model = _env("MODEL") or _env("ARK_MODEL") or ARK_MODEL

        # Sensible defaults when base/model omitted.
        if not primary_base:
            primary_base = "https://ark.cn-beijing.volces.com/api/coding/v3"
        if not primary_model:
            primary_model = "ark-code-latest"

        self.api_key = primary_key
        self.base_url = primary_base
        self.model = primary_model

        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set API_KEY (preferred) or ARK_API_KEY in environment/.env."
            )

        self._primary_client: OpenAI
        self._primary_model = primary_model
        self._fallback_client: Optional[OpenAI] = None
        self._fallback_model: Optional[str] = None
        self._using_fallback = False

        if self.protocol == "anthropic":
            try:
                from anthropic import Anthropic  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    "Anthropic protocol selected but 'anthropic' package is not installed. "
                    "Please add it to requirements and reinstall."
                ) from e

            # Ark provides an Anthropic-compatible API endpoint.
            # Anthropic SDK supports overriding base_url for compatible gateways.
            self.client = Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            self._primary_client = OpenAI(api_key=primary_key, base_url=primary_base)
            self.client = self._primary_client

            disabled = (_env("LLM_FALLBACK_DISABLED") or "").lower() in ("1", "true", "yes")
            fb_base = _env("LLM_FALLBACK_BASE_URL", "http://127.0.0.1:30023/v1")
            fb_key = _env("LLM_FALLBACK_API_KEY", "my-local-secret-key")
            fb_model = _env("LLM_FALLBACK_MODEL", "qwen3.5")
            if not disabled and fb_base and fb_key and fb_model:
                self._fallback_client = OpenAI(api_key=fb_key, base_url=fb_base)
                self._fallback_model = fb_model

        # In-memory storage for active runs
        self.runs: Dict[str, DebateRun] = {}

    def _read_skill(self, path: Path) -> str:
        """Read skill content from file, return empty if not exists"""
        if not path.exists():
            print(f"Warning: Skill file not found at {path}")
            return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading skill file {path}: {e}")
            return ""

    def _build_system_prompt(self, speaker: Speaker) -> str:
        """SKILL + 共享事实底盘 deep-research.md（与架构宪章一致）。"""
        skill_text = (self._skills.get(speaker) or "").strip()
        role = _speaker_zh(speaker)
        if not skill_text:
            skill_text = f"（角色文件未读入；请以 {role} 身份、基于事实底盘谨慎发言。）"

        parts: List[str] = [
            f"你现在需要扮演 **{role}**，严格遵循下列角色技能文档中的思维框架与表达要求：\n\n{skill_text}",
        ]
        dr = (self.deep_research or "").strip()
        if dr:
            parts.append(
                "\n\n---\n\n【共享事实底盘 — 全文】\n"
                "以下为 `docs/background/deep-research.md` 合并正文；心里有数即可，**口语里不必句句挂「§几」**。\n\n"
                f"{dr}"
            )
        parts.append("\n\n" + ORAL_FORUM_CONTRACT_ZH.strip())
        parts.append("\n\n接下来只根据本回合 user 指令发言；不要编造文档未支持的具体数字。")
        return "".join(parts)

    def create_new_run(self) -> str:
        """Create a new debate run and start background execution"""
        run_id = str(uuid.uuid4())
        run = DebateRun(
            run_id=run_id,
            status=RunStatus.RUNNING,
            topic=DEBATE_TOPIC,
            turns=[],
        )
        self.runs[run_id] = run
        return run_id

    async def run_debate(self, run_id: str) -> None:
        """Execute the debate sequence turn by turn"""
        run = self.runs.get(run_id)
        if not run:
            return

        try:
            last_text_by_speaker: Dict[Speaker, str] = {}
            last_speaker: Optional[Speaker] = None
            for i, (speaker, base_prompt) in enumerate(DIALOGUE_TURNS, 1):
                if run.status != RunStatus.RUNNING:
                    break
                if run.skip_to_jensen:
                    break

                system_prompt = self._build_system_prompt(speaker)
                opponent_name = _speaker_zh(last_speaker) if last_speaker else ""
                opponent_last = last_text_by_speaker.get(last_speaker) if last_speaker else None
                user_prompt = f"{base_prompt}{_interaction_wrapper(opponent_name, opponent_last)}"

                response_text = await self._call_llm(
                    system_prompt,
                    user_prompt,
                    temperature=FORUM_LLM_TEMPERATURE,
                )
                if response_text is None:
                    run.status = RunStatus.ERROR
                    run.error = f"第 {i} 轮（{speaker}）未能获取模型回复：请检查 API 配置、网络或模型可用性。"
                    self._save_result(run)
                    return

                response_text = _clean_model_output(response_text)
                response_text = _clean_forum_live(response_text or "", speaker=speaker)
                response_text = response_text.strip()

                # Add turn
                turn = Turn(
                    round=(i + 1) // 2,  # 1,1,2,2,3,3
                    speaker=speaker,
                    text=response_text,
                    created_at=time.time(),
                    kind="forum",
                )
                run.turns.append(turn)
                last_text_by_speaker[speaker] = turn.text
                last_speaker = speaker

                # Slow down text output so UI doesn't race ahead of audio playback.
                await asyncio.sleep(DISPLAY_DELAY_SECONDS_PER_TURN)

            if run.status == RunStatus.RUNNING:
                await self._append_jensen_vc_turn(run)
            if run.status == RunStatus.RUNNING:
                await self._append_liptan_tag_turn(run)

            if run.status == RunStatus.RUNNING:
                run.status = RunStatus.DONE
                run.finished_at = time.time()
            self._save_result(run)

        except Exception as e:
            run.status = RunStatus.ERROR
            run.error = f"Unexpected error: {str(e)}"
            self._save_result(run)

    async def _append_jensen_vc_turn(self, run: DebateRun) -> None:
        """阶段二：黄仁勋视频串场闭幕独白（叠 Jensen SKILL + jensen-closing-speech 弹药）。"""
        ammo = self._read_skill(JENSEN_CLOSING_PATH).strip()
        if not ammo:
            print("Warning: jensen-closing-speech.md missing or empty")
            ammo = "（弹药文件缺失；仍请按 Jensen SKILL 完成闭幕独白。）"
        transcript = _format_turns_transcript_zh(run.turns)
        _jvc_tmax = 12000
        if len(transcript) > _jvc_tmax:
            transcript = "…[论坛前段已省略以加速串场]\n" + transcript[-_jvc_tmax:]
        user = _jensen_vc_user_prompt(transcript, ammo)
        system = self._build_system_prompt(Speaker.JENSEN)
        _jvc_smax = 28000
        if len(system) > _jvc_smax:
            system = system[:_jvc_smax].rstrip() + "\n\n[为串场独白加速：system 尾部已截断]\n"
        raw = await self._call_llm(
            system,
            user,
            temperature=FORUM_LLM_TEMPERATURE,
            max_tokens=min(600, MAX_RESPONSE_TOKENS + 200),
        )
        if not raw:
            run.status = RunStatus.ERROR
            run.error = "黄仁勋（视频串场）独白生成失败：模型无返回或 API 异常。"
            return
        fixed = _ensure_jensen_golden_line(_clean_model_output(raw))
        fixed = _clean_forum_live(fixed or "", speaker=Speaker.JENSEN).strip()
        run.turns.append(
            Turn(
                round=4,
                speaker=Speaker.JENSEN,
                text=fixed,
                created_at=time.time(),
                kind="jensen_vc",
            )
        )
        await asyncio.sleep(DISPLAY_DELAY_SECONDS_PER_TURN)

    async def _append_liptan_tag_turn(self, run: DebateRun) -> None:
        """黄仁勋之后：陈立武一句收束（吴伟不再接话）。"""
        text = (
            "Jensen，您刚那段我听见了。**说白了：我们都没赢——因为这场仗才刚开始。**"
            "对，**这场仗才刚开始**；后面拼的是量产节奏、现金流、还有客户用脚投票，咱们别把终局今天就判死。"
        )
        cleaned = _clean_forum_live(text, speaker=Speaker.LIPTAN).strip()
        run.turns.append(
            Turn(
                round=5,
                speaker=Speaker.LIPTAN,
                text=cleaned,
                created_at=time.time(),
                kind="liptan_tag",
            )
        )
        await asyncio.sleep(DISPLAY_DELAY_SECONDS_PER_TURN)

    def request_skip_to_jensen(self, run_id: str) -> bool:
        run = self.runs.get(run_id)
        if not run or run.status != RunStatus.RUNNING:
            return False
        run.skip_to_jensen = True
        return True

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = MAX_RESPONSE_TOKENS,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """Call LLM with error handling (supports 2 protocols)."""
        if self.protocol == "anthropic":
            t = temperature if temperature is not None else DEFAULT_LLM_TEMPERATURE
            return await asyncio.to_thread(
                self._call_anthropic, system_prompt, user_prompt, max_tokens, t
            )
        return await asyncio.to_thread(
            self._call_openai,
            system_prompt,
            user_prompt,
            max_tokens,
            temperature if temperature is not None else DEFAULT_LLM_TEMPERATURE,
        )

    def _openai_chat_with_quota_fallback(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
    ) -> Optional[str]:
        """Primary = Volcengine Ark; on 429 / AccountQuotaExceeded switch to local OpenAI-compatible (e.g. Qwen)."""
        if self.protocol != "openai":
            return None

        def _create(client: OpenAI, model: str):
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if self._using_fallback:
            if not self._fallback_client or not self._fallback_model:
                print("[LLM] 已标记为后备模式，但未配置 LLM_FALLBACK_*")
                return None
            try:
                response = _create(self._fallback_client, self._fallback_model)
                return response.choices[0].message.content
            except AuthenticationError:
                print("[LLM] 后备模型鉴权失败")
                return None
            except Exception as e:
                print(f"[LLM] 后备模型调用失败: {e}")
                return None

        try:
            response = _create(self._primary_client, self._primary_model)
            return response.choices[0].message.content
        except AuthenticationError:
            print("API Authentication failed")
            return None
        except APIConnectionError as e:
            print(f"API Connection error: {e}")
            return None
        except (RateLimitError, APIError) as e:
            if self._fallback_client and self._fallback_model and _is_volcengine_quota_exhausted(e):
                print(f"[LLM] 火山引擎配额或限流，自动切换到本地后备模型 {self._fallback_model!r}（{e!s}）")
                self._using_fallback = True
                self.model = self._fallback_model
                self.client = self._fallback_client
                try:
                    response = _create(self._fallback_client, self._fallback_model)
                    return response.choices[0].message.content
                except Exception as e2:
                    print(f"[LLM] 本地后备模型调用失败: {e2}")
                    return None
            print(f"API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected LLM error: {e}")
            return None

    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = MAX_RESPONSE_TOKENS,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
    ) -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._openai_chat_with_quota_fallback(messages, max_tokens, temperature)

    def _call_openai_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
    ) -> Optional[str]:
        return self._openai_chat_with_quota_fallback(messages, max_tokens, temperature)

    def _call_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = MAX_RESPONSE_TOKENS,
        temperature: float = 0.7,
    ) -> Optional[str]:
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # SDK returns a list of content blocks; we join text blocks.
            parts = []
            for block in getattr(message, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            return "\n".join(parts).strip() if parts else None
        except Exception as e:
            print(f"Anthropic-compatible API error: {e}")
            return None

    def _save_result(self, run: DebateRun) -> None:
        """Save the final debate result to docs/_archieved_mds/debate_result.md"""
        output_dir = PROJECT_ROOT / "docs" / "_archieved_mds"
        output_path = output_dir / "debate_result.md"
        output_dir.mkdir(parents=True, exist_ok=True)

        judge_md: Optional[str] = None
        if run.status == RunStatus.DONE and run.turns:
            try:
                lex_body = self._skills.get(Speaker.LEX, "") or ""
                judge_text = (
                    self._call_openai(
                        _lex_review_system_prompt(lex_body),
                        _lex_review_user_prompt(run.topic, run.turns),
                        JUDGE_MAX_RESPONSE_TOKENS,
                        JUDGE_LLM_TEMPERATURE,
                    )
                    if self.protocol != "anthropic"
                    else self._call_anthropic(
                        _lex_review_system_prompt(lex_body),
                        _lex_review_user_prompt(run.topic, run.turns),
                        JUDGE_MAX_RESPONSE_TOKENS,
                        JUDGE_LLM_TEMPERATURE,
                    )
                )
                if judge_text:
                    judge_md = _clean_forum_live(_clean_model_output(judge_text).strip())
                    run.judge_result = judge_md  # store for frontend display
            except Exception as e:
                judge_md = f"对比小结生成失败：{e}"
                run.judge_result = judge_md

        # Build markdown
        lines = []
        lines.append("# 论坛交锋纪要：RISC-V vs x86 vs ARM")
        lines.append("")
        lines.append(f"**主题**：{run.topic}")
        lines.append("")
        lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        model_line = (
            f"{self._primary_model} → {self._fallback_model}（火山配额/限流后已切换本地后备）"
            if self._using_fallback and self._fallback_model
            else self.model
        )
        lines.append(f"**模型**：{model_line}")
        lines.append("")
        lines.append("---")
        lines.append("")

        current_round = 0
        for turn in run.turns:
            if turn.round != current_round:
                current_round = turn.round
                k = getattr(turn, "kind", "forum") or "forum"
                if k == "jensen_vc":
                    lines.append("## 黄仁勋 · 视频串场（示意）")
                elif k == "liptan_tag":
                    lines.append("## 陈立武 · 散场接话")
                else:
                    lines.append(f"## 第 {current_round} 轮")
                lines.append("")

            speaker_name = _speaker_zh(turn.speaker)
            lines.append(f"### {speaker_name}")
            lines.append("")
            lines.append(turn.text)
            lines.append("")

        if judge_md:
            lines.append("---")
            lines.append("")
            lines.append("## Lex 锐评")
            lines.append("")
            lines.append(judge_md)
            lines.append("")

        if run.status == RunStatus.ERROR and run.error:
            lines.append("---")
            lines.append("")
            lines.append(f"**错误**：{run.error}")
            lines.append("")

        if run.status == RunStatus.DONE:
            lines.append("---")
            lines.append("")
            lines.append("对谈完成")

        # Write to file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print(f"Debate saved to {output_path}")
        except Exception as e:
            print(f"Failed to save result: {e}")

    def get_run_status(self, run_id: str) -> Optional[DebateRun]:
        """Get current status of a debate run"""
        return self.runs.get(run_id)

    def get_result_markdown(self, run_id: str) -> Optional[str]:
        """Read the saved result markdown"""
        result_path = PROJECT_ROOT / "docs" / "_archieved_mds" / "debate_result.md"
        if not result_path.exists():
            return None
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    def get_current_run(self) -> Optional[DebateRun]:
        """Get the current active run (for TTS to consume)"""
        if not self.runs:
            return None
        # Get the last run (the one currently being played)
        last_run_id = list(self.runs.keys())[-1]
        return self.runs[last_run_id]

    async def chat_with_debater(
        self,
        run_id: str,
        target_speaker: Speaker,
        user_message: str,
    ) -> Optional[str]:
        """Continue chat with selected debater, shared room context.
        All messages (user + all assistants) in a single chat_history per run.
        """
        run = self.runs.get(run_id)
        if not run:
            return None

        # Build system prompt same as debate (reuse skill for the answering speaker)
        system_prompt = self._build_system_prompt(target_speaker)

        # Only for the first master-chat turn ever in this run: set the discussion scene once.
        # Keep it short to avoid prompt bloat across turns.
        first_turn_user_context = (
            "【对话场景设定（仅本次会话首次注入）】\n"
            "台下是公众科学日分会场延续交流：观众刚听完圆桌，现在向你追问。像在**现场被人拦住聊两句**——口语、有停顿感，"
            "可严谨但别念论文；不要用「Q1」「1）共识」体，也不要在正文里写 @人名 传棒。\n"
            "【身份相关性规则】\n"
            "- 若问题与提问者身份/语境无关：完全忽略其身份，不要硬扯。\n"
            "- 只有当问题与中国语境/政策含义/案例选择直接相关时：才可简短点到提问者语境（最多一句），其余仍以理论与机制为主。\n"
            "【表达约束】不做空泛口号；若引入假设或外部事实，请明确标注为「假设/示例」。"
        )
        is_first_chat_turn = len(run.chat_history) == 0

        # Build openai messages array with full shared-room history as context.
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if is_first_chat_turn:
            messages.append({"role": "system", "content": first_turn_user_context})

        # Each historical message:
        # - User → {"role":"user", "content": content}
        # - Assistant → {"role":"assistant", "content": "【Master Name】content"}
        #   so that the next answering master knows who said what earlier in the shared room.
        for msg in run.chat_history:
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            else:
                # assistant from previous turn (could be different master)
                assert msg.speaker in (
                    Speaker.LEX.value,
                    Speaker.WUWEI.value,
                    Speaker.LIPTAN.value,
                    Speaker.COOK.value,
                    Speaker.JENSEN.value,
                )
                sp = Speaker(msg.speaker)
                speaker_name = _speaker_zh(sp)
                prefixed = f"【{speaker_name}】{msg.content}"
                messages.append({"role": "assistant", "content": prefixed})

        # Finally, prepend the debate transcript to the current question.
        full_question_lines: List[str] = []
        full_question_lines.append("### 当前已经完成的三轮对谈全文（参考上下文）")
        for t in run.turns:
            name = _speaker_zh(t.speaker)
            full_question_lines.append(f"**{name}**: {t.text}")
        full_question_lines.append("")
        full_question_lines.append(f"### 当前这轮：你是{_speaker_zh(target_speaker)}，需要你回答用户的问题。")
        full_question_lines.append(
            "这场对话是一个共享会场，所有之前的对话（包括提问与其他嘉宾的回答）你都能看见。此轮只需要你作答即可。"
        )
        full_question_lines.append("")
        full_question_lines.append(f"**用户问题**: {user_message}")
        full_question_lines.append("")
        full_question_lines.append(
            f"请以你的身份回应：口语自然，**{RESPONSE_LEN_HINT_ZH}** "
            "可加粗一两处真正要敲黑板的地方；不要写 @人名 / →@ 传棒。"
        )
        messages.append({"role": "user", "content": "\n".join(full_question_lines)})

        # Call LLM
        reply: Optional[str] = None
        if self.protocol == "anthropic":
            # Protocol is forced to openai elsewhere; this is fallback.
            reply = self._call_anthropic(system_prompt, "\n".join(full_question_lines), CHAT_MAX_RESPONSE_TOKENS)
        else:
            reply = self._call_openai_messages(messages, CHAT_MAX_RESPONSE_TOKENS)

        if reply is None:
            return None

        # Clean boilerplate disclaimer + oral/TTS hygiene (same as论坛交锋)
        cleaned = _clean_forum_live(_clean_model_output(reply) or "", speaker=target_speaker)

        # Append to shared room: user message first, then assistant reply.
        from datetime import datetime
        now_ts = datetime.now().timestamp()
        run.chat_history.append(
            ChatMessage(
                role="user",
                speaker="user",
                target_speaker=target_speaker.value if hasattr(target_speaker, 'value') else target_speaker,
                content=user_message,
                created_at=now_ts,
            )
        )
        if cleaned:
            run.chat_history.append(
                ChatMessage(
                    role="assistant",
                    speaker=target_speaker.value if hasattr(target_speaker, 'value') else target_speaker,
                    content=cleaned,
                    created_at=now_ts,
                )
            )

        return cleaned


# Singleton instance
runner = DebateRunner()
