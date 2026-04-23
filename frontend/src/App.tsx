import { useState, useEffect, useCallback } from 'react'
import './App.css'
import { RoleCard } from './components/RoleCard'
import { TurnMessage } from './components/TurnMessage'
import { MasterChat } from './components/MasterChat.tsx'
import { DebateAudio } from './components/DebateAudio'
import { speakerMeta } from './utils/avatars'
import { startDebate, getDebateStatus, getDebateResult, downloadMarkdown } from './api'
import type { Turn, RunStatus } from './types'

function App() {
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [judgeResult, setJudgeResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [audioEnabled, setAudioEnabled] = useState(false)

  // Simple markdown render for judge result
  const renderJudgeMarkdown = (text: string) => {
    const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
    const out: string[] = []

    const flushParagraph = (buf: string[]) => {
      if (buf.length === 0) return
      const content = buf.join(' ').trim()
      if (content) out.push(`<p>${content}</p>`)
      buf.length = 0
    }

    const esc = (s: string) =>
      s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')

    const mdInline = (s: string) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

    const para: string[] = []
    let inUl = false
    const closeUl = () => {
      if (inUl) {
        out.push('</ul>')
        inUl = false
      }
    }

    for (const raw of lines) {
      const line = raw.trimRight()
      const trimmed = line.trim()

      if (!trimmed) {
        closeUl()
        flushParagraph(para)
        continue
      }

      const h = trimmed.match(/^#{2,6}\s+(.+)$/)
      if (h) {
        closeUl()
        flushParagraph(para)
        out.push(`<h3>${mdInline(h[1])}</h3>`)
        continue
      }

      const li = trimmed.match(/^(?:-|\d+\.)\s+(.+)$/)
      if (li) {
        flushParagraph(para)
        if (!inUl) {
          out.push('<ul>')
          inUl = true
        }
        out.push(`<li>${mdInline(li[1])}</li>`)
        continue
      }

      closeUl()
      para.push(mdInline(trimmed))
    }

    closeUl()
    flushParagraph(para)

    return <div className="md-render" dangerouslySetInnerHTML={{ __html: out.join('') }} />
  }

  const handleStart = useCallback(async () => {
    // Must be triggered by user gesture to allow autoplay audio
    setAudioEnabled(true)
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

  const handleDownload = useCallback(async () => {
    if (!runId) return
    const content = await getDebateResult(runId)
    downloadMarkdown(content, 'case_dialogue_result.md')
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
  const isRunning = status === 'running' || loading

  return (
    <div className="app-root">
      <div className="app-container">
        <header className="app-header">
          <h1>国家安全案例研究对谈</h1>
          <p className="topic">
            <strong>主题</strong>：滴滴数据安全案 vs Manus案（对比研究）
          </p>
        </header>

        <div className="roles-container">
          <RoleCard
            name={speakerMeta.jervis.nameZh}
            school={speakerMeta.jervis.subtitleZh}
            avatarSrc={speakerMeta.jervis.avatarSrc}
            accent={speakerMeta.jervis.accent}
            isLeft={true}
          />
          <RoleCard
            name={speakerMeta.mearsheimer.nameZh}
            school={speakerMeta.mearsheimer.subtitleZh}
            avatarSrc={speakerMeta.mearsheimer.avatarSrc}
            accent={speakerMeta.mearsheimer.accent}
            isLeft={false}
          />
        </div>

        <div className="controls-container">
          <button
            className="start-button"
            onClick={handleStart}
            disabled={isRunning}
          >
            {isRunning ? '对谈进行中...' : '开始对谈'}
          </button>

          {isDone && (
            <button className="download-button" onClick={handleDownload}>
              下载 Markdown 纪要
            </button>
          )}
        </div>

        <DebateAudio runId={runId} enabled={audioEnabled} />

        {error && (
          <div className="error-box">
            <strong>运行提示</strong>：{error}
          </div>
        )}

        {isRunning && turns.length === 0 && (
          <div className="loading-box">
            正在准备，请稍等第一位嘉宾开场...
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
            <h2 className="judge-title">对比小结</h2>
            <div className="judge-content">
              {renderJudgeMarkdown(judgeResult)}
            </div>
          </div>
        )}

        <footer className="app-footer">
          case-dialogue · Didi vs Manus
        </footer>
      </div>
      {runId && (
        <div className="master-chat-drawer">
          {!chatOpen && (
            <button
              className="master-chat-drawer-toggle"
              onClick={() => setChatOpen(true)}
              aria-label="展开与大师对话"
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
                  aria-label="收起与大师对话"
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
