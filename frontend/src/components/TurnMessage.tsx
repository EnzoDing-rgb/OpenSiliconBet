import './TurnMessage.css';
import type { Turn } from '../types';
import { getAvatarSrc, speakerMeta } from '../utils/avatars';

interface TurnMessageProps {
  turn: Turn;
}

// Very simple markdown parser for basic formatting: **bold** -> <strong>, line breaks -> <br>
function renderMarkdown(text: string) {
  // Replace **text** with <strong>text</strong>
  let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Replace single newlines with <br>
  html = html.replace(/\n/g, '<br />');
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
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
        <div className="message-text">{renderMarkdown(turn.text)}</div>
      </div>
    </div>
  );
}
