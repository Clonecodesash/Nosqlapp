import React from 'react';

export default function AnswerForm({ value, onChange, onSubmit, loading }) {
  return (
    <form
      className="form"
      onSubmit={e => { e.preventDefault(); onSubmit(); }}
      style={{ marginTop: 16 }}
    >
      <label className="field">
        Your answer
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={6}
          placeholder="Write your aggregate schema here..."
          required
        />
      </label>
      <button className="primary-btn" type="submit" disabled={loading}>
        {loading ? 'Submitting…' : 'Submit answer'}
      </button>
    </form>
  );
}
