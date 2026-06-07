import React, { useEffect, useState } from 'react';
import QueryBlock from './QueryBlock';

const emptyExerciseForm = { name: '', answer: '', queries: [{ queryText: '', hint: '' }] };
const emptySchemaForm   = { name: '', image: null };

export default function TeacherSidebar({
  selectedSchema,
  schemaToEdit,
  exerciseToEdit,
  onSchemaSaved,
  onExerciseSaved,
  onClearSchemaEdit,
  onClearExerciseEdit,
}) {
  // Schema form
  const [schemaForm,     setSchemaForm]     = useState(emptySchemaForm);
  const [editingSchemaId, setEditingSchemaId] = useState(null);
  const [schemaError,    setSchemaError]    = useState('');
  const [schemaSuccess,  setSchemaSuccess]  = useState('');
  const [schemaLoading,  setSchemaLoading]  = useState(false);

  // Exercise form
  const [exerciseForm,      setExerciseForm]      = useState(emptyExerciseForm);
  const [editingExerciseId, setEditingExerciseId] = useState(null);
  const [exError,           setExError]           = useState('');
  const [exSuccess,         setExSuccess]         = useState('');
  const [exLoading,         setExLoading]         = useState(false);

  // Populate the relevant form when an Edit button is clicked in the list.
  useEffect(() => {
    if (schemaToEdit) startEditSchema(schemaToEdit);
  }, [schemaToEdit]);

  useEffect(() => {
    if (exerciseToEdit) startEditExercise(exerciseToEdit);
  }, [exerciseToEdit]);

  // ── Schema handlers ────────────────────────────────────────────────────────
  function startEditSchema(schema) {
    setEditingSchemaId(schema.id);
    setSchemaForm({ name: schema.name, image: null });
    setSchemaError('');
    setSchemaSuccess('');
  }

  function resetSchemaForm() {
    setEditingSchemaId(null);
    setSchemaForm(emptySchemaForm);
    onClearSchemaEdit?.();
  }

  async function handleSaveSchema(e) {
    e.preventDefault();
    setSchemaError('');
    setSchemaSuccess('');
    if (!editingSchemaId && !schemaForm.image) {
      setSchemaError('Please upload an image');
      return;
    }
    const formData = new FormData();
    formData.append('name', schemaForm.name);
    if (schemaForm.image) formData.append('image', schemaForm.image);

    setSchemaLoading(true);
    try {
      await onSchemaSaved(editingSchemaId, formData);
      setSchemaSuccess(editingSchemaId ? 'Schema updated' : 'Schema created');
      resetSchemaForm();
    } catch (err) {
      setSchemaError(err.message);
    } finally {
      setSchemaLoading(false);
    }
  }

  // ── Exercise handlers ──────────────────────────────────────────────────────
  function startEditExercise(exercise) {
    setEditingExerciseId(exercise.id);
    setExerciseForm({
      name: exercise.name,
      answer: exercise.answer?.answer || '',
      queries: exercise.queries?.map(q => ({ queryText: q.queryText, hint: q.hint || '' }))
               ?? [{ queryText: '', hint: '' }],
    });
    setExError('');
    setExSuccess('');
  }

  function resetExerciseForm() {
    setEditingExerciseId(null);
    setExerciseForm(emptyExerciseForm);
    onClearExerciseEdit?.();
  }

  function updateQuery(index, field, value) {
    setExerciseForm(cur => ({
      ...cur,
      queries: cur.queries.map((q, i) => i === index ? { ...q, [field]: value } : q),
    }));
  }

  function addQuery() {
    setExerciseForm(cur => ({ ...cur, queries: [...cur.queries, { queryText: '', hint: '' }] }));
  }

  function removeQuery(index) {
    setExerciseForm(cur => ({ ...cur, queries: cur.queries.filter((_, i) => i !== index) }));
  }

  async function handleSaveExercise(e) {
    e.preventDefault();
    setExError('');
    setExSuccess('');
    if (!selectedSchema) { setExError('Select a schema first'); return; }

    const payload = {
      name: exerciseForm.name,
      answer: exerciseForm.answer,
      queries: exerciseForm.queries,
      schemaId: selectedSchema.id,
    };

    setExLoading(true);
    try {
      await onExerciseSaved(editingExerciseId, payload);
      setExSuccess(editingExerciseId ? 'Exercise updated' : 'Exercise created');
      resetExerciseForm();
    } catch (err) {
      setExError(err.message);
    } finally {
      setExLoading(false);
    }
  }

  return (
    <aside className="panel">

      {/* ── Schema form ── */}
      <div className="section-title">
        <div>
          <h2>{editingSchemaId ? 'Edit schema' : 'Create schema'}</h2>
          <p>Manage ER schemas</p>
        </div>
      </div>

      {schemaError   && <div className="error-box"   style={{ marginBottom: 12 }}>{schemaError}</div>}
      {schemaSuccess && <div className="success-box" style={{ marginBottom: 12 }}>{schemaSuccess}</div>}

      <form className="form" onSubmit={handleSaveSchema}>
        <label className="field">
          Schema name
          <input
            type="text"
            value={schemaForm.name}
            onChange={e => setSchemaForm(c => ({ ...c, name: e.target.value }))}
            placeholder="E-Commerce System"
            required
          />
        </label>
        <label className="field">
          ER Diagram image
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            onChange={e => setSchemaForm(c => ({ ...c, image: e.target.files?.[0] || null }))}
            required={!editingSchemaId}
          />
        </label>
        {schemaForm.image && <div className="file-note">{schemaForm.image.name}</div>}
        <div className="file-note">
          {editingSchemaId ? 'Leave empty to keep current image. ' : ''}
          JPG, PNG, WebP, or GIF — max 5 MB.
        </div>
        <div className="row-actions">
          <button className="secondary-btn" type="button" onClick={resetSchemaForm}>Reset</button>
          <button className="primary-btn" type="submit" disabled={schemaLoading}>
            {schemaLoading ? 'Saving…' : editingSchemaId ? 'Update schema' : 'Create schema'}
          </button>
        </div>
      </form>

      <hr style={{ margin: '24px 0', borderColor: '#e5e7eb' }} />

      {/* ── Exercise form ── */}
      {selectedSchema ? (
        <>
          <div className="section-title">
            <div>
              <h2>{editingExerciseId ? 'Edit exercise' : 'Create exercise'}</h2>
              <p>For: {selectedSchema.name}</p>
            </div>
          </div>

          {exError   && <div className="error-box"   style={{ marginBottom: 12 }}>{exError}</div>}
          {exSuccess && <div className="success-box" style={{ marginBottom: 12 }}>{exSuccess}</div>}

          <form className="form" onSubmit={handleSaveExercise}>
            <label className="field">
              Exercise name
              <input
                type="text"
                value={exerciseForm.name}
                onChange={e => setExerciseForm(c => ({ ...c, name: e.target.value }))}
                placeholder="Task A: Customer nesting"
                required
              />
            </label>
            <label className="field">
              Correct answer
              <textarea
                value={exerciseForm.answer}
                onChange={e => setExerciseForm(c => ({ ...c, answer: e.target.value }))}
                rows={4}
                placeholder="Write the reference JSON-SM schema here"
                required
              />
            </label>

            {exerciseForm.queries.map((q, i) => (
              <QueryBlock
                key={i}
                query={q}
                index={i}
                onChange={updateQuery}
                onRemove={removeQuery}
                canRemove={exerciseForm.queries.length > 1}
              />
            ))}

            <div className="row-actions">
              <button className="secondary-btn" type="button" onClick={addQuery}>
                Add query
              </button>
              {editingExerciseId && (
                <button className="secondary-btn" type="button" onClick={resetExerciseForm}>
                  Cancel
                </button>
              )}
              <button className="primary-btn" type="submit" disabled={exLoading}>
                {exLoading ? 'Saving…' : editingExerciseId ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </>
      ) : (
        <div className="empty-state">Select a schema to create exercises</div>
      )}
    </aside>
  );
}
