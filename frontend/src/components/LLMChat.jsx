import React, { useEffect, useRef } from 'react';
import {
  explainError,
  giveHint,
  fixSchema,
  describeSchema,
  explainSchema,
  checkErrors,
} from '../api/exercises';

// Action catalogs: which questions the user can ask the LLM.
// `label` doubles as the button text and the user's chat message.
const WRONG_ACTIONS = [
  { key: 'explainError', label: 'What does this error mean?', fn: explainError },
  { key: 'hint',         label: 'Give me a hint',            fn: giveHint },
  { key: 'fix',          label: 'How can I fix my schema?',  fn: fixSchema },
];

const CORRECT_ACTIONS = [
  { key: 'describe', label: 'Describe my schema',             fn: describeSchema },
  { key: 'explain',  label: 'Explain my schema',             fn: explainSchema },
  { key: 'errors',   label: 'Does my schema have any errors?', fn: checkErrors },
];

function ChatMessage({ role, text, loading, error }) {
  const isUser = role === 'user';
  return (
    <div className={`chat-msg ${isUser ? 'chat-msg-user' : 'chat-msg-ai'}`}>
      <div className="chat-avatar">{isUser ? 'You' : 'LLM'}</div>
      <div className={`chat-bubble ${error ? 'chat-bubble-error' : ''}`}>
        {loading ? (
          <span className="chat-typing">Thinking…</span>
        ) : (
          <span style={{ whiteSpace: 'pre-wrap' }}>{text}</span>
        )}
      </div>
    </div>
  );
}

// llm prop comes from useLLM(): { messages, busy, ask, reset }
export default function LLMChat({ llm, isCorrect }) {
  const actions = isCorrect ? CORRECT_ACTIONS : WRONG_ACTIONS;
  const bottomRef = useRef(null);

  // Keep the latest message in view as the conversation grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [llm.messages]);

  return (
    <div className="llm-chat">
      <div className="chat-thread">
        <ChatMessage
          role="ai"
          text="Would you like to ask me anything about this result?"
        />
        {llm.messages.map(m => (
          <ChatMessage key={m.id} {...m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-actions">
        {actions.map(action => (
          <button
            key={action.key}
            className="secondary-btn"
            type="button"
            onClick={() => llm.ask(action)}
            disabled={llm.busy}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
