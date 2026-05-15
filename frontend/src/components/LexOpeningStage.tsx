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
      <div
        className="lex-opening-stage__panel"
        style={{ ['--lex-accent' as string]: lex.accent }}
      >
        <div className="lex-opening-stage__masthead">
          <p className="lex-opening-stage__venue">公众科学日分会场 · 科普圆桌</p>
          <div className="lex-opening-stage__masthead-row">
            <div className="lex-opening-stage__avatar-wrap" style={{ ['--accent' as string]: lex.accent }}>
              <img className="lex-opening-stage__avatar" src={lex.avatarSrc} alt="" width={104} height={104} />
              <span className="lex-opening-stage__mic" aria-hidden title="话筒">
                <svg viewBox="0 0 32 48" width="36" height="50" focusable="false">
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
            <h2 className="lex-opening-stage__h2" id="lex-opening-title">Lex 开场</h2>
          </div>
        </div>

        <div className="lex-opening-stage__script">
          <p className="lex-opening-stage__lede">
            大家好，我是 Lex。
          </p>
          <p className="lex-opening-stage__lede">
            很多人第一次听到「指令集」三个字会觉得离自己很远——好像只有工程师才该关心。但我想用一个特别笨的比喻把它拉近一点：
          </p>
          <p className="lex-opening-stage__lede">
            想象三条高速公路。第一条修得最早，收费站最多、服务区最全，几乎所有大货车都习惯走它——这就是 x86，几十年的世界默认通道。第二条路后来居上，把「省电」和「无处不在」做成了艺术，你的手机、平板、车里很大一部分都在用它——这是 ARM。第三条路是新来的：它说「规则写在纸上，谁都能修路、谁都能改收费站」——开源、模块化、不被某一家锁死——这就是 RISC-V。
          </p>
          <p className="lex-opening-stage__lede">
            三条路不是谁把谁「一脚踢死」的故事，更像一场长期的共存与拉扯。而今天坐在我旁边的几位朋友，恰好分别站在这三条路上——但他们又都被同一件事绑在一起：AI 和 Agent 把算力饥渴写进了每一个产品里。所以我想问的问题其实不炫技，而是很朴素：在这波浪潮里，RISC-V 到底是配角，还是有机会成为主角之一？
          </p>
          <p className="lex-opening-stage__lede">
            我不站队。我只负责把问题问得更深一点。接下来，让我们听听路上的人自己怎么说。
          </p>
        </div>

        {step === 'init' ? (
          <div className="lex-opening-stage__actions">
            <button type="button" className="lex-opening-stage__primary" onClick={() => setStep('opening')}>
              播放开场
            </button>
          </div>
        ) : (
          <>
            <audio ref={longRef} className="lex-opening-stage__audio" src={AUDIO_LONG} preload="none" onError={() => setLongBroken(true)} />
            <audio ref={shortRef} className="lex-opening-stage__audio" src={AUDIO_SHORT} preload="none" />
            <div className="lex-opening-stage__actions">
              {longBroken ? (
                <button type="button" className="lex-opening-stage__primary" onClick={() => complete()}>
                  进入论坛交锋
                </button>
              ) : (
                <div className="lex-opening-stage__row">
                  <button type="button" className="lex-opening-stage__ghost" onClick={skip}>
                    跳过开场
                  </button>
                  <button type="button" className="lex-opening-stage__primary" onClick={() => complete()}>
                    进入论坛交锋
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
