import os
import time
import uuid
import asyncio
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError, AuthenticationError, RateLimitError
from .models import DebateRun, RunStatus, Turn, Speaker, ChatMessage

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Hardcoded API config (as requested)
# 调用一下火山的模型
ARK_API_KEY = "ark-da654523-f2ad-42e4-9a13-c33d664f9fc5-d83b0"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_MODEL = "ark-code-latest"

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


JERVIS_SKILL_PATH = _skill_path("DIDI_SKILL_PATH", PROJECT_ROOT / "docs" / "didi-case-research-SKILL.md")
MEARSHEIMER_SKILL_PATH = _skill_path("MANUS_SKILL_PATH", PROJECT_ROOT / "docs" / "manus-case-research-SKILL.md")

# Dialogue topic
DEBATE_TOPIC = "滴滴数据安全案 vs Manus案：国家安全与数据/技术跨境治理的对比研究"

MAX_RESPONSE_TOKENS = 400
RESPONSE_LEN_HINT_ZH = "严格控制在150字以内。"
DISPLAY_DELAY_SECONDS_PER_TURN = 7.0

# Judge output needs to be longer than debater turns; otherwise it gets cut off.
JUDGE_MAX_RESPONSE_TOKENS = 500

# Master chat should allow longer, multi-turn replies.
CHAT_MAX_RESPONSE_TOKENS = 500


def _speaker_zh(speaker: Speaker) -> str:
    return "滴滴 Researcher" if speaker == Speaker.JERVIS else "Manus Researcher"


def _interaction_wrapper(opponent_name_zh: str, opponent_last: Optional[str]) -> str:
    if not opponent_last:
        return ""
    return (
        f"\n\n【对方刚刚的发言（请逐点回应，不要忽略）】\n"
        f"{opponent_name_zh}：\n{opponent_last}\n"
    )


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


# The 6-turn dialogue sequence (3 rounds), Manus Researcher speaks first.
# Each turn will be wrapped with the opponent's immediately previous message to enforce interaction.
DIALOGUE_TURNS: List[Tuple[Speaker, str]] = [
    # Round 1: align on facts & key disputes
    (Speaker.MEARSHEIMER, (
        "你是Manus Researcher。第1轮请先发言：用统一框架把Manus案的“已确认事实脉络/信息不足点/关键争点”讲清楚。"
        "要求：尽量可核验，不编造；明确标注“已确认/信息不足/推断”。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.JERVIS, (
        "你是滴滴 Researcher。第1轮回应：用同一框架梳理滴滴案，并对照Manus案补齐“共同的监管逻辑/不同的信息状态”。"
        "要求：唱和式补充，不要变成胜负评判；指出1-2个最关键的可比维度。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
    # Round 2: risk elements & governance moves
    (Speaker.MEARSHEIMER, (
        "你是Manus Researcher。第2轮：围绕“国家安全风险要素与治理抓手”做要素拆解（2-4条），并明确："
        "1) 你这案里最像滴滴案的点；2) 最不像的点；3) 你希望对方补充核验的材料清单。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.JERVIS, (
        "你是滴滴 Researcher。第2轮：用同一维度拆解滴滴案，并回应对方提出的“最像/最不像”判断："
        "补充你的边界条件与反例，给出1个“如果换成不同数据类型/主体结构会如何”的可检验预测。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
    # Round 3: research agenda & falsifiable predictions
    (Speaker.MEARSHEIMER, (
        "你是Manus Researcher。第3轮：输出一个“研究议程”小结："
        "给出2-3条可证伪的研究命题/预测（每条说明可用什么公开材料验证），并提出1个对政策制定者的含义。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
    (Speaker.JERVIS, (
        "你是滴滴 Researcher。第3轮：在承接对方研究议程的基础上，给出你的2-3条研究命题/预测，并用一句话总结："
        "这两个案例共同揭示了什么样的国家安全治理范式。"
        "\n\n请用markdown formatting增强可读性：**加粗关键点**，分段与编号，降低阅读负担。"
        f"{RESPONSE_LEN_HINT_ZH}"
    )),
]


def _judge_system_prompt() -> str:
    return (
        "你是CaseComparator（双案例对比摘要器）。你的目标不是评判胜负，而是把两位研究者的对谈"
        "提炼成可用于写论文/政策备忘录的“异同对比+研究议程”。"
        "不要引入外部事实核查；只基于对谈文本做归纳，明确区分“对谈中已确认事实/推断/待核验点”。"
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
        f"以下是三轮对谈全文：\n{transcript}\n\n"
        "请按模板输出“对比小结”，只基于对谈内容做归纳（不要引入外部事实核查）。\n"
        "输出必须严格按下面模板（不要加多余段落/说明），并用markdown增强可读性：\n"
        "- 只用 **加粗**（不要用表情、不要用代码块）\n"
        "- 分行、分段，降低阅读负担\n"
        "- 用 1/2/3/4 编号形成层次\n\n"
        "1) **相同点（3-6条）**\n"
        "- ...\n\n"
        "2) **不同点（3-6条）**\n"
        "- ...\n\n"
        "3) **关键争点与待核验清单（3-6条）**\n"
        "- ...\n\n"
        "4) **研究议程（可证伪命题/预测，3-6条）**\n"
        "- 每条写明“如何用公开材料验证/推翻”\n"
    )


class DebateRunner:
    def __init__(self):
        # Read skills on initialization
        self.jervis_skill = self._read_skill(JERVIS_SKILL_PATH)
        self.mearsheimer_skill = self._read_skill(MEARSHEIMER_SKILL_PATH)

        # Initialize LLM client (OpenAI-compatible for Ark coding endpoint)
        self.protocol = "openai"  # For Ark https://ark.cn-beijing.volces.com/api/coding/v3 which is OpenAI-compatible
        primary_key = _env("ARK_API_KEY") or ARK_API_KEY
        primary_base = _env("ARK_BASE_URL") or ARK_BASE_URL
        primary_model = _env("ARK_MODEL") or ARK_MODEL
        self.api_key = primary_key
        self.base_url = primary_base
        self.model = primary_model

        if not self.api_key:
            raise RuntimeError("Missing API_KEY")

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
        """Build system prompt combining the skill rules and role"""
        if speaker == Speaker.JERVIS:
            skill_text = self.jervis_skill
            prefix = "你现在需要扮演滴滴 Researcher，严格遵循以下思维框架和表达方式：\n\n"
        else:
            skill_text = self.mearsheimer_skill
            prefix = "你现在需要扮演Manus Researcher，严格遵循以下思维框架和表达方式：\n\n"

        # If skill is empty, just use the basic role
        if not skill_text:
            if speaker == Speaker.JERVIS:
                return "你是滴滴 Researcher，专注滴滴数据安全案的案例研究者。"
            else:
                return "你是Manus Researcher，专注Manus案的案例研究者。"

        return f"{prefix}{skill_text}\n\n接下来请根据用户的问题扮演这个角色进行案例研究对谈。"

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
            for i, (speaker, base_prompt) in enumerate(DIALOGUE_TURNS, 1):
                if run.status != RunStatus.RUNNING:
                    break

                system_prompt = self._build_system_prompt(speaker)
                opponent = Speaker.MEARSHEIMER if speaker == Speaker.JERVIS else Speaker.JERVIS
                opponent_last = last_text_by_speaker.get(opponent)
                user_prompt = f"{base_prompt}{_interaction_wrapper(_speaker_zh(opponent), opponent_last)}"

                response_text = await self._call_llm(system_prompt, user_prompt)
                if response_text is None:
                    run.status = RunStatus.ERROR
                    run.error = f"第 {i} 轮（{speaker}）未能获取模型回复：请检查 API 配置、网络或模型可用性。"
                    self._save_result(run)
                    return

                response_text = _clean_model_output(response_text)
                response_text = (response_text or "").strip()

                # Ensure first round explicitly self-identifies (deterministic UX).
                # Round 1 has two turns: i=1 (Mearsheimer) and i=2 (Jervis).
                if i == 1:
                    response_text = f"【我是 Manus Researcher】\n\n{response_text}"
                elif i == 2:
                    response_text = f"【我是 滴滴 Researcher】\n\n{response_text}"

                # Add turn
                turn = Turn(
                    round=(i + 1) // 2,  # 1,1,2,2,3,3
                    speaker=speaker,
                    text=response_text,
                    created_at=time.time(),
                )
                run.turns.append(turn)
                last_text_by_speaker[speaker] = turn.text

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

    async def _call_llm(self, system_prompt: str, user_prompt: str, *, max_tokens: int = MAX_RESPONSE_TOKENS) -> Optional[str]:
        """Call LLM with error handling (supports 2 protocols)."""
        if self.protocol == "anthropic":
            return await asyncio.to_thread(self._call_anthropic, system_prompt, user_prompt, max_tokens)
        return await asyncio.to_thread(self._call_openai, system_prompt, user_prompt, max_tokens)

    def _openai_chat_with_quota_fallback(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ) -> Optional[str]:
        """Primary = Volcengine Ark; on 429 / AccountQuotaExceeded switch to local OpenAI-compatible (e.g. Qwen)."""
        if self.protocol != "openai":
            return None

        def _create(client: OpenAI, model: str):
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
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

    def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int = MAX_RESPONSE_TOKENS) -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._openai_chat_with_quota_fallback(messages, max_tokens)

    def _call_openai_messages(self, messages: List[Dict[str, str]], max_tokens: int) -> Optional[str]:
        return self._openai_chat_with_quota_fallback(messages, max_tokens)

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
        """Save the final debate result to docs/debate_result.md"""
        output_dir = PROJECT_ROOT / "docs"
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
                    judge_md = judge_text.strip()
                    run.judge_result = judge_md  # store for frontend display
            except Exception as e:
                judge_md = f"对比小结生成失败：{e}"
                run.judge_result = judge_md

        # Build markdown
        lines = []
        lines.append("# 案例研究对谈纪要：滴滴数据安全案 vs Manus案")
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
            lines.append("## 对比小结")
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
        result_path = PROJECT_ROOT / "docs" / "debate_result.md"
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
            "你在与一位中国的国家安全学方向博士生进行学术讨论。整体风格要求：严谨、可证伪、术语清晰、尽量用“主张-机制-证据/可检验预测-反例边界”结构。\n"
            "【身份相关性规则】\n"
            "- 若问题与提问者身份/语境无关：完全忽略其身份，不要硬扯。\n"
            "- 只有当问题与中国语境/政策含义/案例选择直接相关时：才可简短点到提问者语境（最多一句），其余仍以理论与机制为主。\n"
            "【表达约束】不做空泛口号，不堆砌名词；若引入假设或外部事实，请明确标注为“假设/示例”。"
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
                assert msg.speaker in ("jervis", "mearsheimer")
                sp: Speaker = msg.speaker  # type: ignore
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
        full_question_lines.append("这场对话是一个共享会场，所有之前的对话（包括提问和另外一位大师的回答）你都能看见。此轮只需要你作答即可。")
        full_question_lines.append("")
        full_question_lines.append(f"**用户问题**: {user_message}")
        full_question_lines.append("")
        full_question_lines.append(
            "请以你的身份回应，用markdown加粗重点，保持层次感，允许展开到300-400字。"
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

        # Clean boilerplate disclaimer
        cleaned = _clean_model_output(reply)

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
