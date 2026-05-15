import type { StartDebateResponse, DebateStatusResponse, DebateResultResponse, Speaker, ChatResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export async function startDebate(): Promise<string> {
  const response = await fetch(`${API_BASE}/debate/start`, {
    method: 'POST',
  });
  const data: StartDebateResponse = await response.json();
  return data.run_id;
}

export async function skipForumToJensen(runId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/debate/skip-forum/${runId}`, { method: 'POST' });
  const data = (await response.json()) as { ok?: boolean };
  return !!data.ok;
}

export async function getDebateStatus(runId: string): Promise<DebateStatusResponse> {
  const response = await fetch(`${API_BASE}/debate/status/${runId}`);
  return await response.json();
}

export async function getDebateResult(runId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/debate/result/${runId}`);
  const data: DebateResultResponse = await response.json();
  return data.content || '';
}

export async function postChat(runId: string, speaker: Speaker, message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/debate/chat/${runId}`, {
    method: 'POST',
    headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ speaker, message }),
  });
  return await response.json();
}

export async function triggerLexReview(runId: string): Promise<string | null> {
  const response = await fetch(`${API_BASE}/debate/trigger-lex-review/${runId}`, {
    method: 'POST',
  });
  const data = await response.json() as { judge_result?: string };
  return data.judge_result ?? null;
}

export async function postBetVote(camp: string): Promise<{ riscv: number; x86: number; arm: number }> {
  const response = await fetch(`${API_BASE}/bet/vote?camp=${encodeURIComponent(camp)}`, {
    method: 'POST',
  })
  return await response.json()
}

export async function getBetState(): Promise<{ riscv: number; x86: number; arm: number }> {
  const response = await fetch(`${API_BASE}/bet/state`)
  return await response.json()
}

export async function postBetReset(): Promise<{ riscv: number; x86: number; arm: number }> {
  const response = await fetch(`${API_BASE}/bet/reset`, { method: 'POST' })
  return await response.json()
}

export function downloadMarkdown(content: string, filename: string = 'debate_result.md') {
  const blob = new Blob([content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
