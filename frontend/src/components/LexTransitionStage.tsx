import { useCallback, useEffect, useRef, useState } from 'react'
import { speakerMeta } from '../utils/avatars'

const AUDIO_SRC = '/audio/lex-transition.mp3'

interface Props {
  onFinished: () => void
}

export function LexTransitionStage({ onFinished }: Props) {
  const [audioBroken, setAudioBroken] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [done, setDone] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const finishRef = useRef(onFinished)
  finishRef.current = onFinished

  const finish = useCallback(() => {
    try { audioRef.current?.pause() } catch { /* ignore */ }
    finishRef.current()
  }, [])

  const handleEnded = useCallback(() => {
    setDone(true)
    finish()
  }, [finish])

  // Start playing on mount
  useEffect(() => {
    const a = audioRef.current
    if (!a) return
    if (audioBroken) return
    a.currentTime = 0
    void a.play().then(() => setPlaying(true)).catch(() => setAudioBroken(true))
  }, [audioBroken])

  const lex = speakerMeta.lex

  return (
    <section className="lex-transition-stage" aria-label="Lex 过渡串场">
      <div
        className="lex-transition-stage__panel"
        style={{ '--lex-accent': lex.accent } as React.CSSProperties}
      >
        <div className="lex-transition-stage__masthead">
          <h2 className="lex-transition-stage__h2">Lex 串场</h2>
        </div>

        <div className="lex-transition-stage__host">
          <div className="lex-transition-stage__avatar-wrap" style={{ '--accent': lex.accent } as React.CSSProperties}>
            <img className="lex-transition-stage__avatar" src={lex.avatarSrc} alt="" width={96} height={96} />
          </div>
          <div className="lex-transition-stage__host-text">
            <p className="lex-transition-stage__host-line">Lex Fridman from MIT</p>
          </div>
        </div>

        <div className="lex-transition-stage__script">
          {audioBroken ? (
            <p className="lex-transition-stage__warn">
              未检测到过渡音频（<code>lex-transition.mp3</code>）。
            </p>
          ) : (
            <p className="lex-transition-stage__line">
              「好的，我们嘉宾的对谈到此结束，现在让我们看看观众们觉得哪一方更占优势。」
            </p>
          )}
        </div>

        <div className="lex-transition-stage__actions">
          {!playing && !audioBroken && <p className="lex-transition-stage__hint">正在播放…</p>}
          <button
            type="button"
            className="lex-transition-stage__primary"
            onClick={done ? finish : () => { audioRef.current?.pause(); finish() }}
            data-played={done || undefined}
          >
            {done ? '查看投票结果 →' : '跳过 →'}
          </button>
        </div>
      </div>

      <audio
        ref={audioRef}
        src={AUDIO_SRC}
        preload="auto"
        onEnded={handleEnded}
        onError={() => setAudioBroken(true)}
      />
    </section>
  )
}
