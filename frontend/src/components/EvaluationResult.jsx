import React from 'react';

export default function EvaluationResult({ evaluation }) {
  if (!evaluation) return null;

  const { isCorrect, score, feedback } = evaluation;

  return (
    <div className="answer-log">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span className={`result-label ${isCorrect ? 'result-correct' : 'result-wrong'}`}>
          {isCorrect ? 'Correct' : 'Needs work'}
        </span>
        
      </div>

      {feedback?.length > 0 && (
        <div className="feedback-box" style={{ marginTop: 12 }}>
          <strong>Evaluation feedback</strong>
          <ul className="query-list" style={{ marginTop: 8 }}>
            {feedback.map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
