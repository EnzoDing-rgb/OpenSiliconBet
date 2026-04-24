import './TurnMessage.css';
import type { Turn } from '../types';
import { getAvatarSrc, speakerMeta } from '../utils/avatars';
import { markdownToSafeHtml } from '../utils/markdownRender';

interface TurnMessageProps {
  turn: Turn;
}

export function TurnMessage({ turn }: TurnMessageProps) {
  const isJervis = turn.speaker === 'jervis';
  const alignRight = !isJervis;

  return (
    <div className={`turn-container ${alignRight ? 'align-right' : ''}`}>
      <div className="avatar-small-wrap" style={{ ['--accent' as string]: speakerMeta[turn.speaker].accent }}>
        <img className="avatar-small-img" src={getAvatarSrc(turn.speaker)} alt={speakerMeta[turn.speaker].nameZh} />
      </div>
      <div className={`message-bubble ${isJervis ? 'jervis' : 'mearsheimer'}`}>
        <div className="speaker-name">{speakerMeta[turn.speaker].nameZh}</div>
        <div
          className="message-text md-render"
          dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(turn.text) }}
        />
      </div>
    </div>
  );
}
