import { useEffect, useMemo, useRef, useState } from 'react'

type AudioMeta = {
  type: 'meta'
  format: 'PCM_24000HZ_MONO_16BIT'
  speaker: 'jervis' | 'mearsheimer'
  round: number
  turn_index: number
}

type ControlMsg =
  | AudioMeta
  | { type: 'turn_done'; speaker: 'jervis' | 'mearsheimer'; round: number; turn_index: number }
  | { type: 'all_done' }
  | { type: 'error'; message: string }

class PcmPlayer {
  private ctx: AudioContext | null = null
  private node: ScriptProcessorNode | null = null
  private queue: Float32Array[] = []
  private queuedSamples = 0
  private readOffset = 0
  private currentChunk: Float32Array | null = null
  private readonly sampleRate = 24000

  prime() {
    if (this.ctx) return
    this.ctx = new AudioContext({ sampleRate: 24000 })
    // eslint-disable-next-line deprecation/deprecation
    this.node = this.ctx.createScriptProcessor(4096, 0, 1)
    this.node.onaudioprocess = (e) => {
      const out = e.outputBuffer.getChannelData(0)
      let i = 0
      while (i < out.length) {
        if (!this.currentChunk || this.readOffset >= this.currentChunk.length) {
          this.currentChunk = this.queue.shift() ?? null
          this.readOffset = 0
          if (!this.currentChunk) break
        }
        const available = this.currentChunk.length - this.readOffset
        const need = out.length - i
        const take = Math.min(available, need)
        out.set(this.currentChunk.subarray(this.readOffset, this.readOffset + take), i)
        this.readOffset += take
        i += take
        this.queuedSamples -= take
      }
      // Fill remainder with zeros
      while (i < out.length) out[i++] = 0
    }
    this.node.connect(this.ctx.destination)
  }

  async resumeIfNeeded() {
    if (!this.ctx) return
    if (this.ctx.state !== 'running') {
      await this.ctx.resume()
    }
  }

  getBufferedMs() {
    const currentRemaining = this.currentChunk ? Math.max(0, this.currentChunk.length - this.readOffset) : 0
    const total = this.queuedSamples + currentRemaining
    return (total / this.sampleRate) * 1000
  }

  pushPcm16le(buf: ArrayBuffer) {
    // Convert Int16 PCM mono -> Float32 [-1, 1]
    const view = new DataView(buf)
    const n = Math.floor(view.byteLength / 2)
    if (n <= 0) return
    const out = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      const s = view.getInt16(i * 2, true)
      out[i] = s / 32768
    }
    this.queue.push(out)
    this.queuedSamples += out.length
    // Prevent unbounded memory growth if backend outruns playback
    const maxBuffered = 24000 * 30 // 30s
    while (this.queuedSamples > maxBuffered && this.queue.length > 1) {
      const drop = this.queue.shift()
      if (drop) this.queuedSamples -= drop.length
    }
  }

  stop() {
    this.queue = []
    this.queuedSamples = 0
    this.readOffset = 0
    this.currentChunk = null
    if (this.node) {
      try {
        this.node.disconnect()
      } catch {}
    }
    if (this.ctx) {
      try {
        this.ctx.close()
      } catch {}
    }
    this.node = null
    this.ctx = null
  }
}

export function DebateAudio({ runId, enabled }: { runId: string | null; enabled: boolean }) {
  const [meta, setMeta] = useState<AudioMeta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const player = useMemo(() => new PcmPlayer(), [])
  const pendingAckRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled || !runId) return

    player.prime()
    void player.resumeIfNeeded()
    setError(null)
    setDone(false)
    pendingAckRef.current = null

    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = window.location.hostname || 'localhost'
    const wsPort = '8000'

    const ws = new WebSocket(`${wsProtocol}://${wsHost}:${wsPort}/ws/debate-audio?run_id=${encodeURIComponent(runId)}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start' }))
    }

    ws.onmessage = (evt) => {
      if (typeof evt.data === 'string') {
        const msg = JSON.parse(evt.data) as ControlMsg
        if (msg.type === 'meta') setMeta(msg)
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
      setError('音频WebSocket连接失败')
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
      } catch {}
      wsRef.current = null
      window.clearInterval(ackTimer)
      player.stop()
    }
  }, [enabled, runId, player])

  if (!enabled || !runId) return null

  return (
    <div className="audio-status">
      <div>
        <strong>语音</strong>：
        {error ? (
          <span className="audio-error"> {error}</span>
        ) : done ? (
          <span> 已播放完成</span>
        ) : meta ? (
          <span>
            {' '}
            正在播放：{meta.speaker === 'jervis' ? '杰维斯' : '米尔斯海默'}（第 {meta.round} 轮）
          </span>
        ) : (
          <span> 连接中...</span>
        )}
      </div>
    </div>
  )
}

