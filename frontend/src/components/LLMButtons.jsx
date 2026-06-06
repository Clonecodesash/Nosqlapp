import React from 'react';

function LLMPanel({ open, data, borderColor, label }) {
  if (!open || !data) return null;
  return (
    <div className="review-box" style={{ borderColor, marginTop: 12 }}>
      <strong>{label}</strong>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{data}</pre>
    </div>
  );
}

// llm prop comes from useLLM() hook:
// { explainError, hint, fix, success } — each has { data, loading, open, handle }
export default function LLMButtons({ llm, isCorrect, onViewAnswer, correctAnswer }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div className="row-actions">
        {!isCorrect ? (
          <>
            <button
              className="secondary-btn"
              type="button"
              onClick={llm.explainError.handle}
              disabled={llm.explainError.loading}
            >
              {llm.explainError.loading ? 'Analyzing…' : 'Explain error'}
            </button>

            <button
              className="secondary-btn"
              type="button"
              onClick={llm.hint.handle}
              disabled={llm.hint.loading}
            >
              {llm.hint.loading ? 'Thinking…' : 'Give me a hint'}
            </button>

            <button
              className="secondary-btn"
              type="button"
              onClick={llm.fix.handle}
              disabled={llm.fix.loading}
            >
              {llm.fix.loading ? 'Fixing…' : 'Fix my schema'}
            </button>
          </>
        ) : (
          <button
            className="secondary-btn"
            type="button"
            onClick={llm.success.handle}
            disabled={llm.success.loading}
          >
            {llm.success.loading ? 'Loading…' : 'Why is this correct?'}
          </button>
        )}

        <button className="secondary-btn" type="button" onClick={onViewAnswer}>
          View reference answer
        </button>
      </div>

      <LLMPanel
        open={llm.explainError.open}
        data={llm.explainError.data}
        borderColor="#ef4444"
        label="Error explanation"
      />
      <LLMPanel
        open={llm.hint.open}
        data={llm.hint.data}
        borderColor="#3b82f6"
        label="Hint"
      />
      <LLMPanel
        open={llm.fix.open}
        data={llm.fix.data}
        borderColor="#10b981"
        label="Corrected schema"
      />
      <LLMPanel
        open={llm.success.open}
        data={llm.success.data}
        borderColor="#8b5cf6"
        label="Why it is correct"
      />

      {correctAnswer && (
        <div className="review-box" style={{ marginTop: 12 }}>
          <strong>Reference answer</strong>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{correctAnswer}</pre>
        </div>
      )}
    </div>
  );
}
