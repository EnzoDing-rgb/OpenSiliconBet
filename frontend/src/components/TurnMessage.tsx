import './TurnMessage.css';
import type { Turn } from '../types';
import { getAvatarSrc, speakerMeta } from '../utils/avatars';
import { markdownToSafeHtml } from '../utils/markdownRender';

interface TurnMessageProps {
  turn: Turn
  /** 覆盖气泡正文（如黄仁勋串场流式） */
  displayTextOverride?: string | null
}

export function TurnMessage({ turn, displayTextOverride }: TurnMessageProps) {
  const meta = speakerMeta[turn.speaker]
  const bubbleClass = `message-bubble speaker-${turn.speaker}`
  const isJensenVc = turn.kind === 'jensen_vc'
  const body = displayTextOverride ?? turn.text

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
      <div className={bubbleClass}>
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
