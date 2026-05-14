export function friendlyTtsPhaseDetail(params: {
  phase: string
  speakerLabel: string | null
  round: number | null
  turnIndex: number | null
  totalTurns: number | null
}): string {
  const { phase, speakerLabel, round, turnIndex, totalTurns } = params
  const who = speakerLabel ?? '当前讲者'
  const r = round != null ? `第 ${round} 轮` : ''
  const turnHint =
    turnIndex != null &&
    turnIndex >= 0 &&
    totalTurns != null &&
    totalTurns > 0
      ? `（第 ${turnIndex + 1} / ${totalTurns} 段）`
      : ''

  switch (phase) {
    case 'connecting':
      return `正在连接语音服务…`
    case 'generating':
      return `${who}${r ? ` · ${r}` : ''}：正在合成语音${turnHint}`
    case 'playing':
      return `正在播放：${who}${r ? `（${r}）` : ''}${turnHint}`
    case 'completed':
      return `${who}：本段语音已生成完毕，缓冲播放中${turnHint}`
    case 'waiting_content':
      return '正在等待下一位研究者的文本生成…'
    default:
      return `语音状态：${phase}`
  }
}
