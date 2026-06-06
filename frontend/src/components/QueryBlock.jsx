import React from 'react';

export default function QueryBlock({ query, index, onChange, onRemove, canRemove }) {
  return (
    <div className="query-block">
      <label className="field">
        Query text
        <textarea
          value={query.queryText}
          onChange={e => onChange(index, 'queryText', e.target.value)}
          rows={2}
          required
        />
      </label>
      <label className="field" style={{ marginTop: 12 }}>
        Hint
        <input
          type="text"
          value={query.hint}
          onChange={e => onChange(index, 'hint', e.target.value)}
          placeholder="Optional hint for students"
        />
      </label>
      {canRemove && (
        <button
          className="secondary-btn danger-btn"
          type="button"
          onClick={() => onRemove(index)}
          style={{ marginTop: 12 }}
        >
          Remove query
        </button>
      )}
    </div>
  );
}
