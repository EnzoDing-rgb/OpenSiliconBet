export type Speaker = "lex" | "wuwei" | "liptan" | "cook" | "jensen";
export type RunStatus = "running" | "done" | "error";

export interface Turn {
  round: number;
  speaker: Speaker;
  text: string;
  created_at: number;
  /** forum | jensen_vc | liptan_tag */
  kind?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  speaker: "user" | Speaker;
  target_speaker?: Speaker;
  content: string;
  created_at: number;
}

export interface ChatResponse {
  reply: string;
  chat_history: ChatMessage[];
}

export interface DebateStatusResponse {
  status: RunStatus;
  current_round: number;
  turns: Turn[];
  error?: string;
  judge_result?: string;
}

export interface StartDebateResponse {
  run_id: string;
}

export interface DebateResultResponse {
  content?: string;
  error?: string;
}
