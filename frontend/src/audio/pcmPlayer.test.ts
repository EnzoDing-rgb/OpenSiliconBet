import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { PcmPlayer } from './pcmPlayer'

beforeEach(() => {
  class MockAudioContext {
    state: AudioContextState = 'running'
    destination = {}
    async suspend() {
      this.state = 'suspended'
    }
    async resume() {
      this.state = 'running'
    }
    async close() {
      this.state = 'closed'
    }
    createScriptProcessor() {
      return {
        connect: vi.fn(),
        disconnect: vi.fn(),
        onaudioprocess: null as unknown as ((ev: AudioProcessingEvent) => void) | null,
      }
    }
    createGain() {
      return { gain: { value: 1.0 }, connect: vi.fn() }
    }
  }
  vi.stubGlobal('AudioContext', MockAudioContext as unknown as typeof AudioContext)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PcmPlayer', () => {
  it('suspend and resume toggle context state', async () => {
    const p = new PcmPlayer()
    p.prime()
    expect(p.isSuspended()).toBe(false)
    await p.suspendPlayback()
    expect(p.isSuspended()).toBe(true)
    await p.resumePlayback()
    expect(p.isSuspended()).toBe(false)
    p.stop()
  })
})
