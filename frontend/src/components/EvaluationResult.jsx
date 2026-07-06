import React from 'react';

// Maps a taxonomy severity to a small coloured badge label.
const SEVERITY_STYLES = {
  critical: { background: '#b00020', color: '#fff' },
  error: { background: '#d32f2f', color: '#fff' },
  warning: { background: '#f9a825', color: '#000' },
  info: { background: '#1976d2', color: '#fff' },
};

// Feedback items may be structured objects ({ message, severity, code, ... })
// or, for older stored logs, plain strings. Normalise both shapes here.
function normalizeItem(item) {
  if (typeof item === 'string') {
    return { message: item, severity: 'info', code: null };
  }
  return item;
}

export default function EvaluationResult({ evaluation }) {
  if (!evaluation) return null;

  const { isCorrect, feedback } = evaluation;

  return (
    <div className={`result-panel ${isCorrect ? 'result-panel-correct' : 'result-panel-wrong'}`}>
      <span className={`result-label ${isCorrect ? 'result-correct' : 'result-wrong'}`}>
        {isCorrect ? 'Correct' : 'Wrong'}
      </span>

      {!isCorrect && feedback?.length > 0 && (
        <div className="feedback-box" style={{ marginTop: 12 }}>
          <strong>What went wrong</strong>
          <ul className="query-list" style={{ marginTop: 8 }}>
            {feedback.map((raw, i) => {
              const item = normalizeItem(raw);
              const badge = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.info;
              return (
                <li key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  {item.severity && (
                    <span
                      style={{
                        ...badge,
                        borderRadius: 4,
                        padding: '1px 6px',
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        flexShrink: 0,
                      }}
                    >
                      {item.severity}
                    </span>
                  )}
                  <span>
                    {item.message}
                    {item.code && (
                      <span style={{ color: '#888', marginLeft: 6, fontSize: 12 }}>
                        ({item.code})
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
