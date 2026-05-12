import { useState, useEffect, useCallback } from 'react'
import './App.css'
import { RoleCard } from './components/RoleCard'
import { TurnMessage } from './components/TurnMessage'
import { MasterChat } from './components/MasterChat.tsx'
import { DebateAudio } from './components/DebateAudio'
import { LexOpeningStage } from './components/LexOpeningStage'
import { speakerMeta } from './utils/avatars'
import { markdownToSafeHtml } from './utils/markdownRender'
import { startDebate, getDebateStatus, getDebateResult, downloadMarkdown } from './api'
import type { Turn, RunStatus } from './types'

const KEYNOTE_IMAGE_SRC = '/images/summit-cas-iss-keynote.png'

function App() {
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [judgeResult, setJudgeResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [audioEnabled, setAudioEnabled] = useState(false)
  /** 架构 §1：阶段 0 / 0.5 由 Lex 垫场 + 预录开场，完成后再请求后端论坛交锋（阶段 1） */
  const [lexPreamble, setLexPreamble] = useState(false)

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
    setChatOpen(false)
    try {
      const id = await startDebate()
      setRunId(id)
    } catch (e) {
      setError(`无法启动对谈：${e}`)
      setLoading(false)
    }
  }, [])

  const handleStart = useCallback(() => {
    // 用户手势：解锁后续 TTS / 预录 mp3 autoplay
    setAudioEnabled(true)
    setError(null)
    setLexPreamble(true)
  }, [])

  const handleDownload = useCallback(async () => {
    if (!runId) return
    const content = await getDebateResult(runId)
    downloadMarkdown(content, 'riscv_forum_result.md')
  }, [runId])

  // Polling
  useEffect(() => {
    if (!runId || status === 'done' || status === 'error') {
      if (status === 'done' || status === 'error') {
        setLoading(false)
      }
      return
    }

    const interval = setInterval(async () => {
      if (!runId) return
      try {
        const data = await getDebateStatus(runId)
        setStatus(data.status)
        setTurns(data.turns)
        if (data.error) {
          setError(data.error)
        }
        if (data.judge_result) {
          setJudgeResult(data.judge_result)
        }
      } catch (e) {
        console.error('Polling error', e)
      }
    }, 1500)

    return () => clearInterval(interval)
  }, [runId, status])

  const isDone = status === 'done'
  const isRunning = status === 'running' || loading || lexPreamble

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
            alt="中科院软件所讲堂 · AI Summit 会场示意（RISC-V vs x86 vs ARM）"
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

        <DebateAudio runId={runId} enabled={audioEnabled} totalTurns={6} />

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
            论坛交锋生成中：首位发言嘉宾为吴伟（RISC-V）——主持开场已由 Lex 完成。
          </div>
        )}

        {turns.length > 0 && (
          <div className="timeline-container">
            {(() => {
              const elements: React.ReactElement[] = []
              let currentRound = 0

              turns.forEach((turn) => {
                if (turn.round !== currentRound) {
                  currentRound = turn.round
                  elements.push(
                    <div key={`round-${currentRound}`} className="round-divider">
                      <span>第 {currentRound} 轮</span>
                    </div>
                  )
                }
                elements.push(<TurnMessage key={`turn-${turn.created_at}`} turn={turn} />)
              })

              return elements
            })()}

            {isRunning && (
              <div className="waiting-text">正在等待下一位嘉宾回应...</div>
            )}
          </div>
        )}

        {judgeResult && (
          <div className="judge-box">
            <h2 className="judge-title">论坛纪要</h2>
            <div className="judge-content">
              {renderCompareMarkdown(judgeResult)}
            </div>
          </div>
        )}

        <footer className="app-footer">
          RISC-V 三国杀 · 公众科学日分会场 demo
        </footer>
      </div>
      {runId && (
        <div className="master-chat-drawer">
          {!chatOpen && (
            <button
              className="master-chat-drawer-toggle"
              onClick={() => setChatOpen(true)}
              aria-label="展开与研究者对话"
            >
              与研究者对话
            </button>
          )}
          {chatOpen && (
            <div className="master-chat-drawer-panel">
              <div className="master-chat-drawer-header">
                <div className="master-chat-drawer-title">与研究者对话</div>
                <button
                  className="master-chat-drawer-close"
                  onClick={() => setChatOpen(false)}
                  aria-label="收起与研究者对话"
                >
                  收起
                </button>
              </div>
              <MasterChat runId={runId} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
