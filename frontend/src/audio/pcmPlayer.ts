/** Plays mono 16-bit LE PCM at 24kHz via ScriptProcessorNode (legacy but simple). */
export class PcmPlayer {
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
    const currentRemaining = this.currentChunk ? Math.max(0, this.currentChunk.length - this.readOffset) : 0
    const total = this.queuedSamples + currentRemaining
    return (total / this.sampleRate) * 1000
  }

  pushPcm16le(buf: ArrayBuffer) {
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
    const maxBuffered = 24000 * 30
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
      } catch {
        void 0
      }
    }
    if (this.ctx) {
      try {
        void this.ctx.close()
      } catch {
        void 0
      }
    }
    this.node = null
    this.ctx = null
  }
}
