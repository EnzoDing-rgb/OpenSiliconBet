import { useState, useEffect, useCallback, useRef } from 'react'
import './App.css'
import { RoleCard } from './components/RoleCard'
import { TurnMessage } from './components/TurnMessage'
import { MasterChat } from './components/MasterChat.tsx'
import { DebateAudio, type DebateAudioHandle } from './components/DebateAudio'
import { LexOpeningStage } from './components/LexOpeningStage'
import { LexTransitionStage } from './components/LexTransitionStage'
import { AudienceBetPanel } from './components/AudienceBetPanel'
import { speakerMeta } from './utils/avatars'
import { markdownToSafeHtml } from './utils/markdownRender'
import { startDebate, getDebateStatus, getDebateResult, downloadMarkdown, skipForumToJensen, triggerLexReview } from './api'
import type { Turn, RunStatus } from './types'
import { mergeTurnsFromPoll, hasServerJensenVc, isJensenVcPlaceholder } from './utils/mergeTurnsFromPoll'

const KEYNOTE_IMAGE_SRC = '/images/summit-cas-iss-keynote.png'
const INTRO_VIDEO_SRC = '/video/intro.mp4'

function App() {
  const [showIntro, setShowIntro] = useState(true)
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [judgeResult, setJudgeResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [audioEnabled, setAudioEnabled] = useState(false)
  const [lexPreamble, setLexPreamble] = useState(false)
  const [skipForumSent, setSkipForumSent] = useState(false)
  const skipForumSentRef = useRef(false)
  const [jensenStreamText, setJensenStreamText] = useState<string | null>(null)
  const debateAudioRef = useRef<DebateAudioHandle>(null)
  const jensenPlaceholderRef = useRef<Turn | null>(null)
  const [lexReviewVisible, setLexReviewVisible] = useState(false)
  const [lexTransitionDone, setLexTransitionDone] = useState(false)
  const [lexReviewLoading, setLexReviewLoading] = useState(false)
  const [lexReviewTtsActive, setLexReviewTtsActive] = useState(false)
  const introVideoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    skipForumSentRef.current = skipForumSent
  }, [skipForumSent])

  const renderCompareMarkdown = (text: string) => (
    <div className="md-render compare-md" dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(text) }} />
  )

  const startForumBackend = useCallback(async () => {
    setLoading(true)
    setError(null)
    setTurns([])
    setStatus(null)
    setRunId(null)
    setJudgeResult(null)
    setSkipForumSent(false)
    jensenPlaceholderRef.current = null
    setJensenStreamText(null)
    setLexReviewVisible(false)
    setLexReviewTtsActive(false)
    setLexTransitionDone(false)
    try {
      const id = await startDebate()
      setRunId(id)
    } catch (e) {
      setError(`无法启动对谈：${e}`)
      setLoading(false)
    }
  }, [])

  const handleStart = useCallback(() => {
    setAudioEnabled(true)
    setError(null)
    setLexPreamble(true)
  }, [])

  const handleDownload = useCallback(async () => {
    if (!runId) return
    const content = await getDebateResult(runId)
    downloadMarkdown(content, 'riscv_forum_result.md')
  }, [runId])

  const handleEndQa = useCallback(async () => {
    if (!runId) return
    setLexReviewLoading(true)
    try {
      const result = await triggerLexReview(runId)
      if (result) {
        setJudgeResult(result)
        setLexReviewVisible(true)
        setLexReviewTtsActive(true)
      }
    } catch {
      setError('Lex 锐评生成失败')
    } finally {
      setLexReviewLoading(false)
    }
  }, [runId])

  const handleIntroEnded = useCallback(() => {
    setShowIntro(false)
  }, [])

  const handleIntroSkip = useCallback(() => {
    const v = introVideoRef.current
    if (v) { v.pause(); v.currentTime = v.duration ?? 0 }
    setShowIntro(false)
  }, [])

  // Polling
  useEffect(() => {
    if (!runId || status === 'done' || status === 'error') {
      if (status === 'done' || status === 'error') {
        setLoading(false)
      }
      return
    }

    const tick = async () => {
      if (!runId) return
      try {
        const data = await getDebateStatus(runId)
        setStatus(data.status)
        setJensenStreamText(
          data.jensen_stream_text === undefined || data.jensen_stream_text === null
            ? null
            : data.jensen_stream_text,
        )
        setTurns(
          mergeTurnsFromPoll(data.turns, skipForumSentRef.current, jensenPlaceholderRef.current),
        )
        if (hasServerJensenVc(data.turns)) {
          jensenPlaceholderRef.current = null
          setJensenStreamText(null)
        }
        if (data.error) {
          setError(data.error)
        }
      } catch (e) {
        console.error('Polling error', e)
      }
    }

    void tick()
    const interval = setInterval(() => void tick(), 600)
    return () => clearInterval(interval)
  }, [runId, status])

  const isDone = status === 'done'
  const isRunning = status === 'running' || loading || lexPreamble

  // Intro video overlay
  if (showIntro) {
    return (
      <div className="intro-video-overlay">
        <video
          ref={introVideoRef}
          className="intro-video"
          src={INTRO_VIDEO_SRC}
          autoPlay
          playsInline
          onEnded={handleIntroEnded}
        />
        <div className="intro-video-controls">
          <button className="intro-skip-btn" onClick={handleIntroSkip}>
            跳过 &rarr;
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="app-root">
      <div className="app-container">
        <header className="app-header">
          <h1>RISC-V 三国杀 · 论坛交锋</h1>
          <p className="topic">
            <strong>主题</strong>：RISC-V vs x86 vs ARM（Agent 时代算力格局 · demo）
          </p>
        </header>

        <div className="hero-keynote-wrap">
          <img
            className="hero-keynote-img"
            src={KEYNOTE_IMAGE_SRC}
            alt="圆桌论坛会场示意（RISC-V vs x86 vs ARM）"
            loading="eager"
            decoding="async"
          />
        </div>

        {lexPreamble && (
          <LexOpeningStage
            onFinished={() => {
              setLexPreamble(false)
              void startForumBackend()
            }}
          />
        )}

        <div
          className={`roundtable-wrap${lexPreamble ? ' roundtable-wrap--lex-active' : ''}`}
          aria-hidden={lexPreamble}
        >
          <p className="roundtable-caption">圆桌席次 · Lex 左侧主持 · 四嘉宾围席</p>
          <div className="roundtable-stage" aria-label="论坛圆桌席次">
            <div className="roundtable-oval" aria-hidden />
            <div className="roundtable-seat roundtable-seat--lex">
              <RoleCard
                name={speakerMeta.lex.nameZh}
                school={speakerMeta.lex.subtitleZh}
                avatarSrc={speakerMeta.lex.avatarSrc}
                accent={speakerMeta.lex.accent}
                isLeft
                variant="seat"
              />
            </div>
            <div className="roundtable-seat roundtable-seat--wuwei">
              <RoleCard
                name={speakerMeta.wuwei.nameZh}
                school={speakerMeta.wuwei.subtitleZh}
                avatarSrc={speakerMeta.wuwei.avatarSrc}
                accent={speakerMeta.wuwei.accent}
                isLeft
                variant="seat"
              />
            </div>
            <div className="roundtable-seat roundtable-seat--liptan">
              <RoleCard
                name={speakerMeta.liptan.nameZh}
                school={speakerMeta.liptan.subtitleZh}
                avatarSrc={speakerMeta.liptan.avatarSrc}
                accent={speakerMeta.liptan.accent}
                isLeft
                variant="seat"
              />
            </div>
            <div className="roundtable-seat roundtable-seat--cook">
              <RoleCard
                name={speakerMeta.cook.nameZh}
                school={speakerMeta.cook.subtitleZh}
                avatarSrc={speakerMeta.cook.avatarSrc}
                accent={speakerMeta.cook.accent}
                isLeft
                variant="seat"
              />
            </div>
            <div className="roundtable-seat roundtable-seat--jensen">
              <RoleCard
                name={speakerMeta.jensen.nameZh}
                school={speakerMeta.jensen.subtitleZh}
                avatarSrc={speakerMeta.jensen.avatarSrc}
                accent={speakerMeta.jensen.accent}
                isLeft
                variant="seat"
              />
            </div>
          </div>
        </div>

        <div className="controls-container">
          <button
            className="start-button"
            onClick={handleStart}
            disabled={isRunning}
          >
            {lexPreamble ? 'Lex 开场中…' : isRunning ? '对谈进行中...' : '开始对谈'}
          </button>

          {isDone && (
            <button className="download-button" onClick={handleDownload}>
              下载 Markdown 纪要
            </button>
          )}
        </div>

        <DebateAudio
          ref={debateAudioRef}
          runId={runId}
          enabled={audioEnabled}
          skipToJensenActive={skipForumSent}
          totalTurns={8}
        />

        {lexReviewTtsActive && runId && (
          <DebateAudio
            runId={runId}
            enabled={true}
            skipToJensenActive={false}
            totalTurns={1}
            lexReview={true}
          />
        )}

        {error && (
          <div className="error-box">
            <strong>运行提示</strong>：{error}
          </div>
        )}

        {!lexPreamble && loading && !runId && (
          <div className="loading-box">正在连接论坛服务器…</div>
        )}

        {!lexPreamble && isRunning && runId && turns.length === 0 && (
          <div className="loading-box">
            论坛交锋生成中：首位发言嘉宾为神秘 RISC-V 专家（RISC-V）——主持开场已由 Lex 完成。
          </div>
        )}

        {turns.length > 0 && (
          <div className="timeline-with-skip">
            <div className="timeline-container">
              {runId &&
                status === 'running' &&
                turns.length >= 1 &&
                turns.length < 6 &&
                !turns.some((t) => t.kind === 'jensen_vc') && (
                  <div className="jensen-vc-callout" aria-label="黄仁勋视频串场">
                    {!skipForumSent ? (
                      <>
                        <button
                          type="button"
                          className="jensen-vc-btn"
                          onClick={() => {
                            debateAudioRef.current?.skipNonJensenAudioToJensen()
                            const ph: Turn = {
                              round: 4,
                              speaker: 'jensen',
                              text: '[视频接入中，黄仁勋正在发言...]',
                              created_at: Date.now(),
                              kind: 'jensen_vc',
                            }
                            jensenPlaceholderRef.current = ph
                            setTurns((prev) => [...prev, ph])
                            setSkipForumSent(true)
                            void skipForumToJensen(runId)
                          }}
                        >
                          黄仁勋 Video Call
                        </button>
                        <p className="jensen-vc-hint">
                          跳过尚未生成的论坛尾段，直接进入黄仁勋视频串场环节。
                        </p>
                      </>
                    ) : (
                      <div className="jensen-vc-confirmed" aria-live="polite">
                        <div className="jensen-vc-confirmed-badge">已触发</div>
                        <div className="jensen-vc-confirmed-title">黄仁勋 Video Call</div>
                        <p className="jensen-vc-hint">系统将在当前神秘 RISC-V 专家发言结束后，切入黄仁勋视频串场。</p>
                        <div className="jensen-vc-loading">
                          <div className="jensen-vc-spinner" />
                          <span>正在生成黄仁勋串场内容，请稍候</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

              {(() => {
                const elements: React.ReactElement[] = []
                let currentRound = 0

                turns.forEach((turn) => {
                  if (turn.round !== currentRound) {
                    currentRound = turn.round
                    const k = turn.kind || 'forum'
                    let label = `第 ${currentRound} 轮`
                    if (k === 'jensen_vc') label = '黄仁勋 · 视频串场'
                    else if (k === 'liptan_tag') label = '陈立武 · 散场接话'
                    elements.push(
                      <div key={`round-${currentRound}-${k}`} className="round-divider">
                        <span>{label}</span>
                      </div>
                    )
                  }
                  elements.push(
                    <TurnMessage
                      key={`turn-${turn.created_at}`}
                      turn={turn}
                      displayTextOverride={
                        isJensenVcPlaceholder(turn)
                          ? jensenStreamText != null
                            ? jensenStreamText.length > 0
                              ? jensenStreamText
                              : '（模型流式输出中…）'
                            : undefined
                          : undefined
                      }
                      onSpeakSelection={
                        audioEnabled && runId
                          ? (speaker, text) => debateAudioRef.current?.speakSelection(speaker, text)
                          : undefined
                      }
                    />,
                  )
                })

                return elements
              })()}

              {isRunning && (
                <div className="waiting-text">正在等待下一位嘉宾回应...</div>
              )}
            </div>
          </div>
        )}

        {/* After debate done: Lex transition → then BET + Q&A */}
        {isDone && !lexTransitionDone && (
          <LexTransitionStage onFinished={() => setLexTransitionDone(true)} />
        )}

        {isDone && lexTransitionDone && !lexReviewVisible && (
          <div className="lex-section">
            <AudienceBetPanel />

            {runId && (
              <div className="audience-qa-box">
                <h2 className="audience-qa-title">观众提问</h2>
                <MasterChat runId={runId} />
                <div className="qa-end-area">
                  <button
                    className="qa-end-btn"
                    onClick={handleEndQa}
                    disabled={lexReviewLoading}
                  >
                    {lexReviewLoading ? '正在生成 Lex 锐评…' : '结束提问 · Lex 锐评'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Lex review visible after ending Q&A */}
        {judgeResult && lexReviewVisible && (
          <div className="lex-section">
            <div className="judge-box">
              <h2 className="judge-title">Lex 锐评</h2>
              <div className="judge-content">
                {renderCompareMarkdown(judgeResult)}
              </div>
            </div>
          </div>
        )}

        <footer className="app-footer">
          RISC-V 三国杀 · 公众科学日分会场 demo
        </footer>
      </div>
    </div>
  )
}

export default App
