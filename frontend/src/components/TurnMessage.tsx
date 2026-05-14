import { useRef } from 'react'
import './TurnMessage.css'
import type { Speaker, Turn } from '../types'
import { getAvatarSrc, speakerMeta } from '../utils/avatars'
import { markdownToSafeHtml } from '../utils/markdownRender'

interface TurnMessageProps {
  turn: Turn
  /** 覆盖气泡正文（如黄仁勋串场流式） */
  displayTextOverride?: string | null
  /** 气泡内选中文字 → 用该讲者 Voice 读（仅 jensen_vc / liptan_tag） */
  onSpeakSelection?: (speaker: Speaker, text: string) => void
}

export function TurnMessage({ turn, displayTextOverride, onSpeakSelection }: TurnMessageProps) {
  const bubbleRef = useRef<HTMLDivElement>(null)
  const meta = speakerMeta[turn.speaker]
  const bubbleClass = `message-bubble speaker-${turn.speaker}`
  const isJensenVc = turn.kind === 'jensen_vc'
  const isLiptanTag = turn.kind === 'liptan_tag'
  const allowSelectionTts =
    !!onSpeakSelection &&
    ((isJensenVc && turn.speaker === 'jensen') || (isLiptanTag && turn.speaker === 'liptan'))
  const body = displayTextOverride ?? turn.text

  const handleMouseUp = () => {
    if (!allowSelectionTts) return
    const root = bubbleRef.current
    if (!root) return
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return
    const a = sel.anchorNode
    const f = sel.focusNode
    if (!a || !f) return
    if (!root.contains(a) || !root.contains(f)) return
    const t = sel.toString().trim()
    if (t.length < 2) return
    onSpeakSelection(turn.speaker, t)
  }

  return (
    <div className={isJensenVc ? 'turn-block turn-block--jensen-vc' : 'turn-block'}>
      {isJensenVc && (
        <div className="jensen-vc-banner" role="presentation">
          <div className="jensen-vc-frame-wrap">
            <img src={getAvatarSrc('jensen')} alt="" className="jensen-vc-frame" />
          </div>
          <span className="jensen-vc-badge">Video call · 示意</span>
        </div>
      )}
      <div className="turn-container">
      <div className="avatar-small-wrap" style={{ ['--accent' as string]: meta.accent }}>
        <img className="avatar-small-img" src={getAvatarSrc(turn.speaker)} alt={meta.nameZh} />
      </div>
      <div className={bubbleClass} ref={bubbleRef} onMouseUp={handleMouseUp}>
        <div className="speaker-name sr-only">{meta.nameZh}</div>
        <div
          className="message-text md-render"
          dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(body) }}
        />
      </div>
    </div>
    </div>
  );
}
