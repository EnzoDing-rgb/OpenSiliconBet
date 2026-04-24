import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PcmPlayer } from '../audio/pcmPlayer'
import { friendlyTtsPhaseDetail } from '../utils/ttsPhaseUi'

type AudioMeta = {
  type: 'meta'
  format: 'PCM_24000HZ_MONO_16BIT'
  speaker: 'jervis' | 'mearsheimer'
  round: number
  turn_index: number
}

type PhaseMsg = {
  type: 'phase'
  phase: string
  turn_index?: number
  round?: number
  speaker?: 'jervis' | 'mearsheimer'
  message?: string
}

type ControlMsg =
  | AudioMeta
  | PhaseMsg
  | { type: 'turn_done'; speaker: 'jervis' | 'mearsheimer'; round: number; turn_index: number }
  | { type: 'all_done' }
  | { type: 'error'; message: string }

function speakerZh(s: 'jervis' | 'mearsheimer' | undefined): string | null {
  if (s === 'jervis') return '滴滴 Researcher'
  if (s === 'mearsheimer') return 'Manus Researcher'
  return null
}

export function DebateAudio({
  runId,
  enabled,
  totalTurns = null,
}: {
  runId: string | null
  enabled: boolean
  /** Expected dialogue segments (e.g. 6 for 3 rounds × 2). Shown as progress hint. */
  totalTurns?: number | null
}) {
  const [meta, setMeta] = useState<AudioMeta | null>(null)
  const [serverPhase, setServerPhase] = useState<string>('idle')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [manualPaused, setManualPaused] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const player = useMemo(() => new PcmPlayer(), [])
  const pendingAckRef = useRef<number | null>(null)

  const statusDetail = useMemo(() => {
    if (error) return error
    if (done) return '已播放完成'
    if (!meta) return '正在连接语音通道…'
    const who = speakerZh(meta.speaker)
    const phase = serverPhase === 'idle' ? 'connecting' : serverPhase
    return friendlyTtsPhaseDetail({
      phase,
      speakerLabel: who,
      round: meta.round,
      turnIndex: meta.turn_index,
      totalTurns: totalTurns ?? null,
    })
  }, [error, done, meta, serverPhase, totalTurns])

  useEffect(() => {
    if (!meta) return
    setManualPaused(false)
    void player.resumePlayback()
  }, [meta?.turn_index, meta, player])

  const togglePause = useCallback(async () => {
    try {
      if (player.isSuspended()) {
        await player.resumePlayback()
        setManualPaused(false)
      } else {
        await player.suspendPlayback()
        setManualPaused(true)
      }
    } catch {
      setError('暂停/继续播放失败，请刷新页面重试')
    }
  }, [player])

  useEffect(() => {
    if (!enabled || !runId) return

    player.prime()
    void player.resumeIfNeeded()
    setError(null)
    setDone(false)
    setMeta(null)
    setServerPhase('idle')
    pendingAckRef.current = null

    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = window.location.hostname || 'localhost'
    const wsPort = '9000'

    const ws = new WebSocket(`${wsProtocol}://${wsHost}:${wsPort}/ws/debate-audio?run_id=${encodeURIComponent(runId)}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start' }))
    }

    ws.onmessage = (evt) => {
      if (typeof evt.data === 'string') {
        const msg = JSON.parse(evt.data) as ControlMsg
        if (msg.type === 'meta') {
          setMeta(msg)
        }
        if (msg.type === 'phase') {
          setServerPhase(msg.phase)
        }
        if (msg.type === 'error') setError(msg.message)
        if (msg.type === 'all_done') setDone(true)
        if (msg.type === 'turn_done') {
          pendingAckRef.current = msg.turn_index
        }
        return
      }
      if (evt.data instanceof ArrayBuffer) {
        player.pushPcm16le(evt.data)
      }
    }

    ws.onerror = () => {
      setError('音频 WebSocket 连接失败')
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    const ackTimer = window.setInterval(() => {
      const pending = pendingAckRef.current
      const wsNow = wsRef.current
      if (pending == null || !wsNow || wsNow.readyState !== WebSocket.OPEN) return
      if (player.getBufferedMs() < 120) {
        wsNow.send(JSON.stringify({ type: 'ack_turn_done', turn_index: pending }))
        pendingAckRef.current = null
      }
    }, 80)

    return () => {
      try {
        ws.close()
      } catch {
        void 0
      }
      wsRef.current = null
      window.clearInterval(ackTimer)
      player.stop()
    }
  }, [enabled, runId, player])

  if (!enabled || !runId) return null

  const showPause = !error && !done && !!meta

  return (
    <div className="audio-status">
      <div className="audio-status-row">
        <div className="audio-status-text">
          <strong>语音</strong>：{manualPaused ? <span className="audio-paused-hint">已暂停 · </span> : null}
          <span className={error ? 'audio-error' : ''}>{statusDetail}</span>
        </div>
        {showPause && (
          <button type="button" className="audio-pause-btn" onClick={() => void togglePause()}>
            {manualPaused ? '继续' : '暂停'}
          </button>
        )}
      </div>
    </div>
  )
}
