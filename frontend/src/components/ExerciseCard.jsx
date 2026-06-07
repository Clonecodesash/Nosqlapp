import React from 'react';

export default function ExerciseCard({ exercise, role, onClick, onEdit, onDelete }) {
  return (
    <article
      className="exercise-card exercise-card-clickable"
      onClick={onClick}
    >
      <div className="exercise-body">
        <div className="meta-row">
          <h3>{exercise.name}</h3>
          <div className="row-actions">
            <span className="count-badge">
              {exercise.queries?.length || 0} queries
            </span>
            {role === 'teacher' && (
              <>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={e => { e.stopPropagation(); onEdit(exercise); }}
                >
                  Edit
                </button>
                <button
                  className="secondary-btn danger-btn"
                  type="button"
                  onClick={e => { e.stopPropagation(); onDelete(exercise); }}
                >
                  Delete
                </button>
              </>
            )}
          </div>
        </div>

        <ul className="query-list">
          {exercise.queries?.map((q, i) => (
            <li key={q.id || i}><strong>{q.queryText}</strong></li>
          ))}
        </ul>

        {role === 'teacher' && exercise.answer && (
          <div className="answer-log">
            <strong>Correct answer:</strong> {exercise.answer.answer}
          </div>
        )}

        {role === 'student' && (
          <button
            className="primary-btn"
            type="button"
            style={{ marginTop: 12 }}
            onClick={e => { e.stopPropagation(); onClick(); }}
          >
            Open exercise
          </button>
        )}
      </div>
    </article>
  );
}
