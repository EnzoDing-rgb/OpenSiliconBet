import type { Turn } from '../types'

/** 前端插入的串场占位，轮询应用 server turns 时需保留直到真身到达 */
export function isJensenVcPlaceholder(t: Turn): boolean {
  if (t.kind !== 'jensen_vc') return false
  const s = t.text
  if (s.includes('失败') || s.includes('异常')) return false
  return (
    s.startsWith('（正在生成') ||
    s.includes('（正在生成黄仁勋串场') ||
    (s.includes('视频接入中') && s.includes('黄仁勋正在发言')) ||
    s.startsWith('[视频接入')
  )
}

/** server 已写入黄仁勋 jensen_vc 条（非前端占位） */
export function hasServerJensenVc(turns: Turn[]): boolean {
  return turns.some((t) => t.kind === 'jensen_vc')
}

/**
 * 轮询到的 server turns 与「跳过论坛 → 黄仁勋」占位合并。
 * - server 尚无 jensen_vc 且 ref 有占位 → append 占位
 * - server 已有真 jensen → 丢弃 ref，用 server
 */
export function mergeTurnsFromPoll(
  serverTurns: Turn[],
  skipForumSent: boolean,
  jensenPlaceholder: Turn | null,
): Turn[] {
  if (hasServerJensenVc(serverTurns)) {
    return serverTurns
  }
  if (skipForumSent && jensenPlaceholder) {
    return [...serverTurns, jensenPlaceholder]
  }
  return serverTurns
}
