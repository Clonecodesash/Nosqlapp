import React, { useEffect, useState } from 'react';
import Topbar from '../components/Topbar';
import ExerciseCard from '../components/ExerciseCard';
import TeacherSidebar from '../components/TeacherSidebar';
import { listExercises, createExercise, updateExercise } from '../api/exercises';

export default function ExercisesPage({
  token,
  role,
  schema,
  onLogout,
  onBack,
  onSelectExercise,
}) {
  const [exercises, setExercises] = useState([]);
  const [error,     setError]     = useState('');

  useEffect(() => {
    loadExercises();
  }, [schema.id]);

  async function loadExercises() {
    try {
      setExercises(await listExercises(token, schema.id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleExerciseSaved(editingId, payload) {
    if (editingId) {
      await updateExercise(token, editingId, payload);
    } else {
      await createExercise(token, payload);
    }
    await loadExercises();
  }

  return (
    <div className="app-shell">
      <Topbar role={role} onLogout={onLogout} />

      <main className="main-grid">
        {role === 'teacher' && (
          <TeacherSidebar
            selectedSchema={schema}
            onSchemaSaved={() => {}}
            onExerciseSaved={handleExerciseSaved}
          />
        )}

        <section className={role === 'teacher' ? '' : 'panel'}
          style={role !== 'teacher' ? { gridColumn: '1 / -1' } : undefined}>

          {error && <div className="error-box" style={{ marginBottom: 14 }}>{error}</div>}

          <div className="section-title">
            <div>
              <h2>{schema.name}</h2>
              <p>Exercises for this schema</p>
            </div>
            <div className="row-actions">
              <button className="secondary-btn" type="button" onClick={onBack}>
                Back to schemas
              </button>
              <span className="count-badge">{exercises.length} exercises</span>
            </div>
          </div>

          {exercises.length === 0 ? (
            <div className="empty-state">No exercises for this schema yet.</div>
          ) : (
            <div className="exercise-list">
              {exercises.map(exercise => (
                <ExerciseCard
                  key={exercise.id}
                  exercise={exercise}
                  role={role}
                  onClick={() => onSelectExercise(exercise)}
                  onEdit={() => {}}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
