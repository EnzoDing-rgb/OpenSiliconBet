import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { speakerMeta } from '../utils/avatars'
import './LexOpeningStage.css'

/** 与 `docs/background/lex-opening-script.md`、Vite `public/audio/` 约定一致 */
const AUDIO_LONG = '/audio/lex-opening-long.mp3'
const AUDIO_SHORT = '/audio/lex-opening-short.mp3'

type InnerStep = 'init' | 'opening'

export function LexOpeningStage({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<InnerStep>('init')
  const [longBroken, setLongBroken] = useState(false)
  const gid = useId().replace(/:/g, '')
  const longRef = useRef<HTMLAudioElement | null>(null)
  const shortRef = useRef<HTMLAudioElement | null>(null)
  const skippedRef = useRef(false)
  const finishRef = useRef(onFinished)
  finishRef.current = onFinished

  const complete = useCallback(() => {
    try {
      longRef.current?.pause()
      shortRef.current?.pause()
    } catch {
      void 0
    }
    finishRef.current()
  }, [])

  const playShortThenDone = useCallback(() => {
    const s = shortRef.current
    if (!s) {
      complete()
      return
    }
    s.currentTime = 0
    void s.play().catch(() => complete())
  }, [complete])

  const skip = useCallback(() => {
    skippedRef.current = true
    longRef.current?.pause()
    if (longRef.current) longRef.current.currentTime = 0
    playShortThenDone()
  }, [playShortThenDone])

  useEffect(() => {
    const s = shortRef.current
    if (!s) return
    const onShortEnded = () => complete()
    s.addEventListener('ended', onShortEnded)
    return () => s.removeEventListener('ended', onShortEnded)
  }, [complete, step])

  useEffect(() => {
    if (step !== 'opening') return
    const L = longRef.current
    if (!L || longBroken) return
    const onLongEnded = () => {
      if (skippedRef.current) return
      complete()
    }
    L.addEventListener('ended', onLongEnded)
    return () => L.removeEventListener('ended', onLongEnded)
  }, [complete, step, longBroken])

  useEffect(() => {
    if (step !== 'opening' || longBroken) return
    const L = longRef.current
    if (!L) return
    skippedRef.current = false
    L.currentTime = 0
    void L.play().catch(() => setLongBroken(true))
  }, [step, longBroken])

  const lex = speakerMeta.lex

  return (
    <section className="lex-opening-stage" aria-labelledby="lex-opening-title">
      <div className="lex-opening-stage__panel">
        <p className="lex-opening-stage__venue" id="lex-opening-title">
          公众科学日分会场 · 中科院软件所讲堂
        </p>
        <h2 className="lex-opening-stage__h2">阶段 {step === 'init' ? '0' : '0.5'} · Lex 主持开场</h2>

        <div className="lex-opening-stage__host">
          <div className="lex-opening-stage__avatar-wrap" style={{ ['--accent' as string]: lex.accent }}>
            <img className="lex-opening-stage__avatar" src={lex.avatarSrc} alt="" width={120} height={120} />
            <span className="lex-opening-stage__mic" aria-hidden title="话筒">
              <svg viewBox="0 0 32 48" width="40" height="56" focusable="false">
                <rect x="12" y="6" width="8" height="22" rx="4" fill={`url(#mic-grad-${gid})`} stroke="#1e293b" strokeWidth="1" />
                <path d="M10 28c0 4 2 7 6 7s6-3 6-7" fill="none" stroke="#1e293b" strokeWidth="1.5" />
                <rect x="14" y="34" width="4" height="10" rx="1" fill="#334155" />
                <ellipse cx="16" cy="46" rx="10" ry="2" fill="#475569" />
                <defs>
                  <linearGradient id={`mic-grad-${gid}`} x1="12" y1="6" x2="20" y2="28" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#94a3b8" />
                    <stop offset="1" stopColor="#475569" />
                  </linearGradient>
                </defs>
              </svg>
            </span>
          </div>
          <div className="lex-opening-stage__host-text">
            <p className="lex-opening-stage__name">{lex.nameZh}</p>
            <p className="lex-opening-stage__role">{lex.subtitleZh}</p>
          </div>
        </div>

        {step === 'init' ? (
          <div className="lex-opening-stage__copy">
            <p>
              大家好，我是 Lex。今天这场「RISC-V vs x86 vs ARM」不是判输赢的擂台，而是把三条算力路线放在同一张圆桌上——看
              Agent 时代它们各自怎么接招。
            </p>
            <p className="lex-opening-stage__hint">下面是我的预录开场（阶段 0.5）。你也可以稍后一键跳过短接进圆桌。</p>
            <button type="button" className="lex-opening-stage__primary" onClick={() => setStep('opening')}>
              播放 Lex 预录开场
            </button>
          </div>
        ) : (
          <div className="lex-opening-stage__copy">
            <audio ref={longRef} src={AUDIO_LONG} preload="none" onError={() => setLongBroken(true)} />
            <audio ref={shortRef} src={AUDIO_SHORT} preload="none" />
            {longBroken ? (
              <>
                <p className="lex-opening-stage__warn">
                  未检测到预录音频（请将 <code>lex-opening-long.mp3</code> / <code>lex-opening-short.mp3</code> 放入{' '}
                  <code>frontend/public/audio/</code>，见 <code>lex-opening-script.md</code>）。
                </p>
                <button type="button" className="lex-opening-stage__primary" onClick={() => complete()}>
                  直接进入论坛交锋
                </button>
              </>
            ) : (
              <>
                <p>正在播放预录贯口… 跳过时会先停长轨，再播短句「好的，那让我们直接开始。」（无叠声）</p>
                <div className="lex-opening-stage__row">
                  <button type="button" className="lex-opening-stage__ghost" onClick={skip}>
                    跳过开场
                  </button>
                  <button type="button" className="lex-opening-stage__primary" onClick={() => complete()}>
                    直接进入论坛交锋
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
