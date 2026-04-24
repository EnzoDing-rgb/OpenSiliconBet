import { describe, expect, it } from 'vitest'
import { friendlyTtsPhaseDetail } from './ttsPhaseUi'

describe('friendlyTtsPhaseDetail', () => {
  it('covers known phases', () => {
    expect(
      friendlyTtsPhaseDetail({
        phase: 'connecting',
        speakerLabel: null,
        round: null,
        turnIndex: null,
        totalTurns: null,
      }),
    ).toContain('连接')

    expect(
      friendlyTtsPhaseDetail({
        phase: 'waiting_content',
        speakerLabel: null,
        round: null,
        turnIndex: 3,
        totalTurns: 6,
      }),
    ).toContain('等待')

    const playing = friendlyTtsPhaseDetail({
      phase: 'playing',
      speakerLabel: '滴滴 Researcher',
      round: 2,
      turnIndex: 1,
      totalTurns: 6,
    })
    expect(playing).toContain('滴滴')
    expect(playing).toContain('2')
    expect(playing).toContain('2 / 6')
  })
})
