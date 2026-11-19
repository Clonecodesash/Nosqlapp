import React from 'react';

// Pedagogical class of a finding (backend/error_taxonomy.py) -> badge label + colours.
const CLASS_STYLES = {
  syntax:       { label: 'Syntax error',             background: '#d32f2f', color: '#fff' },
  schema:       { label: 'Schema-dependent error',   background: '#b00020', color: '#fff' },
  workload:     { label: 'Workload-dependent error', background: '#c2410c', color: '#fff' },
  complication: { label: 'Complication',             background: '#1976d2', color: '#fff' },
  internal:     { label: 'Internal error',           background: '#475569', color: '#fff' },
};

// Feedback items may be structured objects ({ message, category, code, ... })
// or, for older stored logs, plain strings. Normalise both shapes here.
function normalizeItem(item) {
  if (typeof item === 'string') {
    return { message: item, category: null, code: null };
  }
  return item;
}

function location(item) {
  if (item.line != null && item.col != null) return `line ${item.line}, column ${item.col}`;
  return null;
}

function FindingList({ items }) {
  return (
    <ul className="query-list" style={{ marginTop: 8 }}>
      {items.map((raw, i) => {
        const item = normalizeItem(raw);
        const style = CLASS_STYLES[item.category];
        const where = location(item);
        return (
          <li key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            {style && (
              <span
                style={{
                  background: style.background,
                  color: style.color,
                  borderRadius: 4,
                  padding: '1px 6px',
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  flexShrink: 0,
                }}
              >
                {style.label}
              </span>
            )}
            <span>
              {item.message}
              {where && (
                <span style={{ marginLeft: 6, fontWeight: 600 }}>({where})</span>
              )}
              {item.code && (
                <span style={{ color: '#888', marginLeft: 6, fontSize: 12 }}>
                  {item.code}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// The verdict is binary: no grade is shown. A wrong answer shows the one
// finding reported by the engine; a correct answer lists its complications,
// if any, as suggestions for simplifying the design.
export default function EvaluationResult({ evaluation }) {
  if (!evaluation) return null;

  const { isCorrect, feedback } = evaluation;
  const items = feedback || [];

  return (
    <div className={`result-panel ${isCorrect ? 'result-panel-correct' : 'result-panel-wrong'}`}>
      <span className={`result-label ${isCorrect ? 'result-correct' : 'result-wrong'}`}>
        {isCorrect ? 'Correct' : 'Wrong'}
      </span>

      {!isCorrect && items.length > 0 && (
        <div className="feedback-box">
          <strong>What went wrong</strong>
          <FindingList items={items} />
        </div>
      )}

      {isCorrect && items.length > 0 && (
        <div className="feedback-box">
          <strong>Suggestions to simplify your design</strong>
          <FindingList items={items} />
        </div>
      )}
    </div>
  );
}
