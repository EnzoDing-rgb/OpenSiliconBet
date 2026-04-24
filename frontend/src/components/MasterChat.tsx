import './MasterChat.css';
import { useState, useEffect, useRef } from 'react';
import { postChat } from '../api';
import type { Speaker, ChatMessage } from '../types';
import { markdownToSafeHtml } from '../utils/markdownRender';

interface MasterChatProps {
  runId: string;
}

export function MasterChat({ runId }: MasterChatProps) {
  const [speaker, setSpeaker] = useState<Speaker>('jervis');
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when chat updates
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
      // server already updated chat history in memory, we just fetch it from response
      setChatHistory(reply.chat_history);
    } catch (err: unknown) {
      console.error('Chat error', err);
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter (without Shift) → send; Shift+Enter → newline
    // Guard IME composition (e.g., Chinese Pinyin) to avoid accidental sends.
    const native = e.nativeEvent as KeyboardEvent
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const isComposing = (native as any).isComposing || (native as any).keyCode === 229

    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="master-chat-container">
      <div className="speaker-tabs">
        <button
          className={speaker === 'jervis' ? 'tab active' : 'tab'}
          onClick={() => setSpeaker('jervis')}
        >
          滴滴 Researcher
        </button>
        <button
          className={speaker === 'mearsheimer' ? 'tab active' : 'tab'}
          onClick={() => setSpeaker('mearsheimer')}
        >
          Manus Researcher
        </button>
      </div>

      <div className="chat-history">
        {chatHistory.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-speaker">
              {msg.role === 'user' ? (
                <>
                  国安学博士生
                  {msg.target_speaker && (
                    <span className="target-chip">@{msg.target_speaker === 'jervis' ? '滴滴 Researcher' : 'Manus Researcher'}</span>
                  )}
                </>
              ) : (
                msg.speaker === 'jervis' ? '滴滴 Researcher' : 'Manus Researcher'
              )}
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
          onClick={handleSend}
          disabled={sending || !message.trim()}
        >
          发送
        </button>
      </div>

      <div className="chat-hint">
        你可以追问某个论点 / 要求举例 / 请求更清晰的定义
      </div>
    </div>
  );
}
