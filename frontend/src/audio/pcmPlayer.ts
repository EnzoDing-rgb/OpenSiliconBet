/** One context for the page, created inside a click so the browser allows sound. */
let sharedCtx: AudioContext | null = null

function liveContext(): AudioContext {
  if (!sharedCtx || sharedCtx.state === 'closed') {
    sharedCtx = new AudioContext({ sampleRate: 24000 })
  }
  if (sharedCtx.state !== 'running') void sharedCtx.resume()
  return sharedCtx
}

export function unlockPcmPlayback() {
  if (typeof window === 'undefined') return
  liveContext()
}

/** Plays mono 16-bit LE PCM at 24kHz by scheduling buffers on one shared context. */
export class PcmPlayer {
  private ctx: AudioContext | null = null
  private gainNode: GainNode | null = null
  private sources: AudioBufferSourceNode[] = []
  private playhead = 0
  private readonly sampleRate = 24000

  prime() {
    if (this.ctx && this.ctx.state !== 'closed') return
    this.ctx = liveContext()
    this.gainNode = this.ctx.createGain()
    this.gainNode.gain.value = 100.0
    this.gainNode.connect(this.ctx.destination)
    this.playhead = 0
  }

  setVolume(v: number) {
    if (this.gainNode) {
      this.gainNode.gain.value = Math.max(0, Math.min(200, v))
    }
  }

  getVolume(): number {
    return this.gainNode?.gain.value ?? 1.0
  }

  async resumeIfNeeded() {
    if (!this.ctx) return
    if (this.ctx.state !== 'running') {
      await this.ctx.resume()
    }
  }

  async suspendPlayback() {
    if (this.ctx && this.ctx.state === 'running') {
      await this.ctx.suspend()
    }
  }

  async resumePlayback() {
    if (this.ctx && this.ctx.state === 'suspended') {
      await this.ctx.resume()
    }
  }

  isSuspended(): boolean {
    return this.ctx != null && this.ctx.state === 'suspended'
  }

  getBufferedMs() {
    if (!this.ctx) return 0
    return Math.max(0, (this.playhead - this.ctx.currentTime) * 1000)
  }

  pushPcm16le(buf: ArrayBuffer) {
    this.prime()
    const ctx = this.ctx
    const gain = this.gainNode
    if (!ctx || ctx.state === 'closed' || !gain) return
    if (ctx.state !== 'running') void ctx.resume()
    const view = new DataView(buf)
    const n = Math.floor(view.byteLength / 2)
    if (n <= 0) return
    const audioBuf = ctx.createBuffer(1, n, this.sampleRate)
    const channel = audioBuf.getChannelData(0)
    for (let i = 0; i < n; i++) {
      channel[i] = view.getInt16(i * 2, true) / 32768
    }
    const src = ctx.createBufferSource()
    src.buffer = audioBuf
    src.connect(gain)
    const startAt = Math.max(ctx.currentTime + 0.02, this.playhead)
    src.start(startAt)
    this.playhead = startAt + audioBuf.duration
    this.sources.push(src)
    src.onended = () => {
      this.sources = this.sources.filter((item) => item !== src)
    }
  }

  clear() {
    for (const src of this.sources) {
      try {
        src.stop()
      } catch {
        void 0
      }
    }
    this.sources = []
    this.playhead = this.ctx ? this.ctx.currentTime : 0
  }

  stop() {
    this.clear()
    if (this.gainNode) {
      try {
        this.gainNode.disconnect()
      } catch {
        void 0
      }
    }
    this.gainNode = null
    this.ctx = null
  }
}
