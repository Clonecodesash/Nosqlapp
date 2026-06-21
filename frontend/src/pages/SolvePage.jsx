import React, { useState } from 'react';
import Topbar from '../components/Topbar';
import AnswerForm from '../components/AnswerForm';
import EvaluationResult from '../components/EvaluationResult';
import LLMChat from '../components/LLMChat';
import { submitAnswer } from '../api/exercises';
import { useLLM } from '../hooks/useLLM';

export default function SolvePage({
  token,
  role,
  username,
  schema,
  exercise,
  onLogout,
  onBack,
}) {
  const [answerText,    setAnswerText]    = useState('');
  const [evaluation,    setEvaluation]    = useState(null);
  const [submitting,    setSubmitting]    = useState(false);
  const [error,         setError]         = useState('');
  const [imgBroken,     setImgBroken]     = useState(false);

  const llm = useLLM(token, exercise.id);

  async function handleSubmit() {
    setError('');
    setSubmitting(true);
    llm.reset();
    // NOTE: answerText is intentionally NOT cleared here so the student
    // can still read, edit, and resubmit their answer after seeing feedback.
    try {
      const result = await submitAnswer(token, exercise.id, answerText);
      setEvaluation(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <Topbar role={role} username={username} onLogout={onLogout} />

      <main style={{ maxWidth: 860, margin: '0 auto', padding: '28px 24px' }}>
        {error && <div className="error-box" style={{ marginBottom: 14 }}>{error}</div>}

        <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h2>{exercise.name}</h2>
            <p>From: {schema.name}</p>
          </div>
          <button className="secondary-btn" type="button" onClick={onBack}>
            Back to exercises
          </button>
        </div>

        <div>
          <h3 style={{ marginBottom: 6 }}>Generate the aggregate schema, with regards to the ER Schema and the set of workload given</h3>
        </div>

       {/* ── Two-column: ER diagram left, queries right ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '7fr 4fr', gap: 20, marginBottom: 20 }}>

          {/* LEFT — ER schema image */}
          <div style={{ border: '1px solid #e1e7f0', borderRadius: 8, overflow: 'hidden', background: '#f8fafc' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #e1e7f0', fontSize: 13, fontWeight: 700, color: '#64748b' }}>
              ER Diagram — {schema.name}
            </div>
            {schema.image && !imgBroken ? (
              <img
                src={schema.image}
                alt={`ER diagram for ${schema.name}`}
                onError={() => setImgBroken(true)}
                style={{ display: 'block', width: '100%', height: 380, objectFit: 'contain', background: '#f8fafc' }}
              />
            ) : (
              <div className="image-fallback" style={{ height: 380 }}>
                ER diagram could not be displayed.
              </div>
            )}
          </div>

          {/* RIGHT — Queries */}
          <div style={{ border: '1px solid #e1e7f0', borderRadius: 8, background: '#fff', padding: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#64748b', marginBottom: 12 }}>
              Queries
            </div>
            <ul className="query-list">
              {exercise.queries?.map((q, i) => (
                <li key={q.id || i}>
                  <strong>Query {i + 1}: {q.queryText}</strong>
                </li>
              ))}
            </ul>
            {role === 'teacher' && exercise.answer && (
              <div className="answer-log" style={{ marginTop: 16 }}>
                <strong>Correct answer:</strong>
                <pre style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{exercise.answer.answer}</pre>
              </div>
            )}
          </div>
        </div>

        {/* ── Bottom — answer box + results (full width) ──
            Shown for everyone: students solve, teachers can test their own exercises. */}
        <article className="exercise-card">
          <div className="exercise-body">
            {role === 'teacher' && (
              <p className="eyebrow" style={{ marginBottom: 8 }}>
                Teacher preview — submit a trial answer to test this exercise
              </p>
            )}
            <AnswerForm
              value={answerText}
              onChange={setAnswerText}
              onSubmit={handleSubmit}
              loading={submitting}
            />
            {evaluation && (
              <>
                <EvaluationResult evaluation={evaluation} />
                <LLMChat
                  llm={llm}
                  isCorrect={evaluation.isCorrect}
                />
              </>
            )}
          </div>
        </article>
      </main>
    </div>
  );
}