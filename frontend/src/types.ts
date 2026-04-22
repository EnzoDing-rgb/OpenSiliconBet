export type Speaker = "jervis" | "mearsheimer";
export type RunStatus = "running" | "done" | "error";

export interface Turn {
  round: number;
  speaker: Speaker;
  text: string;
  created_at: number;
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
