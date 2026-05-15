import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  forwardRef,
} from 'react'
import { PcmPlayer } from '../audio/pcmPlayer'
import { friendlyTtsPhaseDetail } from '../utils/ttsPhaseUi'
import type { Speaker } from '../types'
import { speakerLabelZh } from '../utils/avatars'

type AudioMeta = {
  type: 'meta'
  format: 'PCM_24000HZ_MONO_16BIT'
  speaker: Speaker
  round: number
  turn_index: number
  selection?: boolean
}

type PhaseMsg = {
  type: 'phase'
  phase: string
  turn_index?: number
  round?: number
  speaker?: Speaker
  message?: string
}

type ControlMsg =
  | AudioMeta
  | PhaseMsg
  | { type: 'turn_done'; speaker: Speaker; round: number; turn_index: number; skip_playback?: boolean; selection?: boolean }
  | { type: 'all_done' }
  | { type: 'error'; message: string }

function speakerZh(s: Speaker | undefined): string | null {
  if (!s) return null
  return speakerLabelZh(s)
}

export type DebateAudioHandle = {
  /** Video Call：打断当前段合成/播放，跳过队列中非黄仁勋段，只播 jensen_vc */
  skipNonJensenAudioToJensen: () => void
  /** 选中气泡内文字：用对应讲者 Voice ID 播一段（仅 jensen / liptan） */
  speakSelection: (speaker: Speaker, text: string) => void
}

export const DebateAudio = forwardRef<
  DebateAudioHandle,
  {
    runId: string | null
    enabled: boolean
    skipToJensenActive?: boolean
    /** Expected dialogue segments (e.g. 6 for 3 rounds × 2). Shown as progress hint. */
    totalTurns?: number | null
    /** When true, connects in lex_review mode (plays judge_result TTS only). */
    lexReview?: boolean
  }
>(function DebateAudio({ runId, enabled, skipToJensenActive = false, totalTurns = null, lexReview = false }, ref) {
  const [meta, setMeta] = useState<AudioMeta | null>(null)
  const [serverPhase, setServerPhase] = useState<string>('idle')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [manualPaused, setManualPaused] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const player = useMemo(() => new PcmPlayer(), [])
  const pendingAckRef = useRef<number | null>(null)
  const lowBufferSinceRef = useRef<number | null>(null)

  useImperativeHandle(
    ref,
    () => ({
      skipNonJensenAudioToJensen: () => {
        player.clear()
        void player.resumeIfNeeded()
        setManualPaused(false)
        const ws = wsRef.current
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'skip_audio_until_jensen' }))
        }
        const pending = pendingAckRef.current
        if (pending != null && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ack_turn_done', turn_index: pending }))
          pendingAckRef.current = null
          lowBufferSinceRef.current = null
        }
      },
      speakSelection: (speaker: Speaker, text: string) => {
        const t = text.trim().slice(0, 1500)
        if (t.length < 2) return
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) return
        ws.send(JSON.stringify({ type: 'speak_selection', speaker, text: t }))
      },
    }),
    [player],
  )

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
    if (!meta || skipToJensenActive) return
    setManualPaused(false)
    void player.resumePlayback()
  }, [meta?.turn_index, meta, player, skipToJensenActive])

  useEffect(() => {
    if (!skipToJensenActive) return
    setManualPaused(false)
    void player.resumeIfNeeded()
  }, [player, skipToJensenActive])

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
    lowBufferSinceRef.current = null

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host || 'localhost'
    const lexReviewParam = lexReview ? '&lex_review=1' : ''
    const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/debate-audio?run_id=${encodeURIComponent(runId)}${lexReviewParam}`)
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
          if (msg.selection && msg.turn_index === -1) {
            const wsNow = wsRef.current
            if (wsNow && wsNow.readyState === WebSocket.OPEN) {
              wsNow.send(JSON.stringify({ type: 'ack_turn_done', turn_index: -1 }))
            }
            pendingAckRef.current = null
            lowBufferSinceRef.current = null
            return
          }
          pendingAckRef.current = msg.turn_index
          lowBufferSinceRef.current = null
          if (msg.skip_playback) {
            const wsNow = wsRef.current
            if (wsNow && wsNow.readyState === WebSocket.OPEN) {
              wsNow.send(JSON.stringify({ type: 'ack_turn_done', turn_index: msg.turn_index }))
              pendingAckRef.current = null
              lowBufferSinceRef.current = null
            }
          }
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
      const bufferedMs = player.getBufferedMs()
      if (bufferedMs <= 16) {
        if (lowBufferSinceRef.current == null) {
          lowBufferSinceRef.current = window.performance.now()
          return
        }
        if (window.performance.now() - lowBufferSinceRef.current < 220) return
        wsNow.send(JSON.stringify({ type: 'ack_turn_done', turn_index: pending }))
        pendingAckRef.current = null
        lowBufferSinceRef.current = null
        return
      }
      lowBufferSinceRef.current = null
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
  }, [enabled, runId, player, lexReview])

  if (!enabled || !runId) return null

  const showPause = !skipToJensenActive && !error && !done && !!meta

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
})
