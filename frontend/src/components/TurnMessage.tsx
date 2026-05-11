import './TurnMessage.css';
import type { Turn } from '../types';
import { getAvatarSrc, speakerMeta } from '../utils/avatars';
import { markdownToSafeHtml } from '../utils/markdownRender';

interface TurnMessageProps {
  turn: Turn;
}

export function TurnMessage({ turn }: TurnMessageProps) {
  const meta = speakerMeta[turn.speaker]
  const bubbleClass = `message-bubble speaker-${turn.speaker}`

  return (
    <div className="turn-container">
      <div className="avatar-small-wrap" style={{ ['--accent' as string]: meta.accent }}>
        <img className="avatar-small-img" src={getAvatarSrc(turn.speaker)} alt={meta.nameZh} />
      </div>
      <div className={bubbleClass}>
        <div className="speaker-name sr-only">{meta.nameZh}</div>
        <div
          className="message-text md-render"
          dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(turn.text) }}
        />
      </div>
    </div>
  );
}
