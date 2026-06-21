import { useRef, useState } from 'react';

// One hook owns the LLM conversation state so SolvePage and the chat UI stay clean.
// The conversation is an ordered list of messages:
//   { id, role: 'user' | 'ai', text, loading?, error? }
// Clicking an action button appends the user's question, then the AI reply.
// Buttons stay available, so the same question can be asked again to continue the chat.

export function useLLM(token, exerciseId) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const nextId = useRef(0);

  // Reset the conversation when the student submits a new answer
  function reset() {
    setMessages([]);
    setBusy(false);
  }

  // action: { label, fn }  — fn(token, exerciseId) resolves to { explanation }
  async function ask(action) {
    if (busy) return;

    const pendingId = nextId.current++;
    setMessages(prev => [
      ...prev,
      { id: nextId.current++, role: 'user', text: action.label },
      { id: pendingId, role: 'ai', text: '', loading: true },
    ]);
    setBusy(true);

    try {
      const data = await action.fn(token, exerciseId);
      setMessages(prev =>
        prev.map(m =>
          m.id === pendingId ? { ...m, text: data.explanation, loading: false } : m
        )
      );
    } catch (err) {
      setMessages(prev =>
        prev.map(m =>
          m.id === pendingId
            ? { ...m, text: `Sorry, something went wrong: ${err.message}`, loading: false, error: true }
            : m
        )
      );
    } finally {
      setBusy(false);
    }
  }

  return { messages, busy, reset, ask };
}
