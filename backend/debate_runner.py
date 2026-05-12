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

# Dialogue topic（论坛交锋 demo）
DEBATE_TOPIC = "RISC-V vs x86 vs ARM：Agent 时代的指令集与算力格局（中科院公众科学日分会场 · 论坛交锋）"

MAX_RESPONSE_TOKENS = 400
# 与宪章 GLOBAL 对齐：可见中文正文约 200 字（宁少勿灌水）
RESPONSE_LEN_HINT_ZH = "中文可见正文约 200 字以内；宁少勿堆字，密度优先。"
FORUM_LLM_TEMPERATURE = 0.88
DEFAULT_LLM_TEMPERATURE = 0.72
DISPLAY_DELAY_SECONDS_PER_TURN = 7.0

# Judge output needs to be longer than debater turns; otherwise it gets cut off.
JUDGE_MAX_RESPONSE_TOKENS = 500

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
- **禁止**在正文里出现传棒符号：`@人名`、`@无`、`→@`、`→ @` 等（接话顺序由系统安排）；想点名就口语直呼「老陈」「库克这边」之类自然带过即可。
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


def _judge_system_prompt() -> str:
    return (
        "你是现场主持人，散场前对着观众**口播收束**（这段也会给人读/念出来）。"
        "只基于下面 transcript，不要引入场外新事实。"
        "用**三四段短口语**：大家各自最硬的一个点、真正掐起来的一个分歧、两三件观众散场后可以自己去查证的事。"
        "不要用「1）2）3）」公文编号；不要写成咨询报告摘要。"
    )


def _judge_user_prompt(topic: str, turns: List["Turn"]) -> str:
    transcript_lines: List[str] = []
    current_round = 0
    for t in turns:
        if t.round != current_round:
            current_round = t.round
            transcript_lines.append(f"\n## 第 {current_round} 轮\n")
        transcript_lines.append(f"{_speaker_zh(t.speaker)}：{t.text}\n")

    transcript = "\n".join(transcript_lines).strip()
    return (
        f"主题：{topic}\n\n"
        f"以下是圆桌口语实录（可能略乱，但别帮嘉宾改口风）：\n{transcript}\n\n"
        "请你用**主持人散场口播**写出来：语气轻松、句子短；最多用 **一两处加粗** 帮观众抓住关键词。"
        "不要输出「1）2）3）」那种模板；不要替嘉宾补充他们没说过的硬数字。"
    )


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
                )
                run.turns.append(turn)
                last_text_by_speaker[speaker] = turn.text
                last_speaker = speaker

                # Slow down text output so UI doesn't race ahead of audio playback.
                await asyncio.sleep(DISPLAY_DELAY_SECONDS_PER_TURN)

            # Mark done
            run.status = RunStatus.DONE
            run.finished_at = time.time()
            self._save_result(run)

        except Exception as e:
            run.status = RunStatus.ERROR
            run.error = f"Unexpected error: {str(e)}"
            self._save_result(run)

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
            return await asyncio.to_thread(self._call_anthropic, system_prompt, user_prompt, max_tokens)
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

    def _call_anthropic(self, system_prompt: str, user_prompt: str, max_tokens: int = MAX_RESPONSE_TOKENS) -> Optional[str]:
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.7,
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
                judge_text = (
                    self._call_openai(
                        _judge_system_prompt(),
                        _judge_user_prompt(run.topic, run.turns),
                        JUDGE_MAX_RESPONSE_TOKENS,
                    )
                    if self.protocol != "anthropic"
                    else self._call_anthropic(
                        _judge_system_prompt(),
                        _judge_user_prompt(run.topic, run.turns),
                        JUDGE_MAX_RESPONSE_TOKENS,
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
            lines.append("## 论坛纪要")
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
