import './MasterChat.css';
import { useState, useEffect, useRef } from 'react';
import { postChat } from '../api';
import type { Speaker, ChatMessage } from '../types';
import { markdownToSafeHtml } from '../utils/markdownRender';
import { speakerLabelZh } from '../utils/avatars';

const CHAT_SPEAKERS: Speaker[] = ['lex', 'wuwei', 'liptan', 'cook', 'jensen'];

interface MasterChatProps {
  runId: string;
  onSpeakSelection?: (speaker: Speaker, text: string) => void;
}

export function MasterChat({ runId, onSpeakSelection }: MasterChatProps) {
  const [speaker, setSpeaker] = useState<Speaker>('wuwei');
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);

  const handleSend = async () => {
    const trimmed = message.trim();
    if (!trimmed || !runId || sending) return;

    const now = Date.now();
    const optimisticUserMsg: ChatMessage = {
      role: 'user',
      speaker: 'user',
      target_speaker: speaker,
      content: trimmed,
      created_at: now,
    };

    setSending(true);
    setError(null);
    setChatHistory((prev) => [...prev, optimisticUserMsg]);
    setMessage('');
    try {
      const reply = await postChat(runId, speaker, trimmed);
      setChatHistory(reply.chat_history);
      // Play the assistant's reply via TTS
      if (onSpeakSelection && reply.chat_history.length > 0) {
        const lastMsg = reply.chat_history[reply.chat_history.length - 1];
        if (lastMsg.role === 'assistant' && lastMsg.content) {
          onSpeakSelection(lastMsg.speaker as Speaker, lastMsg.content);
        }
      }
    } catch (err: unknown) {
      console.error('Chat error', err);
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const native = e.nativeEvent as KeyboardEvent
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const isComposing = (native as any).isComposing || (native as any).keyCode === 229

    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const labelForMsgSpeaker = (s: ChatMessage['speaker'], target?: Speaker) => {
    if (s === 'user') {
      return (
        <>
          观众
          {target && (
            <span className="target-chip">@{speakerLabelZh(target)}</span>
          )}
        </>
      );
    }
    return speakerLabelZh(s as Speaker);
  };

  return (
    <div className="master-chat-container">
      <div className="master-chat-header">
        <div>
          <div className="master-chat-eyebrow">Audience Q&A</div>
          <div className="master-chat-title">选择一位嘉宾，继续追问</div>
        </div>
        <div className="master-chat-status">{sending ? '嘉宾思考中…' : `当前对象：${speakerLabelZh(speaker)}`}</div>
      </div>

      <div className="speaker-tabs">
        {CHAT_SPEAKERS.map((s) => (
          <button
            key={s}
            type="button"
            className={speaker === s ? 'tab active' : 'tab'}
            onClick={() => setSpeaker(s)}
          >
            {speakerLabelZh(s)}
          </button>
        ))}
      </div>

      <div className="chat-history">
        {chatHistory.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-speaker">
              {labelForMsgSpeaker(msg.speaker, msg.target_speaker)}
            </div>
            <div
              className="chat-content md-render"
              dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(msg.content) }}
            />
          </div>
        ))}
        {sending && <div className="chat-loading">正在生成回复...</div>}
        {error && <div className="chat-error">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-container">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题... (Enter发送，Shift+Enter换行)"
          disabled={sending}
        />
        <button
          className="send-button"
          onClick={() => void handleSend()}
          disabled={sending || !message.trim()}
        >
          发送
        </button>
      </div>

      <div className="chat-hint">
        可选择嘉宾标签后追问；口径以共享事实档案与角色 SKILL 为准。
      </div>
    </div>
  );
}
