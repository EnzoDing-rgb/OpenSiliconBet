import type { StartDebateResponse, DebateStatusResponse, DebateResultResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export async function startDebate(): Promise<string> {
  const response = await fetch(`${API_BASE}/debate/start`, {
    method: 'POST',
  });
  const data: StartDebateResponse = await response.json();
  return data.run_id;
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
