import os
import time
import uuid
import asyncio
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError, AuthenticationError
from .models import DebateRun, RunStatus, Turn, Speaker, ChatMessage

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Hardcoded API config (as requested)
ARK_API_KEY = "ark-da654523-f2ad-42e4-9a13-c33d664f9fc5-d83b0"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_MODEL = "ark-code-latest"

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default

# Skill file paths (relative to project root)
PROJECT_ROOT = Path(os.path.dirname(__file__)).parent
JERVIS_SKILL_PATH = PROJECT_ROOT / ".agents" / "skills" / "robert-jervis-perspective" / "SKILL.md"
MEARSHEIMER_SKILL_PATH = PROJECT_ROOT / ".agents" / "skills" / "john-mearsheimer-perspective" / "SKILL.md"

# Debate topic and prompts from prompt.md
DEBATE_TOPIC = "《知觉与错误知觉》：错误知觉是国际冲突的独立原因吗？"

MAX_RESPONSE_TOKENS = 400
RESPONSE_LEN_HINT_ZH = "严格控制在150字以内。"
DISPLAY_DELAY_SECONDS_PER_TURN = 7.0

# Judge output needs to be longer than debater turns; otherwise it gets cut off.
JUDGE_MAX_RESPONSE_TOKENS = 500

# Master chat should allow longer, multi-turn replies.
CHAT_MAX_RESPONSE_TOKENS = 500


def _speaker_zh(speaker: Speaker) -> str:
    return "罗伯特·杰维斯" if speaker == Speaker.JERVIS else "约翰·米尔斯海默"


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


# The 6-turn debate sequence (3 rounds), Mearsheimer starts the challenge.
# Each turn will be wrapped with the opponent's immediately previous message to enforce interaction.
DEBATE_TURNS: List[Tuple[Speaker, str]] = [
    (Speaker.MEARSHEIMER, f"你是约翰·米尔斯海默。请先发难：用进攻性现实主义的核心假设，质疑“错误知觉是独立原因”的命题。要点化、锋利、给出1个反例或预测。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
    (Speaker.JERVIS, f"你是罗伯特·杰维斯。请直接回应对方最强的2个论点：指出其遗漏的因果链条，并给出1个具体机制（如安全困境/镜像图像）。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
    (Speaker.MEARSHEIMER, f"你是约翰·米尔斯海默。继续追击：指出对方机制解释不了的结构性规律，并攻击其方法论/可证伪性。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
    (Speaker.JERVIS, f"你是罗伯特·杰维斯。反击：用“同一结构下不同结果/同一信息下不同判断”说明认知变量的独立性，并承认1个结构约束但解释为何不足。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
    (Speaker.MEARSHEIMER, f"你是约翰·米尔斯海默。做最后陈词：用一句话定性对方理论的边界，再给出你的总判断与政策含义。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
    (Speaker.JERVIS, f"你是罗伯特·杰维斯。做最后陈词：承认1点对方批评成立，但明确你理论不可替代的核心洞见与对决策者的警示。\n\n请用markdown formatting增加层次感：**加粗核心论点**，分段阐述，降低阅读负担。{RESPONSE_LEN_HINT_ZH}"),
]


def _judge_system_prompt() -> str:
    return (
        "你是客观公正的辩论裁判。你的目标是基于文本质量给出评分与胜负判断，"
        "不偏袒任何一方，不引入外部事实核查。"
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
        f"以下是三轮交锋全文：\n{transcript}\n\n"
        "请你从3个维度评分（每项0-10分，可带0.5）：\n"
        "1) 论证力度（主张-理由-反驳链条是否完整有力）\n"
        "2) 贴题与回应度（是否紧扣题目、是否逐点回应对手）\n"
        "3) 清晰与说服力（表达是否清楚、是否有抓手）\n\n"
        "输出必须严格按下面模板（不要加多余段落/说明），并用markdown增强可读性：\n"
        "- 只用 **加粗**（不要用表情、不要用代码块）\n"
        "- 分行、分段，降低阅读负担\n"
        "- 用 1/2/3/4 编号形成层次\n\n"
        "1) **维度评分**\n"
        "- **杰维斯**：论证x/10，回应x/10，清晰x/10，总分**x/30**\n"
        "- **米尔斯海默**：论证x/10，回应x/10，清晰x/10，总分**x/30**\n\n"
        "2) **胜者**\n"
        "<杰维斯/米尔斯海默/平局>\n\n"
        "3) **判词**\n"
        "<120字以内，点出胜负关键>\n\n"
        "4) **总结**\n"
        "- **杰维斯**\n"
        "  - 优点(strong)：<400字以内>\n"
        "  - 缺点(weak)：<400字以内>\n"
        "- **米尔斯海默**\n"
        "  - 优点(strong)：<400字以内>\n"
        "  - 缺点(weak)：<400字以内>\n"
    )


class DebateRunner:
    def __init__(self):
        # Read skills on initialization
        self.jervis_skill = self._read_skill(JERVIS_SKILL_PATH)
        self.mearsheimer_skill = self._read_skill(MEARSHEIMER_SKILL_PATH)

        # Initialize LLM client (OpenAI-compatible for Ark coding endpoint)
        self.protocol = "openai"  # For Ark https://ark.cn-beijing.volces.com/api/coding/v3 which is OpenAI-compatible
        # Use hardcoded Ark config (overrides env)
        self.api_key = ARK_API_KEY
        self.base_url = ARK_BASE_URL
        self.model = ARK_MODEL

        if not self.api_key:
            raise RuntimeError("Missing API_KEY")

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
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

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
            prefix = "你现在需要扮演罗伯特·杰维斯，严格遵循以下思维框架和表达方式：\n\n"
        else:
            skill_text = self.mearsheimer_skill
            prefix = "你现在需要扮演约翰·米尔斯海默，严格遵循以下思维框架和表达方式：\n\n"

        # If skill is empty, just use the basic role
        if not skill_text:
            if speaker == Speaker.JERVIS:
                return "你是罗伯特·杰维斯，国际政治认知学派的代表学者，《知觉与错误知觉》作者。"
            else:
                return "你是约翰·米尔斯海默，进攻性现实主义代表学者。"

        return f"{prefix}{skill_text}\n\n接下来请根据用户的问题扮演这个角色进行辩论。"

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
            for i, (speaker, base_prompt) in enumerate(DEBATE_TURNS, 1):
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
                    response_text = f"【我是约翰·米尔斯海默】\n\n{response_text}"
                elif i == 2:
                    response_text = f"【我是罗伯特·杰维斯】\n\n{response_text}"

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

    def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int = MAX_RESPONSE_TOKENS) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except AuthenticationError:
            print("API Authentication failed")
            return None

    def _call_openai_messages(self, messages: List[Dict[str, str]], max_tokens: int) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except AuthenticationError:
            print("API Authentication failed")
            return None
        except APIConnectionError:
            print("API Connection error")
            return None
        except APIError as e:
            print(f"API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected LLM error: {e}")
            return None
        except APIConnectionError:
            print("API Connection error")
            return None
        except APIError as e:
            print(f"API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected LLM error: {e}")
            return None

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
                judge_md = f"裁判评分生成失败：{e}"
                run.judge_result = judge_md

        # Build markdown
        lines = []
        lines.append("# 辩论记录：罗伯特·杰维斯 vs 约翰·米尔斯海默")
        lines.append("")
        lines.append(f"**主题**：{run.topic}")
        lines.append("")
        lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**模型**：{self.model}")
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
            lines.append("## 裁判评分")
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
            lines.append("辩论完成")

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

        # Only for the first master-chat turn ever in this run: tell the assistant who the user is.
        first_turn_user_context = (
            "现在跟你对话的是一个国家政治领域国家安全学的博士生，来自中国。"
            "你可以在相关且有帮助时表达你对中国的鲜明观点；如果不相关就不要硬表达。"
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
        full_question_lines.append("### 当前已经完成的三轮辩论全文（参考上下文）")
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
