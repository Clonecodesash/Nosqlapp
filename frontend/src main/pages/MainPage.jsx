import React, { useEffect, useState } from 'react';

function MainPage({ token, role, onLogout }) {
  const [schemas, setSchemas] = useState([]);
  const [exercises, setExercises] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [answerForms, setAnswerForms] = useState({});
  const [evaluations, setEvaluations] = useState({});
  const [brokenImages, setBrokenImages] = useState({});

  // Separated LLM UI States
  const [explainErrorOpen, setExplainErrorOpen] = useState({});
  const [explainErrorData, setExplainErrorData] = useState({});
  const [explainErrorLoading, setExplainErrorLoading] = useState({});

  const [llmHintOpen, setLlmHintOpen] = useState({});
  const [llmHintData, setLlmHintData] = useState({});
  const [llmHintLoading, setLlmHintLoading] = useState({});

  const [fixSchemaOpen, setFixSchemaOpen] = useState({});
  const [fixSchemaData, setFixSchemaData] = useState({});
  const [fixSchemaLoading, setFixSchemaLoading] = useState({});

  const [explainSuccessOpen, setExplainSuccessOpen] = useState({});
  const [explainSuccessData, setExplainSuccessData] = useState({});
  const [explainSuccessLoading, setExplainSuccessLoading] = useState({});

  // Static items from DB
  const [correctAnswerOpen, setCorrectAnswerOpen] = useState({});
  const [correctAnswers, setCorrectAnswers] = useState({});
  
  // Navigation state
  const [selectedSchemaId, setSelectedSchemaId] = useState(null);
  const [selectedExerciseId, setSelectedExerciseId] = useState(null);
  
  // Form state for schemas
  const [editingSchemaId, setEditingSchemaId] = useState(null);
  const [schemaForm, setSchemaForm] = useState({
    name: '',
    image: null,
  });
  
  // Form state for exercises
  const [editingExerciseId, setEditingExerciseId] = useState(null);
  const [exerciseForm, setExerciseForm] = useState({
    name: '',
    answer: '',
    queries: [{ queryText: '', hint: '' }],
  });

  const authHeaders = {
    Authorization: `Bearer ${token}`,
  };

  // Load schemas
  const loadSchemas = async () => {
    try {
      const res = await fetch('/api/schemas', { headers: authHeaders });
      if (!res.ok) {
        setError('Failed to load schemas');
        return;
      }
      setSchemas(await res.json());
    } catch (err) {
      setError('Network error loading schemas');
    }
  };

  // Load exercises for a specific schema
  const loadExercisesForSchema = async (schemaId) => {
    try {
      const res = await fetch(`/api/schemas/${schemaId}/exercises`, { headers: authHeaders });
      if (!res.ok) {
        setError('Failed to load exercises');
        return;
      }
      setExercises(await res.json());
    } catch (err) {
      setError('Network error loading exercises');
    }
  };

  useEffect(() => {
    if (token) {
      loadSchemas();
    }
  }, [token]);

  // ===== SCHEMA HANDLERS =====
  const resetSchemaForm = () => {
    setEditingSchemaId(null);
    setSchemaForm({ name: '', image: null });
  };

  const startEditSchema = (schema) => {
    setError('');
    setSuccess('');
    setEditingSchemaId(schema.id);
    setSchemaForm({ name: schema.name, image: null });
  };

  const saveSchema = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!editingSchemaId && !schemaForm.image) {
      setError('Please upload a schema image');
      return;
    }

    const formData = new FormData();
    formData.append('name', schemaForm.name);
    if (schemaForm.image) {
      formData.append('image', schemaForm.image);
    }

    const res = await fetch(editingSchemaId ? `/api/schemas/${editingSchemaId}` : '/api/schemas', {
      method: editingSchemaId ? 'PUT' : 'POST',
      headers: authHeaders,
      body: formData,
    });

    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      setError(detail?.detail || 'Failed to save schema');
      return;
    }

    const savedSchema = await res.json();
    setSchemas(current => [
      savedSchema,
      ...current.filter(schema => schema.id !== savedSchema.id),
    ]);
    setBrokenImages(current => {
      const next = { ...current };
      delete next[savedSchema.id];
      return next;
    });
    resetSchemaForm();
    setSuccess(editingSchemaId ? 'Schema updated' : 'Schema created');
    await loadSchemas();
  };

  // ===== EXERCISE HANDLERS =====
  const resetExerciseForm = () => {
    setEditingExerciseId(null);
    setExerciseForm({
      name: '',
      answer: '',
      queries: [{ queryText: '', hint: '' }],
    });
  };

  const startEditExercise = (exercise) => {
    setError('');
    setSuccess('');
    setEditingExerciseId(exercise.id);
    setExerciseForm({
      name: exercise.name,
      answer: exercise.answer?.answer || '',
      queries: exercise.queries ? exercise.queries.map(query => ({
        queryText: query.queryText,
        hint: query.hint || '',
      })) : [{ queryText: '', hint: '' }],
    });
  };

  const updateQuery = (index, field, value) => {
    setExerciseForm(current => ({
      ...current,
      queries: current.queries.map((query, queryIndex) =>
        queryIndex === index ? { ...query, [field]: value } : query
      ),
    }));
  };

  const addQuery = () => {
    setExerciseForm(current => ({
      ...current,
      queries: [...current.queries, { queryText: '', hint: '' }],
    }));
  };

  const removeQuery = (index) => {
    setExerciseForm(current => ({
      ...current,
      queries: current.queries.filter((_, queryIndex) => queryIndex !== index),
    }));
  };

  const saveExercise = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!selectedSchemaId) {
      setError('Please select a schema first');
      return;
    }

    const payload = {
      name: exerciseForm.name,
      answer: exerciseForm.answer,
      queries: exerciseForm.queries,
      schemaId: selectedSchemaId,
    };

    const res = await fetch(editingExerciseId ? `/api/exercises/${editingExerciseId}` : '/api/exercises', {
      method: editingExerciseId ? 'PUT' : 'POST',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      setError(detail?.detail || 'Failed to save exercise');
      return;
    }

    const savedExercise = await res.json();
    setExercises(current => [
      savedExercise,
      ...current.filter(exercise => exercise.id !== savedExercise.id),
    ]);
    resetExerciseForm();
    setSuccess(editingExerciseId ? 'Exercise updated' : 'Exercise created');
    await loadExercisesForSchema(selectedSchemaId);
  };

  // ===== STUDENT SUBMISSION & DETAILED LLM BUTTON ACTIONS =====
  const submitStudentAnswer = async (event, exerciseId) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    const res = await fetch(`/api/exercises/${exerciseId}/answers`, {
      method: 'POST',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ answer: answerForms[exerciseId] || '' }),
    });

    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      setError(detail?.detail || 'Failed to submit answer');
      return;
    }

    const evaluation = await res.json();
    setEvaluations(current => ({ ...current, [exerciseId]: evaluation }));
    
    // Wipe layout visibility state for clean redraws
    setExplainErrorOpen(current => ({ ...current, [exerciseId]: false }));
    setLlmHintOpen(current => ({ ...current, [exerciseId]: false }));
    setFixSchemaOpen(current => ({ ...current, [exerciseId]: false }));
    setExplainSuccessOpen(current => ({ ...current, [exerciseId]: false }));
    setCorrectAnswerOpen(current => ({ ...current, [exerciseId]: false }));
    
    setSuccess('Answer evaluated successfully!');
  };

  // Action 1: Explain Error
  const handleExplainError = async (exerciseId) => {
    if (explainErrorData[exerciseId]) {
      setExplainErrorOpen(curr => ({ ...curr, [exerciseId]: !curr[exerciseId] }));
      return;
    }
    setExplainErrorLoading(curr => ({ ...curr, [exerciseId]: true }));
    try {
      const res = await fetch(`/api/exercises/${exerciseId}/explain-error`, { method: 'POST', headers: authHeaders });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setExplainErrorData(curr => ({ ...curr, [exerciseId]: data.explanation }));
      setExplainErrorOpen(curr => ({ ...curr, [exerciseId]: true }));
    } catch {
      setError('Could not fetch structural details');
    } finally {
      setExplainErrorLoading(curr => ({ ...curr, [exerciseId]: false }));
    }
  };

  // Action 2: Give Me a Hint
  const handleGiveHint = async (exerciseId) => {
    if (llmHintData[exerciseId]) {
      setLlmHintOpen(curr => ({ ...curr, [exerciseId]: !curr[exerciseId] }));
      return;
    }
    setLlmHintLoading(curr => ({ ...curr, [exerciseId]: true }));
    try {
      const res = await fetch(`/api/exercises/${exerciseId}/give-hint`, { method: 'POST', headers: authHeaders });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setLlmHintData(curr => ({ ...curr, [exerciseId]: data.explanation }));
      setLlmHintOpen(curr => ({ ...curr, [exerciseId]: true }));
    } catch {
      setError('Could not fetch guidance details');
    } finally {
      setLlmHintLoading(curr => ({ ...curr, [exerciseId]: false }));
    }
  };

  // Action 3: Fix My Schema
  const handleFixSchema = async (exerciseId) => {
    if (fixSchemaData[exerciseId]) {
      setFixSchemaOpen(curr => ({ ...curr, [exerciseId]: !curr[exerciseId] }));
      return;
    }
    setFixSchemaLoading(curr => ({ ...curr, [exerciseId]: true }));
    try {
      const res = await fetch(`/api/exercises/${exerciseId}/fix-schema`, { method: 'POST', headers: authHeaders });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setFixSchemaData(curr => ({ ...curr, [exerciseId]: data.explanation }));
      setFixSchemaOpen(curr => ({ ...curr, [exerciseId]: true }));
    } catch {
      setError('Could not generate correction paths');
    } finally {
      setFixSchemaLoading(curr => ({ ...curr, [exerciseId]: false }));
    }
  };

  // Action 4: Explain Why It's Correct
  const handleExplainSuccess = async (exerciseId) => {
    if (explainSuccessData[exerciseId]) {
      setExplainSuccessOpen(curr => ({ ...curr, [exerciseId]: !curr[exerciseId] }));
      return;
    }
    setExplainSuccessLoading(curr => ({ ...curr, [exerciseId]: true }));
    try {
      const res = await fetch(`/api/exercises/${exerciseId}/explain-success`, { method: 'POST', headers: authHeaders });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setExplainSuccessData(curr => ({ ...curr, [exerciseId]: data.explanation }));
      setExplainSuccessOpen(curr => ({ ...curr, [exerciseId]: true }));
    } catch {
      setError('Could not process success validation details');
    } finally {
      setExplainSuccessLoading(curr => ({ ...curr, [exerciseId]: false }));
    }
  };

  // Traditional reference answer fallback
  const loadCorrectAnswer = async (exerciseId) => {
    if (correctAnswers[exerciseId]) {
      setCorrectAnswerOpen(current => ({ ...current, [exerciseId]: !current[exerciseId] }));
      return;
    }
    const res = await fetch(`/api/exercises/${exerciseId}/correct-answer`, { headers: authHeaders });
    if (!res.ok) {
      setError('Failed to load reference answer');
      return;
    }
    const data = await res.json();
    setCorrectAnswers(current => ({ ...current, [exerciseId]: data.answer }));
    setCorrectAnswerOpen(current => ({ ...current, [exerciseId]: true }));
  };

  const selectedSchema = schemas.find(s => s.id === selectedSchemaId);
  const selectedExercise = exercises.find(e => e.id === selectedExerciseId);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div>
            <p className="eyebrow"></p>
            <h1 style={{ margin: 0 }}>Aggregate Modeling</h1>
          </div>
          <div className="topbar-actions">
            <span className="role-pill">{role}</span>
            <button className="secondary-btn" type="button" onClick={onLogout}>
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="main-grid">
        {role === 'teacher' && (
          <aside className="panel">
            <div className="section-title">
              <div>
                <h2>{editingSchemaId ? 'Edit schema' : 'Create schema'}</h2>
                <p>Manage ER schemas and exercises</p>
              </div>
            </div>

            <form className="form" onSubmit={saveSchema}>
              <label className="field">
                Schema name
                <input
                  type="text"
                  value={schemaForm.name}
                  onChange={event => setSchemaForm(current => ({ ...current, name: event.target.value }))}
                  placeholder="Database joins"
                  required
                />
              </label>

              <label className="field">
                ER Diagram image
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  onChange={event => setSchemaForm(current => ({ ...current, image: event.target.files?.[0] || null }))}
                  required={!editingSchemaId}
                />
              </label>
              {schemaForm.image && <div className="file-note">{schemaForm.image.name}</div>}
              <div className="file-note">
                {editingSchemaId ? 'Leave empty to keep current image. ' : ''}
                Use JPG, PNG, WebP, or GIF.
              </div>

              <div className="row-actions">
                <button className="secondary-btn" type="button" onClick={resetSchemaForm}>Reset</button>
                <button className="primary-btn" type="submit">{editingSchemaId ? 'Update schema' : 'Create schema'}</button>
              </div>
            </form>

            <hr style={{ margin: '24px 0', borderColor: '#e5e7eb' }} />

            {selectedSchemaId ? (
              <>
                <div className="section-title">
                  <div>
                    <h2>{editingExerciseId ? 'Edit exercise' : 'Create exercise'}</h2>
                    <p>For: {selectedSchema?.name}</p>
                  </div>
                </div>

                <form className="form" onSubmit={saveExercise}>
                  <label className="field">
                    Exercise name
                    <input
                      type="text"
                      value={exerciseForm.name}
                      onChange={event => setExerciseForm(current => ({ ...current, name: event.target.value }))}
                      placeholder="Query optimization"
                      required
                    />
                  </label>

                  <label className="field">
                    Correct answer
                    <textarea
                      value={exerciseForm.answer}
                      onChange={event => setExerciseForm(current => ({ ...current, answer: event.target.value }))}
                      rows={3}
                      required
                    />
                  </label>

                  {exerciseForm.queries.map((query, index) => (
                    <div className="query-block" key={index}>
                      <label className="field">
                        Query text
                        <textarea
                          value={query.queryText}
                          onChange={event => updateQuery(index, 'queryText', event.target.value)}
                          rows={2}
                          required
                        />
                      </label>
                      <label className="field" style={{ marginTop: 12 }}>
                        Hint
                        <input
                          type="text"
                          value={query.hint}
                          onChange={event => updateQuery(index, 'hint', event.target.value)}
                          placeholder="Formal representation hint"
                        />
                      </label>
                      {exerciseForm.queries.length > 1 && (
                        <button className="secondary-btn danger-btn" type="button" onClick={() => removeQuery(index)} style={{ marginTop: 12 }}>
                          Remove query
                        </button>
                      )}
                    </div>
                  ))}

                  <div className="row-actions">
                    <button className="secondary-btn" type="button" onClick={addQuery}>Add query</button>
                    {editingExerciseId && (
                      <button className="secondary-btn" type="button" onClick={resetExerciseForm}>Cancel</button>
                    )}
                    <button className="primary-btn" type="submit">{editingExerciseId ? 'Update' : 'Create'}</button>
                  </div>
                </form>
              </>
            ) : (
              <div style={{ padding: '16px', backgroundColor: '#f3f4f6', borderRadius: '8px', textAlign: 'center', color: '#6b7280' }}>
                Select a schema to create exercises
              </div>
            )}
          </aside>
        )}

        <section className={role === 'teacher' ? '' : 'panel'} style={role === 'teacher' ? undefined : { gridColumn: '1 / -1' }}>
          {error && <div className="error-box" style={{ marginBottom: 14 }}>{error}</div>}
          {success && <div className="success-box" style={{ marginBottom: 14 }}>{success}</div>}

          {!selectedSchemaId ? (
            <>
              <div className="section-title">
                <div>
                  <h2>ER Schemas</h2>
                  <p>Select a schema to {role === 'student' ? 'view exercises' : 'manage exercises'}</p>
                </div>
                <span className="count-badge">{schemas.length} total</span>
              </div>

              {schemas.length === 0 ? (
                <div className="empty-state">No schemas available yet.</div>
              ) : (
                <div className="exercise-list">
                  {schemas.map(schema => (
                    <article
                      className="exercise-card exercise-card-clickable"
                      key={schema.id}
                      onClick={() => {
                        setSelectedSchemaId(schema.id);
                        loadExercisesForSchema(schema.id);
                        setSelectedExerciseId(null);
                      }}
                    >
                      {brokenImages[schema.id] ? (
                        <div className="image-fallback">
                          This image format cannot be displayed. Upload JPG, PNG, WebP, or GIF.
                        </div>
                      ) : (
                        <img
                          className="exercise-media"
                          src={schema.image}
                          alt={schema.name}
                          onError={() => setBrokenImages(current => ({ ...current, [schema.id]: true }))}
                        />
                      )}
                      <div className="exercise-body">
                        <div className="meta-row">
                          <h3>{schema.name}</h3>
                          <div className="row-actions">
                            {role === 'teacher' && (
                              <button
                                className="secondary-btn"
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startEditSchema(schema);
                                }}
                              >
                                Edit
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : !selectedExerciseId ? (
            <>
              <div className="section-title">
                <div>
                  <h2>{selectedSchema?.name}</h2>
                  <p>Exercises for this schema</p>
                </div>
                <div className="row-actions">
                  <button
                    className="secondary-btn"
                    type="button"
                    onClick={() => {
                      setSelectedSchemaId(null);
                      setSelectedExerciseId(null);
                      setExercises([]);
                    }}
                  >
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
                    <article
                      className="exercise-card exercise-card-clickable"
                      key={exercise.id}
                      onClick={() => setSelectedExerciseId(exercise.id)}
                    >
                      <div className="exercise-body">
                        <div className="meta-row">
                          <h3>{exercise.name}</h3>
                          <div className="row-actions">
                            <span className="count-badge">{exercise.queries?.length || 0} queries</span>
                            {role === 'teacher' && (
                              <button
                                className="secondary-btn"
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startEditExercise(exercise);
                                }}
                              >
                                Edit
                              </button>
                            )}
                          </div>
                        </div>

                        <ul className="query-list">
                          {exercise.queries?.map((query, i) => (
                            <li key={query.id || i}>
                              <strong>{query.queryText}</strong>
                            </li>
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
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedExerciseId(exercise.id);
                            }}
                          >
                            Open exercise
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : (
            selectedExercise && (
              <>
                <div className="section-title">
                  <div>
                    <h2>{selectedExercise.name}</h2>
                    <p>From: {selectedSchema?.name}</p>
                  </div>
                  <button
                    className="secondary-btn"
                    type="button"
                    onClick={() => setSelectedExerciseId(null)}
                  >
                    Back to exercises
                  </button>
                </div>

                <article className="exercise-card">
                  {selectedSchema && (
                    brokenImages[selectedSchema.id] ? (
                      <div className="image-fallback">
                        This image format cannot be displayed. Upload JPG, PNG, WebP, or GIF.
                      </div>
                    ) : (
                      <img
                        className="exercise-media"
                        src={selectedSchema.image}
                        alt={selectedSchema.name}
                        onError={() => setBrokenImages(current => ({ ...current, [selectedSchema.id]: true }))}
                      />
                    )
                  )}
                  <div className="exercise-body">
                    <p className="eyebrow">ER schema: {selectedSchema?.name}</p>
                    <ul className="query-list">
                      {selectedExercise.queries?.map((query, index) => (
                        <li key={query.id || index}>
                          <strong>Query {index + 1}: {query.queryText}</strong>
                          {query.hint && <span className="hint">Hint: {query.hint}</span>}
                        </li>
                      ))}
                    </ul>

                    {role === 'teacher' && selectedExercise.answer && (
                      <div className="answer-log">
                        <strong>Correct answer:</strong> {selectedExercise.answer.answer}
                      </div>
                    )}

                    {role === 'student' && (
                      <form className="form" onSubmit={event => submitStudentAnswer(event, selectedExercise.id)}>
                        <label className="field">
                          Your answer
                          <textarea
                            value={answerForms[selectedExercise.id] || ''}
                            onChange={event =>
                              setAnswerForms(current => ({ ...current, [selectedExercise.id]: event.target.value }))
                            }
                            rows={3}
                            required
                          />
                        </label>
                        <button className="primary-btn" type="submit">Submit answer</button>

                        {evaluations[selectedExercise.id] && (
                          <div className="answer-log">
                            <strong className={`result-label ${evaluations[selectedExercise.id].isCorrect ? 'result-correct' : 'result-wrong'}`}>
                              {evaluations[selectedExercise.id].isCorrect ? 'Correct Score Verified' : 'Evaluation Failed'}
                            </strong>

                            {/* Raw Positional Engine Errors List */}
                            {evaluations[selectedExercise.id].feedback?.length > 0 && (
                              <div className="feedback-box">
                                <strong>Evaluation feedback</strong>
                                <ul className="query-list">
                                  {evaluations[selectedExercise.id].feedback.map((message, index) => (
                                    <li key={index}>{message}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Render split dynamic dynamic buttons conditional checks */}
                            <div className="row-actions" style={{ marginTop: 12, gap: '8px', display: 'flex', flexWrap: 'wrap' }}>
                              {!evaluations[selectedExercise.id].isCorrect ? (
                                <>
                                  {/* Button 1A: Explain Error */}
                                  <button
                                    className="secondary-btn"
                                    type="button"
                                    onClick={() => handleExplainError(selectedExercise.id)}
                                    disabled={explainErrorLoading[selectedExercise.id]}
                                  >
                                    {explainErrorLoading[selectedExercise.id] ? 'Analyzing Error...' : ' Explain Error'}
                                  </button>

                                  {/* Button 1B: Give Me a Hint */}
                                  <button
                                    className="secondary-btn"
                                    type="button"
                                    onClick={() => handleGiveHint(selectedExercise.id)}
                                    disabled={llmHintLoading[selectedExercise.id]}
                                  >
                                    {llmHintLoading[selectedExercise.id] ? 'Generating Hint...' : ' Give Me a Hint'}
                                  </button>

                                  {/* Button 2: Fix My Schema */}
                                  <button
                                    className="secondary-btn"
                                    type="button"
                                    onClick={() => handleFixSchema(selectedExercise.id)}
                                    disabled={fixSchemaLoading[selectedExercise.id]}
                                  >
                                    {fixSchemaLoading[selectedExercise.id] ? 'Rebuilding Layout...' : ' Fix My Schema'}
                                  </button>
                                </>
                              ) : (
                                /* Button 3: Why is it Right? */
                                <button
                                  className="secondary-btn"
                                  type="button"
                                  onClick={() => handleExplainSuccess(selectedExercise.id)}
                                  disabled={explainSuccessLoading[selectedExercise.id]}
                                >
                                  {explainSuccessLoading[selectedExercise.id] ? 'Validating Design...' : ' Why is this correct?'}
                                </button>
                              )}

                              <button
                                className="secondary-btn"
                                type="button"
                                onClick={() => loadCorrectAnswer(selectedExercise.id)}
                              >
                                View Reference Target
                              </button>
                            </div>

                            {/* Render Output Triggers */}
                            {explainErrorOpen[selectedExercise.id] && explainErrorData[selectedExercise.id] && (
                              <div className="review-box" style={{ borderColor: '#ef4444' }}>
                                <strong> Error Structural Analysis:</strong>
                                <pre style={{ whiteSpace: 'pre-wrap' }}>{explainErrorData[selectedExercise.id]}</pre>
                              </div>
                            )}

                            {llmHintOpen[selectedExercise.id] && llmHintData[selectedExercise.id] && (
                              <div className="review-box" style={{ borderColor: '#3b82f6' }}>
                                <strong> Architectural Hint Strategy:</strong>
                                <pre style={{ whiteSpace: 'pre-wrap' }}>{llmHintData[selectedExercise.id]}</pre>
                              </div>
                            )}

                            {fixSchemaOpen[selectedExercise.id] && fixSchemaData[selectedExercise.id] && (
                              <div className="review-box" style={{ borderColor: '#10b981' }}>
                                <strong>🛠️ Corrected Solution Reference:</strong>
                                <pre style={{ whiteSpace: 'pre-wrap' }}>{fixSchemaData[selectedExercise.id]}</pre>
                              </div>
                            )}

                            {explainSuccessOpen[selectedExercise.id] && explainSuccessData[selectedExercise.id] && (
                              <div className="review-box" style={{ borderColor: '#8b5cf6' }}>
                                <strong>🌟 Design Validation Win:</strong>
                                <pre style={{ whiteSpace: 'pre-wrap' }}>{explainSuccessData[selectedExercise.id]}</pre>
                              </div>
                            )}

                            {correctAnswerOpen[selectedExercise.id] && correctAnswers[selectedExercise.id] && (
                              <div className="review-box">
                                <strong>Standard Reference Solution Payload:</strong>
                                <pre style={{ whiteSpace: 'pre-wrap' }}>{correctAnswers[selectedExercise.id]}</pre>
                              </div>
                            )}
                          </div>
                        )}
                      </form>
                    )}
                  </div>
                </article>
              </>
            )
          )}
        </section>
      </main>
    </div>
  );
}

export default MainPage;