import { Bot, ChevronDown, LoaderCircle, Send, X } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  askChat,
  startChatSession,
  type ChatSessionState,
  type ChatTranscriptEntry,
} from '../api/chat';
import './Chatbot.css';

const DEFAULT_CITY = 'Miami';
const DEFAULT_DATE = '2020-06-17';

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [city, setCity] = useState(DEFAULT_CITY);
  const [date, setDate] = useState(DEFAULT_DATE);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatSessionState['messages']>([]);
  const [transcript, setTranscript] = useState<ChatTranscriptEntry[]>([]);
  const [sessionState, setSessionState] = useState<ChatSessionState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [transcript, isOpen]);

  const submitQuestion = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isLoading) return;

    setIsLoading(true);
    setError(null);
    try {
      const activeState = sessionState ?? (await startChatSession(city, date)).state;
      const response = await askChat(activeState, trimmedQuestion);
      setSessionState(response.state);
      setMessages(response.state.messages);
      setTranscript(response.transcript);
      setQuestion('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to reach the assistant.');
    } finally {
      setIsLoading(false);
    }
  };

  const resetSession = () => {
    setSessionState(null);
    setMessages([]);
    setTranscript([]);
    setQuestion('');
    setError(null);
  };

  return (
    <aside className={`chatbot ${isOpen ? 'chatbot--open' : ''}`} aria-label="Planning assistant">
      {isOpen && (
        <section className="chatbot__panel">
          <header className="chatbot__header">
            <div className="chatbot__identity">
              <span className="chatbot__identity-icon"><Bot size={18} /></span>
              <div>
                <p>Heat planning assistant</p>
                <span>{messages.length ? 'Session active' : 'Ready to plan'}</span>
              </div>
            </div>
            <button className="chatbot__icon-button" type="button" onClick={() => setIsOpen(false)} aria-label="Collapse chat" title="Collapse chat">
              <ChevronDown size={20} />
            </button>
          </header>

          <div className="chatbot__context">
            <label>
              City
              <input value={city} onChange={(event) => { setCity(event.target.value); resetSession(); }} />
            </label>
            <label>
              Date
              <input type="date" value={date} onChange={(event) => { setDate(event.target.value); resetSession(); }} />
            </label>
            <button type="button" className="chatbot__reset" onClick={resetSession}>New</button>
          </div>

          <div className="chatbot__transcript" ref={transcriptRef} aria-live="polite">
            {transcript.length === 0 ? (
              <p className="chatbot__empty">Ask about heat risk, destinations, or interventions for this scenario.</p>
            ) : transcript.map((entry, index) => (
              <article className={`chatbot__message chatbot__message--${entry.role}`} key={`${entry.role}-${index}`}>
                {entry.text}
              </article>
            ))}
            {isLoading && <p className="chatbot__loading"><LoaderCircle size={16} /> Thinking</p>}
            {error && <p className="chatbot__error">{error}</p>}
          </div>

          <form className="chatbot__composer" onSubmit={submitQuestion}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about this heat scenario"
              rows={2}
              disabled={isLoading}
            />
            <button type="submit" disabled={!question.trim() || isLoading} aria-label="Send question" title="Send question">
              <Send size={18} />
            </button>
          </form>
        </section>
      )}

      <button
        className="chatbot__toggle"
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
        title={isOpen ? 'Close chat' : 'Open chat'}
      >
        {isOpen ? <X size={22} /> : <Bot size={22} />}
      </button>
    </aside>
  );
}
